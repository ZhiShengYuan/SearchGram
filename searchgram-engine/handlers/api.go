package handlers

import (
	"fmt"
	"net/http"
	"os"
	"runtime"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/shirou/gopsutil/v3/cpu"
	"github.com/shirou/gopsutil/v3/disk"
	"github.com/shirou/gopsutil/v3/host"
	"github.com/shirou/gopsutil/v3/load"
	"github.com/shirou/gopsutil/v3/mem"
	log "github.com/sirupsen/logrus"
	"github.com/zhishengyuan/searchgram-engine/engines"
	"github.com/zhishengyuan/searchgram-engine/models"
)

// APIHandler handles all API endpoints
type APIHandler struct {
	engine    engines.SearchEngine
	startTime time.Time
}

// NewAPIHandler creates a new API handler
func NewAPIHandler(engine engines.SearchEngine, startTime time.Time) *APIHandler {
	return &APIHandler{
		engine:    engine,
		startTime: startTime,
	}
}

// Upsert handles message indexing
// POST /api/v1/upsert
func (h *APIHandler) Upsert(c *gin.Context) {
	var message models.Message
	if err := c.ShouldBindJSON(&message); err != nil {
		log.WithError(err).Warn("Invalid upsert request")
		c.JSON(http.StatusBadRequest, models.ErrorResponse{
			Error:   "Bad Request",
			Message: err.Error(),
		})
		return
	}

	// Validate required fields
	if message.ID == "" {
		c.JSON(http.StatusBadRequest, models.ErrorResponse{
			Error:   "Bad Request",
			Message: "message ID is required",
		})
		return
	}

	if err := h.engine.Upsert(&message); err != nil {
		log.WithError(err).Error("Failed to upsert message")
		c.JSON(http.StatusInternalServerError, models.ErrorResponse{
			Error:   "Internal Server Error",
			Message: "Failed to index message",
		})
		return
	}

	c.JSON(http.StatusOK, models.UpsertResponse{
		Success: true,
		ID:      message.ID,
	})
}

// UpsertBatch handles batch message indexing
// POST /api/v1/upsert/batch
func (h *APIHandler) UpsertBatch(c *gin.Context) {
	var req models.BatchUpsertRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		log.WithError(err).Warn("Invalid batch upsert request")
		c.JSON(http.StatusBadRequest, models.ErrorResponse{
			Error:   "Bad Request",
			Message: err.Error(),
		})
		return
	}

	// Validate batch not empty
	if len(req.Messages) == 0 {
		c.JSON(http.StatusBadRequest, models.ErrorResponse{
			Error:   "Bad Request",
			Message: "messages array cannot be empty",
		})
		return
	}

	// Validate individual messages
	for i, message := range req.Messages {
		if message.ID == "" {
			c.JSON(http.StatusBadRequest, models.ErrorResponse{
				Error:   "Bad Request",
				Message: fmt.Sprintf("message at index %d is missing ID", i),
			})
			return
		}
	}

	log.WithField("count", len(req.Messages)).Info("Processing batch upsert")

	indexed, errors, err := h.engine.UpsertBatch(req.Messages)
	if err != nil {
		log.WithError(err).Error("Failed to batch upsert messages")
		c.JSON(http.StatusInternalServerError, models.ErrorResponse{
			Error:   "Internal Server Error",
			Message: "Failed to batch index messages",
		})
		return
	}

	failed := len(req.Messages) - indexed

	c.JSON(http.StatusOK, models.BatchUpsertResponse{
		Success:      failed == 0,
		IndexedCount: indexed,
		FailedCount:  failed,
		Errors:       errors,
	})
}

// Search handles search queries
// POST /api/v1/search
func (h *APIHandler) Search(c *gin.Context) {
	// Start timing
	startTime := time.Now()

	var req models.SearchRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		log.WithError(err).Warn("Invalid search request")
		c.JSON(http.StatusBadRequest, models.ErrorResponse{
			Error:   "Bad Request",
			Message: err.Error(),
		})
		return
	}

	// Set defaults
	if req.Page < 1 {
		req.Page = 1
	}
	if req.PageSize < 1 {
		req.PageSize = 10
	}
	if req.PageSize > 100 {
		req.PageSize = 100 // Max page size
	}

	result, err := h.engine.Search(&req)
	if err != nil {
		log.WithError(err).Error("Search failed")
		c.JSON(http.StatusInternalServerError, models.ErrorResponse{
			Error:   "Internal Server Error",
			Message: "Search query failed",
		})
		return
	}

	// Calculate elapsed time in milliseconds
	tookMs := time.Since(startTime).Milliseconds()

	// Add timing to response
	result.TookMs = tookMs

	c.JSON(http.StatusOK, result)
}

