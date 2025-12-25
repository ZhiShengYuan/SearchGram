package config

import (
	"fmt"
	"strings"
	"time"

	log "github.com/sirupsen/logrus"
	"github.com/spf13/viper"
)

// Config holds all configuration for the search service
type Config struct {
	Server        ServerConfig        `mapstructure:"server"`
	SearchEngine  SearchEngineConfig  `mapstructure:"search_engine"`
	Elasticsearch ElasticsearchConfig `mapstructure:"elasticsearch"`
	Auth          AuthConfig          `mapstructure:"auth"`
	Logging       LoggingConfig       `mapstructure:"logging"`
	Cache         CacheConfig         `mapstructure:"cache"`
}

// ServerConfig holds HTTP server configuration
type ServerConfig struct {
	Host         string        `mapstructure:"host"`
	Port         int           `mapstructure:"port"`
	ReadTimeout  time.Duration `mapstructure:"read_timeout"`
	WriteTimeout time.Duration `mapstructure:"write_timeout"`
}

// SearchEngineConfig holds search engine type configuration
type SearchEngineConfig struct {
	Type string `mapstructure:"type"` // elasticsearch, meilisearch, mongodb, zinc
}

// ElasticsearchConfig holds Elasticsearch-specific configuration
type ElasticsearchConfig struct {
	Host     string `mapstructure:"host"`
	Username string `mapstructure:"username"`
	Password string `mapstructure:"password"`
	Index    string `mapstructure:"index"`
	Shards   int    `mapstructure:"shards"`
	Replicas int    `mapstructure:"replicas"`
}

// AuthConfig holds authentication configuration
type AuthConfig struct {
	Enabled bool   `mapstructure:"enabled"`
	APIKey  string `mapstructure:"api_key"`
}

// LoggingConfig holds logging configuration
type LoggingConfig struct {
	Level  string `mapstructure:"level"`
	Format string `mapstructure:"format"` // json or text
}

// CacheConfig holds caching configuration
type CacheConfig struct {
	Enabled bool          `mapstructure:"enabled"`
	TTL     time.Duration `mapstructure:"ttl"`
}

// Load loads configuration from file and environment
func Load(configPath string) (*Config, error) {
	v := viper.New()

	// Set defaults
	setDefaults(v)

	// Load from config file if provided
	if configPath != "" {
		v.SetConfigFile(configPath)
		if err := v.ReadInConfig(); err != nil {
			log.WithError(err).Warn("Failed to read config file, using defaults")
		}
	}

	// Environment variables override
	v.SetEnvPrefix("ENGINE")
	v.SetEnvKeyReplacer(strings.NewReplacer(".", "_"))
	v.AutomaticEnv()

	// Unmarshal into config struct
	var cfg Config
	if err := v.Unmarshal(&cfg); err != nil {
		return nil, fmt.Errorf("failed to unmarshal config: %w", err)
	}

	// Validate configuration
	if err := cfg.Validate(); err != nil {
		return nil, fmt.Errorf("invalid configuration: %w", err)
	}

	// Configure logging
	configureLogging(&cfg.Logging)

	log.WithFields(log.Fields{
		"host":   cfg.Server.Host,
		"port":   cfg.Server.Port,
		"engine": cfg.SearchEngine.Type,
	}).Info("Configuration loaded")

	return &cfg, nil
}

// setDefaults sets default configuration values
func setDefaults(v *viper.Viper) {
	// Server defaults
	v.SetDefault("server.host", "0.0.0.0")
	v.SetDefault("server.port", 8080)
	v.SetDefault("server.read_timeout", 30*time.Second)
	v.SetDefault("server.write_timeout", 30*time.Second)

	// Search engine defaults
	v.SetDefault("search_engine.type", "elasticsearch")

	// Elasticsearch defaults
	v.SetDefault("elasticsearch.host", "http://elasticsearch:9200")
	v.SetDefault("elasticsearch.username", "elastic")
	v.SetDefault("elasticsearch.password", "changeme")
	v.SetDefault("elasticsearch.index", "telegram")
	v.SetDefault("elasticsearch.shards", 3)
	v.SetDefault("elasticsearch.replicas", 1)

	// Auth defaults
	v.SetDefault("auth.enabled", false)
	v.SetDefault("auth.api_key", "")

	// Logging defaults
	v.SetDefault("logging.level", "info")
	v.SetDefault("logging.format", "json")

	// Cache defaults
	v.SetDefault("cache.enabled", false)
	v.SetDefault("cache.ttl", 300*time.Second)
}

// Validate validates the configuration
func (c *Config) Validate() error {
	// Validate server config
	if c.Server.Port < 1 || c.Server.Port > 65535 {
		return fmt.Errorf("invalid server port: %d", c.Server.Port)
	}

	// Validate search engine type
	validEngines := map[string]bool{
		"elasticsearch": true,
		"meilisearch":   true,
		"mongodb":       true,
		"zinc":          true,
	}
	if !validEngines[c.SearchEngine.Type] {
		return fmt.Errorf("invalid search engine type: %s", c.SearchEngine.Type)
	}

	// Validate Elasticsearch config if selected
	if c.SearchEngine.Type == "elasticsearch" {
		if c.Elasticsearch.Host == "" {
			return fmt.Errorf("elasticsearch host is required")
		}
		if c.Elasticsearch.Index == "" {
			return fmt.Errorf("elasticsearch index is required")
		}
	}

	// Validate auth config
	if c.Auth.Enabled && c.Auth.APIKey == "" {
		return fmt.Errorf("API key is required when auth is enabled")
	}

	return nil
}

// configureLogging configures the logging system
func configureLogging(cfg *LoggingConfig) {
	// Set log level
	level, err := log.ParseLevel(cfg.Level)
	if err != nil {
		log.Warn("Invalid log level, using info")
		level = log.InfoLevel
	}
	log.SetLevel(level)

	// Set log format
	if cfg.Format == "json" {
		log.SetFormatter(&log.JSONFormatter{
			TimestampFormat: time.RFC3339,
		})
	} else {
		log.SetFormatter(&log.TextFormatter{
			FullTimestamp:   true,
			TimestampFormat: time.RFC3339,
		})
	}
}
