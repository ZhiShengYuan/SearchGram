package handlers

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
	log "github.com/sirupsen/logrus"
	"github.com/zhishengyuan/searchgram-engine/engines"
	"github.com/zhishengyuan/searchgram-engine/models"
)

// APIHandler handles all API endpoints
type APIHandler struct {
	engine engines.SearchEngine
}

// NewAPIHandler creates a new API handler
func NewAPIHandler(engine engines.SearchEngine) *APIHandler {
	return &APIHandler{
		engine: engine,
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

// Search handles search queries
// POST /api/v1/search
func (h *APIHandler) Search(c *gin.Context) {
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