// DeleteMessages handles deletion by chat ID
// DELETE /api/v1/messages?chat_id=123456
func (h *APIHandler) DeleteMessages(c *gin.Context) {
	chatIDStr := c.Query("chat_id")
	if chatIDStr == "" {
		c.JSON(http.StatusBadRequest, models.ErrorResponse{
			Error:   "Bad Request",
			Message: "chat_id query parameter is required",
		})
		return
	}

	chatID, err := strconv.ParseInt(chatIDStr, 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, models.ErrorResponse{
			Error:   "Bad Request",
			Message: "Invalid chat_id",
		})
		return
	}

	deletedCount, err := h.engine.Delete(chatID)
	if err != nil {
		log.WithError(err).Error("Failed to delete messages")
		c.JSON(http.StatusInternalServerError, models.ErrorResponse{
			Error:   "Internal Server Error",
			Message: "Failed to delete messages",
		})
		return
	}

	c.JSON(http.StatusOK, models.DeleteResponse{
		Success:      true,
		DeletedCount: deletedCount,
	})
}

// DeleteUser handles deletion by user ID
// DELETE /api/v1/users/:user_id
func (h *APIHandler) DeleteUser(c *gin.Context) {
	userIDStr := c.Param("user_id")
	if userIDStr == "" {
		c.JSON(http.StatusBadRequest, models.ErrorResponse{
			Error:   "Bad Request",
			Message: "user_id is required",
		})
		return
	}

	userID, err := strconv.ParseInt(userIDStr, 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, models.ErrorResponse{
			Error:   "Bad Request",
			Message: "Invalid user_id",
		})
		return
	}

	deletedCount, err := h.engine.DeleteUser(userID)
	if err != nil {
		log.WithError(err).Error("Failed to delete user messages")
		c.JSON(http.StatusInternalServerError, models.ErrorResponse{
			Error:   "Internal Server Error",
			Message: "Failed to delete user messages",
		})
		return
	}

	c.JSON(http.StatusOK, models.DeleteResponse{
		Success:      true,
		DeletedCount: deletedCount,
	})
}

// Clear handles database clearing
// DELETE /api/v1/clear
func (h *APIHandler) Clear(c *gin.Context) {
	if err := h.engine.Clear(); err != nil {
		log.WithError(err).Error("Failed to clear database")
		c.JSON(http.StatusInternalServerError, models.ErrorResponse{
			Error:   "Internal Server Error",
			Message: "Failed to clear database",
		})
		return
	}

	c.JSON(http.StatusOK, models.ClearResponse{
		Success: true,
		Message: "Database cleared successfully",
	})
}

// Ping handles health checks
// GET /api/v1/ping
func (h *APIHandler) Ping(c *gin.Context) {
	result, err := h.engine.Ping()
	if err != nil {
		log.WithError(err).Error("Ping failed")
		c.JSON(http.StatusServiceUnavailable, models.ErrorResponse{
			Error:   "Service Unavailable",
			Message: "Search engine is not available",
		})
		return
	}

	c.JSON(http.StatusOK, result)
}

// Stats handles statistics requests
// GET /api/v1/stats
func (h *APIHandler) Stats(c *gin.Context) {
	result, err := h.engine.Stats()
	if err != nil {
		log.WithError(err).Error("Failed to get stats")
		c.JSON(http.StatusInternalServerError, models.ErrorResponse{
			Error:   "Internal Server Error",
			Message: "Failed to retrieve statistics",
		})
		return
	}

	c.JSON(http.StatusOK, result)
}

// Dedup handles deduplication requests
// POST /api/v1/dedup
func (h *APIHandler) Dedup(c *gin.Context) {
	log.Info("Starting deduplication...")

	result, err := h.engine.Dedup()
	if err != nil {
		log.WithError(err).Error("Deduplication failed")
		c.JSON(http.StatusInternalServerError, models.ErrorResponse{
			Error:   "Internal Server Error",
			Message: "Deduplication failed",
		})
		return
	}

	c.JSON(http.StatusOK, result)
}

