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
	Server        ServerConfig        `mapstructure:"server" json:"server"`
	SearchEngine  SearchEngineConfig  `mapstructure:"search_engine" json:"search_engine"`
	Elasticsearch ElasticsearchConfig `mapstructure:"elasticsearch" json:"elasticsearch"`
	Auth          AuthConfig          `mapstructure:"auth" json:"auth"`
	Logging       LoggingConfig       `mapstructure:"logging" json:"logging"`
	Cache         CacheConfig         `mapstructure:"cache" json:"cache"`
}

// ServerConfig holds HTTP server configuration
type ServerConfig struct {
	Host         string        `mapstructure:"host" json:"host"`
	Port         int           `mapstructure:"port" json:"port"`
	ReadTimeout  time.Duration `mapstructure:"read_timeout" json:"read_timeout"`
	WriteTimeout time.Duration `mapstructure:"write_timeout" json:"write_timeout"`
}

// SearchEngineConfig holds search engine type configuration
type SearchEngineConfig struct {
	Type string `mapstructure:"type" json:"type"` // elasticsearch, meilisearch, mongodb, zinc
}

// ElasticsearchConfig holds Elasticsearch-specific configuration
type ElasticsearchConfig struct {
	Host     string `mapstructure:"host" json:"host"`
	Username string `mapstructure:"username" json:"username"`
	Password string `mapstructure:"password" json:"password"`
	Index    string `mapstructure:"index" json:"index"`
	Shards   int    `mapstructure:"shards" json:"shards"`
	Replicas int    `mapstructure:"replicas" json:"replicas"`
}

// AuthConfig holds authentication configuration
type AuthConfig struct {
	// Legacy API key auth (deprecated)
	Enabled bool   `mapstructure:"enabled" json:"enabled"`
	APIKey  string `mapstructure:"api_key" json:"api_key"`

	// JWT auth (recommended)
	UseJWT           bool        `mapstructure:"use_jwt" json:"use_jwt"`
	Issuer           string      `mapstructure:"issuer" json:"issuer"`
	Audience         string      `mapstructure:"audience" json:"audience"`
	PublicKeyPath    string      `mapstructure:"public_key_path" json:"public_key_path"`
	PrivateKeyPath   string      `mapstructure:"private_key_path" json:"private_key_path"`
	PublicKeyInline  interface{} `mapstructure:"public_key_inline" json:"public_key_inline"`
	PrivateKeyInline interface{} `mapstructure:"private_key_inline" json:"private_key_inline"`
	TokenTTL         int         `mapstructure:"token_ttl" json:"token_ttl"` // seconds
}

// LoggingConfig holds logging configuration
type LoggingConfig struct {
	Level  string `mapstructure:"level" json:"level"`
	Format string `mapstructure:"format" json:"format"` // json or text
}

// CacheConfig holds caching configuration
type CacheConfig struct {
	Enabled bool          `mapstructure:"enabled" json:"enabled"`
	TTL     time.Duration `mapstructure:"ttl" json:"ttl"`
}

// Load loads configuration from file and environment
func Load(configPath string) (*Config, error) {
	v := viper.New()

	// Set defaults
	setDefaults(v)

	// Load from config file if provided
	if configPath != "" {
		v.SetConfigFile(configPath)

		// Detect file type based on extension
		if strings.HasSuffix(configPath, ".json") {
			v.SetConfigType("json")
		} else if strings.HasSuffix(configPath, ".yaml") || strings.HasSuffix(configPath, ".yml") {
			v.SetConfigType("yaml")
		}

		if err := v.ReadInConfig(); err != nil {
			log.WithError(err).Warn("Failed to read config file, using defaults")
		} else {
			log.WithField("file", configPath).Info("Loaded configuration file")
		}
	}

	// Environment variables override
	v.SetEnvPrefix("ENGINE")
	v.SetEnvKeyReplacer(strings.NewReplacer(".", "_"))
	v.AutomaticEnv()

	// For unified config.json, read from search_service section
	var cfg Config
	if v.IsSet("search_service") {
		// Reading from unified config.json format
		if err := v.UnmarshalKey("search_service", &cfg); err != nil {
			return nil, fmt.Errorf("failed to unmarshal search_service config: %w", err)
		}

		// Also read auth from top-level auth section for JWT keys
		if v.IsSet("auth") {
			var authCfg AuthConfig
			if err := v.UnmarshalKey("auth", &authCfg); err == nil {
				// Use JWT settings from top-level auth section
				cfg.Auth.UseJWT = authCfg.UseJWT
				cfg.Auth.Issuer = authCfg.Issuer
				cfg.Auth.Audience = authCfg.Audience
				cfg.Auth.PublicKeyPath = authCfg.PublicKeyPath
				cfg.Auth.PrivateKeyPath = authCfg.PrivateKeyPath
				cfg.Auth.PublicKeyInline = authCfg.PublicKeyInline
				cfg.Auth.PrivateKeyInline = authCfg.PrivateKeyInline
				cfg.Auth.TokenTTL = authCfg.TokenTTL
			}
		}

		// Set search engine type to elasticsearch (only supported type)
		cfg.SearchEngine.Type = "elasticsearch"
	} else {
		// Reading from standalone config.yaml format (legacy)
		if err := v.Unmarshal(&cfg); err != nil {
			return nil, fmt.Errorf("failed to unmarshal config: %w", err)
		}
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
	v.SetDefault("auth.use_jwt", true)
	v.SetDefault("auth.issuer", "search")
	v.SetDefault("auth.audience", "internal")
	v.SetDefault("auth.public_key_path", "keys/public.key")
	v.SetDefault("auth.private_key_path", "keys/private.key")
	v.SetDefault("auth.token_ttl", 300)

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

	// Validate JWT config
	if c.Auth.UseJWT {
		if c.Auth.Issuer == "" {
			return fmt.Errorf("JWT issuer is required when JWT auth is enabled")
		}
		if c.Auth.Audience == "" {
			return fmt.Errorf("JWT audience is required when JWT auth is enabled")
		}
		// Either path-based OR inline keys are acceptable
		if c.Auth.PublicKeyPath == "" && c.Auth.PublicKeyInline == nil {
			return fmt.Errorf("JWT public key (path or inline) is required when JWT auth is enabled")
		}
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
