package middleware

import (
	"net/http"

	"github.com/gin-gonic/gin"
	log "github.com/sirupsen/logrus"
)

// APIKeyAuth middleware validates API key if authentication is enabled
func APIKeyAuth(enabled bool, apiKey string) gin.HandlerFunc {
	return func(c *gin.Context) {
		if !enabled {
			c.Next()
			return
		}

		// Get API key from header
		providedKey := c.GetHeader("X-API-Key")
		if providedKey == "" {
			providedKey = c.GetHeader("Authorization")
			if len(providedKey) > 7 && providedKey[:7] == "Bearer " {
				providedKey = providedKey[7:]
			}
		}

		// Validate API key
		if providedKey != apiKey {
			log.WithFields(log.Fields{
				"ip":     c.ClientIP(),
				"path":   c.Request.URL.Path,
				"method": c.Request.Method,
			}).Warn("Unauthorized API request")

			c.JSON(http.StatusUnauthorized, gin.H{
				"error":   "Unauthorized",
				"message": "Invalid or missing API key",
			})
			c.Abort()
			return
		}

		c.Next()
	}
}

// RequestLogger logs all incoming requests
func RequestLogger() gin.HandlerFunc {
	return func(c *gin.Context) {
		// Start timer
		start := c.GetTime("start")

		// Process request
		c.Next()

		// Calculate latency
		latency := c.GetDuration("latency")

		// Log request
		log.WithFields(log.Fields{
			"status":     c.Writer.Status(),
			"method":     c.Request.Method,
			"path":       c.Request.URL.Path,
			"ip":         c.ClientIP(),
			"latency_ms": latency.Milliseconds(),
			"user_agent": c.Request.UserAgent(),
		}).Info("HTTP request")
	}
}

// CORS middleware enables Cross-Origin Resource Sharing
func CORS() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Writer.Header().Set("Access-Control-Allow-Origin", "*")
		c.Writer.Header().Set("Access-Control-Allow-Credentials", "true")
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Content-Length, Accept-Encoding, X-CSRF-Token, Authorization, X-API-Key, accept, origin, Cache-Control, X-Requested-With")
		c.Writer.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS, GET, PUT, DELETE")

		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(http.StatusNoContent)
			return
		}

		c.Next()
	}
}

// Recovery middleware recovers from panics
func Recovery() gin.HandlerFunc {
	return gin.CustomRecovery(func(c *gin.Context, recovered interface{}) {
		log.WithFields(log.Fields{
			"error":  recovered,
			"path":   c.Request.URL.Path,
			"method": c.Request.Method,
		}).Error("Panic recovered")

		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Internal Server Error",
			"message": "An unexpected error occurred",
		})
	})
}