// CleanCommands handles cleaning command messages (starting with '/')
// DELETE /api/v1/commands
func (h *APIHandler) CleanCommands(c *gin.Context) {
	log.Info("Starting command cleanup...")

	result, err := h.engine.CleanCommands()
	if err != nil {
		log.WithError(err).Error("Command cleanup failed")
		c.JSON(http.StatusInternalServerError, models.ErrorResponse{
			Error:   "Internal Server Error",
			Message: "Command cleanup failed",
		})
		return
	}

	c.JSON(http.StatusOK, result)
}

// Status handles health/status checks (new standardized endpoint)
// GET /api/v1/status
func (h *APIHandler) Status(c *gin.Context) {
	// Get total documents
	result, err := h.engine.Ping()
	totalDocs := int64(0)
	if err == nil {
		totalDocs = result.TotalDocuments
	}

	// Calculate uptime
	uptimeSeconds := int64(time.Since(h.startTime).Seconds())

	// Get hostname
	hostname, err := os.Hostname()
	if err != nil {
		hostname = "unknown"
	}

	c.JSON(http.StatusOK, gin.H{
		"service":             "search",
		"status":              "ok",
		"hostname":            hostname,
		"uptime_seconds":      uptimeSeconds,
		"message_index_total": totalDocs,
		"timestamp":           time.Now().UTC().Format(time.RFC3339),
	})
}

