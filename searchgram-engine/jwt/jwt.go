package jwt

import (
	"crypto/ed25519"
	"crypto/x509"
	"encoding/pem"
	"fmt"
	"io/ioutil"
	"net/http"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
	log "github.com/sirupsen/logrus"
	"github.com/google/uuid"
)

// Config holds JWT configuration
type Config struct {
	Issuer           string
	Audience         string
	PublicKeyPath    string
	PrivateKeyPath   string
	PublicKeyInline  interface{} // Can be string or []string
	PrivateKeyInline interface{} // Can be string or []string
	TokenTTL         int         // seconds
}

// JWTAuth handles JWT authentication
type JWTAuth struct {
	issuer     string
	audience   string
	publicKey  ed25519.PublicKey
	privateKey ed25519.PrivateKey
	tokenTTL   int
}

// Claims represents JWT claims
type Claims struct {
	jwt.RegisteredClaims
}

// NewJWTAuth creates a new JWT authenticator
func NewJWTAuth(cfg Config) (*JWTAuth, error) {
	auth := &JWTAuth{
		issuer:   cfg.Issuer,
		audience: cfg.Audience,
		tokenTTL: cfg.TokenTTL,
	}

	if cfg.TokenTTL == 0 {
		auth.tokenTTL = 300 // Default 5 minutes
	}

	// Load public key (required for verification)
	if cfg.PublicKeyInline != nil {
		// Use inline key
		keyData, err := parseInlineKey(cfg.PublicKeyInline)
		if err != nil {
			return nil, fmt.Errorf("failed to parse inline public key: %w", err)
		}
		publicKey, err := parsePublicKey(keyData)
		if err != nil {
			return nil, fmt.Errorf("failed to parse inline public key: %w", err)
		}
		auth.publicKey = publicKey
		log.Info("Loaded Ed25519 public key from inline config")
	} else if cfg.PublicKeyPath != "" {
		// Load from file
		publicKey, err := loadPublicKey(cfg.PublicKeyPath)
		if err != nil {
			return nil, fmt.Errorf("failed to load public key: %w", err)
		}
		auth.publicKey = publicKey
		log.WithField("path", cfg.PublicKeyPath).Info("Loaded Ed25519 public key from file")
	}

	// Load private key (optional, for generating tokens)
	if cfg.PrivateKeyInline != nil {
		// Use inline key
		keyData, err := parseInlineKey(cfg.PrivateKeyInline)
		if err != nil {
			return nil, fmt.Errorf("failed to parse inline private key: %w", err)
		}
		privateKey, err := parsePrivateKey(keyData)
		if err != nil {
			return nil, fmt.Errorf("failed to parse inline private key: %w", err)
		}
		auth.privateKey = privateKey
		log.Info("Loaded Ed25519 private key from inline config")
	} else if cfg.PrivateKeyPath != "" {
		// Load from file
		privateKey, err := loadPrivateKey(cfg.PrivateKeyPath)
		if err != nil {
			return nil, fmt.Errorf("failed to load private key: %w", err)
		}
		auth.privateKey = privateKey
		log.WithField("path", cfg.PrivateKeyPath).Info("Loaded Ed25519 private key from file")
	}

	log.WithFields(log.Fields{
		"issuer":      auth.issuer,
		"audience":    auth.audience,
		"has_public":  auth.publicKey != nil,
		"has_private": auth.privateKey != nil,
	}).Info("JWT auth initialized")

	return auth, nil
}

// parseInlineKey parses inline key from string or string array
func parseInlineKey(key interface{}) ([]byte, error) {
	switch v := key.(type) {
	case string:
		// Single-line string with \n
		return []byte(strings.ReplaceAll(v, "\\n", "\n")), nil
	case []interface{}:
		// JSON array of lines
		var lines []string
		for _, line := range v {
			if str, ok := line.(string); ok {
				lines = append(lines, str)
			} else {
				return nil, fmt.Errorf("invalid line type in key array")
			}
		}
		return []byte(strings.Join(lines, "\n")), nil
	case []string:
		// String array
		return []byte(strings.Join(v, "\n")), nil
	default:
		return nil, fmt.Errorf("invalid inline key type: %T", key)
	}
}

// parsePublicKey parses an Ed25519 public key from PEM data
func parsePublicKey(keyData []byte) (ed25519.PublicKey, error) {
	block, _ := pem.Decode(keyData)
	if block == nil {
		return nil, fmt.Errorf("failed to decode PEM block")
	}

	pub, err := x509.ParsePKIXPublicKey(block.Bytes)
	if err != nil {
		return nil, fmt.Errorf("failed to parse public key: %w", err)
	}

	edPub, ok := pub.(ed25519.PublicKey)
	if !ok {
		return nil, fmt.Errorf("key is not an Ed25519 public key")
	}

	return edPub, nil
}

// loadPublicKey loads an Ed25519 public key from PEM file
func loadPublicKey(path string) (ed25519.PublicKey, error) {
	keyData, err := ioutil.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("failed to read public key file: %w", err)
	}

	return parsePublicKey(keyData)
}

// parsePrivateKey parses an Ed25519 private key from PEM data
func parsePrivateKey(keyData []byte) (ed25519.PrivateKey, error) {
	block, _ := pem.Decode(keyData)
	if block == nil {
		return nil, fmt.Errorf("failed to decode PEM block")
	}

	priv, err := x509.ParsePKCS8PrivateKey(block.Bytes)
	if err != nil {
		return nil, fmt.Errorf("failed to parse private key: %w", err)
	}

	edPriv, ok := priv.(ed25519.PrivateKey)
	if !ok {
		return nil, fmt.Errorf("key is not an Ed25519 private key")
	}

	return edPriv, nil
}

