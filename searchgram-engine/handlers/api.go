package handlers

import (
	"fmt"
	"net/http"
	"os"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
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