// SoftDeleteMessage handles soft-deleting a single message
// POST /api/v1/messages/soft-delete
func (h *APIHandler) SoftDeleteMessage(c *gin.Context) {
	var req struct {
		ChatID    int64 `json:"chat_id" binding:"required"`
		MessageID int64 `json:"message_id" binding:"required"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		log.WithError(err).Warn("Invalid soft-delete request")
		c.JSON(http.StatusBadRequest, models.ErrorResponse{
			Error:   "Bad Request",
			Message: err.Error(),
		})
		return
	}

	if err := h.engine.SoftDeleteMessage(req.ChatID, req.MessageID); err != nil {
		log.WithError(err).Error("Failed to soft-delete message")
		c.JSON(http.StatusInternalServerError, models.ErrorResponse{
			Error:   "Internal Server Error",
			Message: "Failed to soft-delete message",
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"message": fmt.Sprintf("Message %d-%d marked as deleted", req.ChatID, req.MessageID),
	})
}

// UserStats handles user activity statistics requests
// POST /api/v1/stats/user
func (h *APIHandler) UserStats(c *gin.Context) {
	var req models.UserStatsRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		log.WithError(err).Warn("Invalid user stats request")
		c.JSON(http.StatusBadRequest, models.ErrorResponse{
			Error:   "Bad Request",
			Message: err.Error(),
		})
		return
	}

	// Validate required fields
	if req.GroupID == 0 {
		c.JSON(http.StatusBadRequest, models.ErrorResponse{
			Error:   "Bad Request",
			Message: "group_id is required",
		})
		return
	}
	if req.UserID == 0 {
		c.JSON(http.StatusBadRequest, models.ErrorResponse{
			Error:   "Bad Request",
			Message: "user_id is required",
		})
		return
	}
	if req.FromTimestamp == 0 || req.ToTimestamp == 0 {
		c.JSON(http.StatusBadRequest, models.ErrorResponse{
			Error:   "Bad Request",
			Message: "from_timestamp and to_timestamp are required",
		})
		return
	}
	if req.FromTimestamp > req.ToTimestamp {
		c.JSON(http.StatusBadRequest, models.ErrorResponse{
			Error:   "Bad Request",
			Message: "from_timestamp must be less than to_timestamp",
		})
		return
	}

	result, err := h.engine.GetUserStats(&req)
	if err != nil {
		log.WithError(err).Error("Failed to get user stats")
		c.JSON(http.StatusInternalServerError, models.ErrorResponse{
			Error:   "Internal Server Error",
			Message: "Failed to retrieve user statistics",
		})
		return
	}

	c.JSON(http.StatusOK, result)
}

// SystemInfo handles system information requests
// GET /api/v1/health/system
func (h *APIHandler) SystemInfo(c *gin.Context) {
	// Get memory stats
	memInfo, err := mem.VirtualMemory()
	if err != nil {
		log.WithError(err).Error("Failed to get memory info")
	}

	swapInfo, err := mem.SwapMemory()
	if err != nil {
		log.WithError(err).Error("Failed to get swap info")
	}

	// Get CPU stats
	cpuPercent, err := cpu.Percent(time.Second, false)
	if err != nil {
		log.WithError(err).Error("Failed to get CPU usage")
	}
	cpuUsage := 0.0
	if len(cpuPercent) > 0 {
		cpuUsage = cpuPercent[0]
	}

	cpuCounts, _ := cpu.Counts(true)  // logical cores
	cpuCountsPhysical, _ := cpu.Counts(false) // physical cores

	// Get CPU model/info
	cpuModel := "Unknown"
	cpuInfos, err := cpu.Info()
	if err == nil && len(cpuInfos) > 0 {
		cpuModel = cpuInfos[0].ModelName
	}

	// Get load average
	loadAvg, err := load.Avg()
	loadAvgData := map[string]float64{
		"1min":  0,
		"5min":  0,
		"15min": 0,
	}
	if err == nil && loadAvg != nil {
		loadAvgData["1min"] = loadAvg.Load1
		loadAvgData["5min"] = loadAvg.Load5
		loadAvgData["15min"] = loadAvg.Load15
	}

	// Get disk stats (root partition)
	diskInfo, err := disk.Usage("/")
	if err != nil {
		log.WithError(err).Error("Failed to get disk info")
	}

	// Get host info (uptime, OS, etc.)
	hostInfo, err := host.Info()
	if err != nil {
		log.WithError(err).Error("Failed to get host info")
	}

	// Calculate uptime
	uptimeSeconds := int64(0)
	uptimeFormatted := "unknown"
	if hostInfo != nil {
		uptimeSeconds = int64(hostInfo.Uptime)
		uptimeFormatted = formatDuration(time.Duration(uptimeSeconds) * time.Second)
	}

	// Build response
	response := gin.H{
		"service":   "search",
		"timestamp": time.Now().UTC().Format(time.RFC3339),
		"system": gin.H{
			"cpu": gin.H{
				"model":          cpuModel,
				"usage_percent":  round(cpuUsage, 2),
				"count_logical":  cpuCounts,
				"count_physical": cpuCountsPhysical,
				"load_average":   loadAvgData,
			},
			"memory": gin.H{
				"total_gb":     round(float64(memInfo.Total)/(1024*1024*1024), 2),
				"used_gb":      round(float64(memInfo.Used)/(1024*1024*1024), 2),
				"available_gb": round(float64(memInfo.Available)/(1024*1024*1024), 2),
				"percent":      round(memInfo.UsedPercent, 2),
				"swap_total_gb": round(float64(swapInfo.Total)/(1024*1024*1024), 2),
				"swap_used_gb":  round(float64(swapInfo.Used)/(1024*1024*1024), 2),
				"swap_percent":  round(swapInfo.UsedPercent, 2),
			},
			"disk": gin.H{
				"total_gb": round(float64(diskInfo.Total)/(1024*1024*1024), 2),
				"used_gb":  round(float64(diskInfo.Used)/(1024*1024*1024), 2),
				"free_gb":  round(float64(diskInfo.Free)/(1024*1024*1024), 2),
				"percent":  round(diskInfo.UsedPercent, 2),
			},
			"uptime": gin.H{
				"seconds":   uptimeSeconds,
				"formatted": uptimeFormatted,
			},
			"os": gin.H{
				"system":   runtime.GOOS,
				"platform": hostInfo.Platform,
				"release":  hostInfo.PlatformVersion,
				"machine":  runtime.GOARCH,
			},
		},
	}

	c.JSON(http.StatusOK, response)
}

// Helper function to round float64 to specified decimal places
func round(val float64, precision int) float64 {
	ratio := float64(1)
	for i := 0; i < precision; i++ {
		ratio *= 10
	}
	return float64(int(val*ratio)) / ratio
}

// Helper function to format duration into human-readable string
func formatDuration(d time.Duration) string {
	days := int(d.Hours() / 24)
	hours := int(d.Hours()) % 24
	minutes := int(d.Minutes()) % 60
	seconds := int(d.Seconds()) % 60

	if days > 0 {
		return fmt.Sprintf("%dd %dh %dm %ds", days, hours, minutes, seconds)
	} else if hours > 0 {
		return fmt.Sprintf("%dh %dm %ds", hours, minutes, seconds)
	} else if minutes > 0 {
		return fmt.Sprintf("%dm %ds", minutes, seconds)
	}
	return fmt.Sprintf("%ds", seconds)
}
