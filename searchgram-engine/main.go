package main

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	log "github.com/sirupsen/logrus"
	"github.com/zhishengyuan/searchgram-engine/config"
	"github.com/zhishengyuan/searchgram-engine/engines"
	"github.com/zhishengyuan/searchgram-engine/handlers"
	"github.com/zhishengyuan/searchgram-engine/middleware"
	"golang.org/x/net/http2"
	"golang.org/x/net/http2/h2c"
)

func main() {
	// Load configuration
	configPath := os.Getenv("CONFIG_PATH")
	if configPath == "" {
		configPath = "config.yaml"
	}

	cfg, err := config.Load(configPath)
	if err != nil {
		log.WithError(err).Fatal("Failed to load configuration")
	}

	// Initialize search engine
	var engine engines.SearchEngine
	switch cfg.SearchEngine.Type {
	case "elasticsearch":
		engine, err = engines.NewElasticsearch(
			cfg.Elasticsearch.Host,
			cfg.Elasticsearch.Username,
			cfg.Elasticsearch.Password,
			cfg.Elasticsearch.Index,
			cfg.Elasticsearch.Shards,
			cfg.Elasticsearch.Replicas,
		)
		if err != nil {
			log.WithError(err).Fatal("Failed to initialize Elasticsearch")
		}
	default:
		log.Fatalf("Unsupported search engine type: %s", cfg.SearchEngine.Type)
	}
	defer engine.Close()

	// Create API handler
	apiHandler := handlers.NewAPIHandler(engine)

	// Setup Gin router
	if cfg.Logging.Level != "debug" {
		gin.SetMode(gin.ReleaseMode)
	}

	router := gin.New()

	// Global middleware
	router.Use(middleware.Recovery())
	router.Use(middleware.CORS())
	router.Use(middleware.RequestLogger())
	router.Use(middleware.APIKeyAuth(cfg.Auth.Enabled, cfg.Auth.APIKey))

	// API routes
	v1 := router.Group("/api/v1")
	{
		// Message operations
		v1.POST("/upsert", apiHandler.Upsert)
		v1.POST("/upsert/batch", apiHandler.UpsertBatch)
		v1.POST("/search", apiHandler.Search)
		v1.DELETE("/messages", apiHandler.DeleteMessages)
		v1.DELETE("/users/:user_id", apiHandler.DeleteUser)
		v1.DELETE("/clear", apiHandler.Clear)

		// Health and stats
		v1.GET("/ping", apiHandler.Ping)
		v1.GET("/stats", apiHandler.Stats)
	}

	// Root endpoint
	router.GET("/", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"service": "SearchGram Search Engine",
			"version": "1.0.0",
			"engine":  cfg.SearchEngine.Type,
			"status":  "running",
		})
	})

	// Health check endpoint
	router.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"status": "healthy",
		})
	})

	// Create HTTP/2 handler with h2c (HTTP/2 Cleartext) support
	// This allows HTTP/2 over plain HTTP connections without TLS
	h2s := &http2.Server{}
	h2cHandler := h2c.NewHandler(router, h2s)

	// Create HTTP server with HTTP/2 support
	srv := &http.Server{
		Addr:         fmt.Sprintf("%s:%d", cfg.Server.Host, cfg.Server.Port),
		Handler:      h2cHandler,
		ReadTimeout:  cfg.Server.ReadTimeout,
		WriteTimeout: cfg.Server.WriteTimeout,
	}

	// Start server in goroutine
	go func() {
		log.WithFields(log.Fields{
			"host":     cfg.Server.Host,
			"port":     cfg.Server.Port,
			"engine":   cfg.SearchEngine.Type,
			"http2":    true,
		}).Info("Starting SearchGram Search Engine with HTTP/2 support")

		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.WithError(err).Fatal("Failed to start server")
		}
	}()

	// Wait for interrupt signal to gracefully shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Info("Shutting down server...")

	// Graceful shutdown with 10 second timeout
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		log.WithError(err).Error("Server forced to shutdown")
	}

	log.Info("Server exited")
}
