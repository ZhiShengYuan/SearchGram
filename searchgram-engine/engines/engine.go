package engines

import "github.com/zhishengyuan/searchgram-engine/models"

// SearchEngine defines the interface for all search engine implementations
type SearchEngine interface {
	// Upsert indexes or updates a message
	Upsert(message *models.Message) error

	// UpsertBatch indexes or updates multiple messages in a single operation
	UpsertBatch(messages []models.Message) (int, []string, error)

	// Search performs a search query
	Search(req *models.SearchRequest) (*models.SearchResponse, error)

	// Delete removes messages by chat ID
	Delete(chatID int64) (int64, error)

	// DeleteUser removes all messages from a specific user
	DeleteUser(userID int64) (int64, error)

	// Clear removes all documents from the index
	Clear() error

	// Ping checks the health and returns stats
	Ping() (*models.PingResponse, error)

	// Stats returns detailed statistics
	Stats() (*models.StatsResponse, error)

	// Dedup removes duplicate messages (keeps latest by timestamp)
	Dedup() (*models.DedupResponse, error)

	// Close closes the connection to the search engine
	Close() error
}
