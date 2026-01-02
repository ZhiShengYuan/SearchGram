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
	// Core identifiers
	ID        string `json:"id"`         // Composite key: {chat_id}-{message_id}
	MessageID int64  `json:"message_id"` // Original message ID
	ChatID    int64  `json:"chat_id"`    // Chat ID (for filtering)
	Timestamp int64  `json:"timestamp"`  // Unix timestamp (for sorting)
	Date      int64  `json:"date"`       // Unix timestamp (backward compat)

	// Chat information (searchable)
	ChatType     string `json:"chat_type"`               // PRIVATE, GROUP, SUPERGROUP, CHANNEL, BOT
	ChatTitle    string `json:"chat_title,omitempty"`    // Chat title
	ChatUsername string `json:"chat_username,omitempty"` // Chat username

	// Sender information (normalized, searchable)
	SenderType      string  `json:"sender_type"`                 // "user" or "chat"
	SenderID        int64   `json:"sender_id"`                   // User ID or sender chat ID
	SenderName      string  `json:"sender_name,omitempty"`       // Combined name or chat title
	SenderUsername  string  `json:"sender_username,omitempty"`   // Username (user or chat)
	SenderFirstName *string `json:"sender_first_name,omitempty"` // First name (user only)
	SenderLastName  *string `json:"sender_last_name,omitempty"`  // Last name (user only)
	SenderChatTitle *string `json:"sender_chat_title,omitempty"` // Chat title (chat sender only)

	// Forward information
	IsForwarded      bool    `json:"is_forwarded"`                  // Whether message is forwarded
	ForwardFromType  *string `json:"forward_from_type,omitempty"`   // "user", "chat", "name_only"
	ForwardFromID    *int64  `json:"forward_from_id,omitempty"`     // Forwarded from user/chat ID
	ForwardFromName  *string `json:"forward_from_name,omitempty"`   // Forwarded from name
	ForwardTimestamp *int64  `json:"forward_timestamp,omitempty"`   // Forward date

	// Content information
	ContentType    string  `json:"content_type"`               // "text", "sticker", "photo", "video", "document", "other"
	Text           string  `json:"text,omitempty"`             // Message text
	Caption        *string `json:"caption,omitempty"`          // Media caption
	StickerEmoji   *string `json:"sticker_emoji,omitempty"`    // Sticker emoji
	StickerSetName *string `json:"sticker_set_name,omitempty"` // Sticker set name

	// Entities (unchanged)
	Entities []MessageEntity `json:"entities,omitempty"` // Message entities (mentions, hashtags, etc.)

	// Soft-delete (unchanged)
	IsDeleted bool  `json:"is_deleted"`         // Soft-delete flag
	DeletedAt int64 `json:"deleted_at,omitempty"` // Deletion timestamp

	// Backward compatibility (deprecated, will be removed later)
	Chat     Chat `json:"chat"`      // Old nested chat object
	FromUser User `json:"from_user"` // Old nested user object

	// Full message (stored, not indexed)
	RawMessage map[string]interface{} `json:"raw_message,omitempty"` // Complete Pyrogram message JSON
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

// CleanCommandsResponse represents the result of a clean commands operation
type CleanCommandsResponse struct {
	Success      bool   `json:"success"`
	DeletedCount int64  `json:"deleted_count"`
	Message      string `json:"message,omitempty"`
}

// GetMessageIDsRequest represents a request to get all message IDs for a chat
type GetMessageIDsRequest struct {
	ChatID int64 `json:"chat_id"` // Chat ID to query
}

// GetMessageIDsResponse represents the list of message IDs in the index
type GetMessageIDsResponse struct {
	ChatID     int64   `json:"chat_id"`      // Chat ID
	MessageIDs []int64 `json:"message_ids"`  // List of message IDs (sorted)
	Count      int64   `json:"count"`        // Total count
}
