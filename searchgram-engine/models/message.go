package models

// Chat represents a Telegram chat
type Chat struct {
	ID       int64  `json:"id"`
	Type     string `json:"type"`
	Title    string `json:"title,omitempty"`
	Username string `json:"username,omitempty"`
}

// User represents a Telegram user
type User struct {
	ID        int64  `json:"id"`
	IsBot     bool   `json:"is_bot,omitempty"`
	FirstName string `json:"first_name,omitempty"`
	LastName  string `json:"last_name,omitempty"`
	Username  string `json:"username,omitempty"`
}

// MessageEntity represents a Telegram message entity (mention, hashtag, etc.)
type MessageEntity struct {
	Type   string `json:"type"`             // Entity type (mention, text_mention, hashtag, etc.)
	Offset int    `json:"offset,omitempty"` // Offset in UTF-16 code units
	Length int    `json:"length,omitempty"` // Length in UTF-16 code units
	UserID *int64 `json:"user_id,omitempty"` // User ID for text_mention type
	User   *User  `json:"user,omitempty"`    // User object for text_mention type
}

// Message represents a Telegram message
type Message struct {
	ID        string          `json:"id"`          // Composite key: {chat_id}-{message_id}
	MessageID int64           `json:"message_id"`  // Original message ID
	Text      string          `json:"text"`        // Message text
	Chat      Chat            `json:"chat"`        // Chat information
	FromUser  User            `json:"from_user"`   // Sender information
	Date      int64           `json:"date"`        // Unix timestamp
	Timestamp int64           `json:"timestamp"`   // Unix timestamp (for sorting)
	Entities  []MessageEntity `json:"entities,omitempty"` // Message entities (mentions, hashtags, etc.)
	IsDeleted bool            `json:"is_deleted"`         // Soft-delete flag
	DeletedAt int64           `json:"deleted_at,omitempty"` // Deletion timestamp
}

// SearchRequest represents a search query
type SearchRequest struct {
	Keyword        string  `json:"keyword"`                 // Search keyword
	ChatType       string  `json:"chat_type,omitempty"`     // Filter by chat type
	Username       string  `json:"username,omitempty"`      // Filter by username
	ChatID         *int64  `json:"chat_id,omitempty"`       // Filter by chat ID (for group searches)
	Page           int     `json:"page"`                    // Page number (1-based)
	PageSize       int     `json:"page_size"`               // Results per page
	ExactMatch     bool    `json:"exact_match"`             // Exact vs fuzzy matching
	BlockedUsers   []int64 `json:"blocked_users,omitempty"` // User IDs to exclude
	IncludeDeleted bool    `json:"include_deleted"`         // Include soft-deleted messages (owner only)
}

// SearchResponse represents search results
type SearchResponse struct {
	Hits        []Message `json:"hits"`          // Search results
	TotalHits   int64     `json:"total_hits"`    // Total matching documents
	TotalPages  int       `json:"total_pages"`   // Total pages
	Page        int       `json:"page"`          // Current page
	HitsPerPage int       `json:"hits_per_page"` // Results per page
	TookMs      int64     `json:"took_ms"`       // Server-side timing in milliseconds
}

// UpsertResponse represents the result of an upsert operation
type UpsertResponse struct {
	Success bool   `json:"success"`
	ID      string `json:"id"`
}

// DeleteResponse represents the result of a delete operation
type DeleteResponse struct {
	Success      bool  `json:"success"`
	DeletedCount int64 `json:"deleted_count"`
}

// ClearResponse represents the result of a clear operation
type ClearResponse struct {
	Success bool   `json:"success"`
	Message string `json:"message"`
}

// PingResponse represents health check information
type PingResponse struct {
	Status         string `json:"status"`
	Engine         string `json:"engine"`
	Version        string `json:"version,omitempty"`
	TotalDocuments int64  `json:"total_documents"`
	UptimeSeconds  int64  `json:"uptime_seconds"`
}

// StatsResponse represents statistics
type StatsResponse struct {
	TotalDocuments     int64   `json:"total_documents"`
	TotalChats         int64   `json:"total_chats"`
	TotalUsers         int64   `json:"total_users"`
	IndexSizeBytes     int64   `json:"index_size_bytes"`
	RequestsTotal      int64   `json:"requests_total"`
	RequestsPerMinute  float64 `json:"requests_per_minute"`
}

// BatchUpsertRequest represents a batch upsert request
type BatchUpsertRequest struct {
	Messages []Message `json:"messages"`
}

// BatchUpsertResponse represents the result of a batch upsert operation
type BatchUpsertResponse struct {
	Success      bool     `json:"success"`
	IndexedCount int      `json:"indexed_count"`
	FailedCount  int      `json:"failed_count"`
	Errors       []string `json:"errors,omitempty"`
}

// ErrorResponse represents an error response
type ErrorResponse struct {
	Error   string `json:"error"`
	Message string `json:"message,omitempty"`
	Code    int    `json:"code,omitempty"`
}

// DedupResponse represents the result of a deduplication operation
type DedupResponse struct {
	Success           bool   `json:"success"`
	DuplicatesFound   int64  `json:"duplicates_found"`
	DuplicatesRemoved int64  `json:"duplicates_removed"`
	Message           string `json:"message,omitempty"`
}

// UserStatsRequest represents a user stats query
type UserStatsRequest struct {
	GroupID         int64  `json:"group_id"`                   // Group/chat ID to query
	UserID          int64  `json:"user_id"`                    // User ID to get stats for
	FromTimestamp   int64  `json:"from_timestamp"`             // Start of time window
	ToTimestamp     int64  `json:"to_timestamp"`               // End of time window
	IncludeMentions bool   `json:"include_mentions"`           // Whether to count mentions
	IncludeDeleted  bool   `json:"include_deleted"`            // Include deleted messages (owner only)
}

// UserStatsResponse represents user activity statistics
type UserStatsResponse struct {
	UserMessageCount  int64   `json:"user_message_count"`  // Messages sent by user
	GroupMessageTotal int64   `json:"group_message_total"` // Total messages in group (time window)
	UserRatio         float64 `json:"user_ratio"`          // user_count / group_total
	MentionsOut       int64   `json:"mentions_out"`        // User mentioned others (outgoing)
	MentionsIn        int64   `json:"mentions_in"`         // User was mentioned (incoming)
}