// loadPrivateKey loads an Ed25519 private key from PEM file
func loadPrivateKey(path string) (ed25519.PrivateKey, error) {
	keyData, err := ioutil.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("failed to read private key file: %w", err)
	}

	return parsePrivateKey(keyData)
}

// GenerateToken generates a JWT token for outbound requests
func (a *JWTAuth) GenerateToken(targetAudience string) (string, error) {
	if a.privateKey == nil {
		return "", fmt.Errorf("private key not loaded, cannot generate tokens")
	}

	if targetAudience == "" {
		targetAudience = a.audience
	}

	now := time.Now()
	claims := Claims{
		RegisteredClaims: jwt.RegisteredClaims{
			Issuer:    a.issuer,
			Audience:  jwt.ClaimStrings{targetAudience},
			IssuedAt:  jwt.NewNumericDate(now),
			ExpiresAt: jwt.NewNumericDate(now.Add(time.Duration(a.tokenTTL) * time.Second)),
			ID:        uuid.New().String(),
		},
	}

	token := jwt.NewWithClaims(jwt.SigningMethodEdDSA, claims)
	tokenString, err := token.SignedString(a.privateKey)
	if err != nil {
		return "", fmt.Errorf("failed to sign token: %w", err)
	}

	log.WithFields(log.Fields{
		"iss": claims.Issuer,
		"aud": targetAudience,
		"jti": claims.ID,
	}).Debug("Generated JWT token")

	return tokenString, nil
}

// VerifyToken verifies a JWT token
func (a *JWTAuth) VerifyToken(tokenString string, allowedIssuers []string) (*Claims, error) {
	if a.publicKey == nil {
		return nil, fmt.Errorf("public key not loaded, cannot verify tokens")
	}

	// Parse token
	token, err := jwt.ParseWithClaims(tokenString, &Claims{}, func(token *jwt.Token) (interface{}, error) {
		// Verify signing method
		if _, ok := token.Method.(*jwt.SigningMethodEd25519); !ok {
			return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
		}
		return a.publicKey, nil
	})

	if err != nil {
		return nil, fmt.Errorf("failed to parse token: %w", err)
	}

	if !token.Valid {
		return nil, fmt.Errorf("invalid token")
	}

	claims, ok := token.Claims.(*Claims)
	if !ok {
		return nil, fmt.Errorf("invalid claims type")
	}

	// Verify audience manually
	audienceValid := false
	for _, aud := range claims.Audience {
		if aud == a.audience {
			audienceValid = true
			break
		}
	}
	if !audienceValid {
		return nil, fmt.Errorf("invalid audience: expected %s, got %v", a.audience, claims.Audience)
	}

	// Verify expiration manually
	if claims.ExpiresAt != nil && time.Now().After(claims.ExpiresAt.Time) {
		return nil, fmt.Errorf("token expired")
	}

	// Verify issuer if specified
	if len(allowedIssuers) > 0 {
		validIssuer := false
		for _, allowed := range allowedIssuers {
			if claims.Issuer == allowed {
				validIssuer = true
				break
			}
		}
		if !validIssuer {
			return nil, fmt.Errorf("invalid issuer: %s not in allowed list", claims.Issuer)
		}
	}

	log.WithFields(log.Fields{
		"iss": claims.Issuer,
		"jti": claims.ID,
	}).Debug("Verified JWT token")

	return claims, nil
}

// Middleware creates a Gin middleware for JWT authentication
func (a *JWTAuth) Middleware(allowedIssuers []string) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Extract token from Authorization header
		authHeader := c.GetHeader("Authorization")
		if authHeader == "" {
			log.WithFields(log.Fields{
				"ip":     c.ClientIP(),
				"path":   c.Request.URL.Path,
				"method": c.Request.Method,
			}).Warn("Missing Authorization header")

			c.JSON(http.StatusUnauthorized, gin.H{
				"error":   "Unauthorized",
				"message": "Missing or invalid Authorization header",
			})
			c.Abort()
			return
		}

		// Check Bearer prefix
		if !strings.HasPrefix(authHeader, "Bearer ") {
			log.WithFields(log.Fields{
				"ip":     c.ClientIP(),
				"path":   c.Request.URL.Path,
				"method": c.Request.Method,
			}).Warn("Invalid Authorization header format")

			c.JSON(http.StatusUnauthorized, gin.H{
				"error":   "Unauthorized",
				"message": "Invalid Authorization header format",
			})
			c.Abort()
			return
		}

		// Extract token
		tokenString := strings.TrimPrefix(authHeader, "Bearer ")

		// Verify token
		claims, err := a.VerifyToken(tokenString, allowedIssuers)
		if err != nil {
			log.WithFields(log.Fields{
				"ip":     c.ClientIP(),
				"path":   c.Request.URL.Path,
				"method": c.Request.Method,
				"error":  err.Error(),
			}).Warn("JWT verification failed")

			c.JSON(http.StatusUnauthorized, gin.H{
				"error":   "Unauthorized",
				"message": fmt.Sprintf("Invalid token: %s", err.Error()),
			})
			c.Abort()
			return
		}

		// Attach claims to context
		c.Set("jwt_claims", claims)
		c.Set("jwt_issuer", claims.Issuer)

		c.Next()
	}
}
