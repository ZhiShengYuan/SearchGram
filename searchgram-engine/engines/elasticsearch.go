package engines

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/olivere/elastic/v7"
	log "github.com/sirupsen/logrus"
	"github.com/zhishengyuan/searchgram-engine/models"
)

const (
	defaultIndex = "telegram"
	defaultShards = 3
	defaultReplicas = 1
)

// ElasticsearchEngine implements SearchEngine for Elasticsearch
type ElasticsearchEngine struct {
	client    *elastic.Client
	index     string
	startTime time.Time
}

// NewElasticsearch creates a new Elasticsearch search engine
func NewElasticsearch(host, username, password, index string, shards, replicas int) (*ElasticsearchEngine, error) {
	if index == "" {
		index = defaultIndex
	}
	if shards == 0 {
		shards = defaultShards
	}
	if replicas == 0 {
		replicas = defaultReplicas
	}

	// Create Elasticsearch client
	options := []elastic.ClientOptionFunc{
		elastic.SetURL(host),
		elastic.SetSniff(false),
		elastic.SetHealthcheck(true),
		elastic.SetHealthcheckInterval(30 * time.Second),
	}

	if username != "" && password != "" {
		options = append(options, elastic.SetBasicAuth(username, password))
	}

	client, err := elastic.NewClient(options...)
	if err != nil {
		return nil, fmt.Errorf("failed to create Elasticsearch client: %w", err)
	}

	engine := &ElasticsearchEngine{
		client:    client,
		index:     index,
		startTime: time.Now(),
	}

	// Initialize index with proper mappings
	if err := engine.initializeIndex(shards, replicas); err != nil {
		return nil, fmt.Errorf("failed to initialize index: %w", err)
	}

	log.WithFields(log.Fields{
		"host":  host,
		"index": index,
	}).Info("Elasticsearch engine initialized")

	return engine, nil
}

// initializeIndex creates the index with CJK-optimized settings
func (e *ElasticsearchEngine) initializeIndex(shards, replicas int) error {
	ctx := context.Background()

	// Check if index exists
	exists, err := e.client.IndexExists(e.index).Do(ctx)
	if err != nil {
		return fmt.Errorf("failed to check index existence: %w", err)
	}

	if exists {
		log.WithField("index", e.index).Info("Index already exists")
		return nil
	}

	// Create index with CJK-optimized settings
	indexSettings := map[string]interface{}{
		"settings": map[string]interface{}{
			"number_of_shards":   shards,
			"number_of_replicas": replicas,
			"analysis": map[string]interface{}{
				"analyzer": map[string]interface{}{
					"cjk_analyzer": map[string]interface{}{
						"type":      "custom",
						"tokenizer": "standard",
						"filter":    []string{"cjk_width", "lowercase", "cjk_bigram"},
					},
					"exact_analyzer": map[string]interface{}{
						"type":      "custom",
						"tokenizer": "keyword",
						"filter":    []string{"lowercase"},
					},
				},
			},
		},
		"mappings": map[string]interface{}{
			"properties": map[string]interface{}{
				"id": map[string]interface{}{
					"type": "keyword",
				},
				"message_id": map[string]interface{}{
					"type": "long",
				},
				"text": map[string]interface{}{
					"type":     "text",
					"analyzer": "cjk_analyzer",
					"fields": map[string]interface{}{
						"exact": map[string]interface{}{
							"type":     "text",
							"analyzer": "exact_analyzer",
						},
					},
				},
				"chat": map[string]interface{}{
					"properties": map[string]interface{}{
						"id": map[string]interface{}{
							"type": "long",
						},
						"type": map[string]interface{}{
							"type": "keyword",
						},
						"title": map[string]interface{}{
							"type":     "text",
							"analyzer": "cjk_analyzer",
						},
						"username": map[string]interface{}{
							"type": "keyword",
						},
					},
				},
				"from_user": map[string]interface{}{
					"properties": map[string]interface{}{
						"id": map[string]interface{}{
							"type": "long",
						},
						"is_bot": map[string]interface{}{
							"type": "boolean",
						},
						"first_name": map[string]interface{}{
							"type":     "text",
							"analyzer": "cjk_analyzer",
						},
						"last_name": map[string]interface{}{
							"type":     "text",
							"analyzer": "cjk_analyzer",
						},
						"username": map[string]interface{}{
							"type": "keyword",
						},
					},
				},
				"date": map[string]interface{}{
					"type": "long",
				},
				"timestamp": map[string]interface{}{
					"type": "long",
				},
			},
		},
	}

	_, err = e.client.CreateIndex(e.index).BodyJson(indexSettings).Do(ctx)
	if err != nil {
		return fmt.Errorf("failed to create index: %w", err)
	}

	log.WithField("index", e.index).Info("Created index with CJK optimization")
	return nil
}

// Upsert indexes or updates a message
func (e *ElasticsearchEngine) Upsert(message *models.Message) error {
	ctx := context.Background()

	_, err := e.client.Index().
		Index(e.index).
		Id(message.ID).
		BodyJson(message).
		Do(ctx)

	if err != nil {
		return fmt.Errorf("failed to upsert document: %w", err)
	}

	return nil
}

// UpsertBatch indexes or updates multiple messages using the Bulk API
func (e *ElasticsearchEngine) UpsertBatch(messages []models.Message) (int, []string, error) {
	ctx := context.Background()

	if len(messages) == 0 {
		return 0, nil, nil
	}

	// Create bulk request
	bulkRequest := e.client.Bulk().Index(e.index)

	// Add all messages to bulk request
	for i := range messages {
		req := elastic.NewBulkIndexRequest().
			Id(messages[i].ID).
			Doc(&messages[i])
		bulkRequest.Add(req)
	}

	// Execute bulk request
	bulkResponse, err := bulkRequest.Do(ctx)
	if err != nil {
		return 0, nil, fmt.Errorf("failed to execute bulk upsert: %w", err)
	}

	// Process results
	var errors []string
	indexed := 0
	failed := 0

	// Check for individual item errors
	if bulkResponse.Errors {
		for _, item := range bulkResponse.Items {
			for action, result := range item {
				if result.Error != nil {
					failed++
					errorMsg := fmt.Sprintf("Document %s failed (%s): %s",
						result.Id, action, result.Error.Reason)
					errors = append(errors, errorMsg)
					log.WithField("document_id", result.Id).Warn(errorMsg)
				} else {
					indexed++
				}
			}
		}
	} else {
		// All documents indexed successfully
		indexed = len(messages)
	}

	log.WithFields(log.Fields{
		"total":   len(messages),
		"indexed": indexed,
		"failed":  failed,
	}).Info("Bulk upsert completed")

	return indexed, errors, nil
}

// Search performs a search query
func (e *ElasticsearchEngine) Search(req *models.SearchRequest) (*models.SearchResponse, error) {
	ctx := context.Background()

	// Build the query
	boolQuery := elastic.NewBoolQuery()

	// Text search query (fuzzy or exact)
	if req.Keyword != "" {
		if req.ExactMatch {
			// Exact match using match_phrase
			matchQuery := elastic.NewMatchPhraseQuery("text.exact", req.Keyword)
			boolQuery.Must(matchQuery)
		} else {
			// Fuzzy match using standard analyzer
			matchQuery := elastic.NewMatchQuery("text", req.Keyword).Fuzziness("AUTO")
			boolQuery.Must(matchQuery)
		}
	}

	// Filter by chat type
	if req.ChatType != "" {
		chatTypeFilter := elastic.NewTermQuery("chat.type", strings.ToUpper(req.ChatType))
		boolQuery.Filter(chatTypeFilter)
	}

	// Filter by username
	if req.Username != "" {
		// Try to parse as user ID
		usernameQuery := elastic.NewBoolQuery()
		usernameQuery.Should(elastic.NewTermQuery("chat.username", req.Username))
		usernameQuery.Should(elastic.NewTermQuery("from_user.username", req.Username))
		boolQuery.Filter(usernameQuery)
	}

	// Filter by chat ID (for group-specific searches)
	if req.ChatID != nil {
		chatIDFilter := elastic.NewTermQuery("chat.id", *req.ChatID)
		boolQuery.Filter(chatIDFilter)
	}

	// Exclude blocked users
	if len(req.BlockedUsers) > 0 {
		for _, userID := range req.BlockedUsers {
			boolQuery.MustNot(elastic.NewTermQuery("from_user.id", userID))
		}
	}

	// Pagination
	if req.Page < 1 {
		req.Page = 1
	}
	if req.PageSize < 1 {
		req.PageSize = 10
	}
	from := (req.Page - 1) * req.PageSize

	// Execute search
	searchResult, err := e.client.Search().
		Index(e.index).
		Query(boolQuery).
		Sort("timestamp", false). // Sort by timestamp descending
		From(from).
		Size(req.PageSize).
		TrackTotalHits(true).
		Do(ctx)

	if err != nil {
		return nil, fmt.Errorf("search query failed: %w", err)
	}

	// Parse results
	var messages []models.Message
	for _, hit := range searchResult.Hits.Hits {
		var msg models.Message
		if err := json.Unmarshal(hit.Source, &msg); err != nil {
			log.WithError(err).Warn("Failed to unmarshal search result")
			continue
		}
		messages = append(messages, msg)
	}

	totalHits := searchResult.Hits.TotalHits.Value
	totalPages := int((totalHits + int64(req.PageSize) - 1) / int64(req.PageSize))

	return &models.SearchResponse{
		Hits:        messages,
		TotalHits:   totalHits,
		TotalPages:  totalPages,
		Page:        req.Page,
		HitsPerPage: req.PageSize,
	}, nil
}

// Delete removes messages by chat ID
func (e *ElasticsearchEngine) Delete(chatID int64) (int64, error) {
	ctx := context.Background()

	query := elastic.NewTermQuery("chat.id", chatID)

	result, err := e.client.DeleteByQuery().
		Index(e.index).
		Query(query).
		Do(ctx)

	if err != nil {
		return 0, fmt.Errorf("failed to delete by chat ID: %w", err)
	}

	return result.Deleted, nil
}

// DeleteUser removes all messages from a specific user
func (e *ElasticsearchEngine) DeleteUser(userID int64) (int64, error) {
	ctx := context.Background()

	query := elastic.NewTermQuery("from_user.id", userID)

	result, err := e.client.DeleteByQuery().
		Index(e.index).
		Query(query).
		Do(ctx)

	if err != nil {
		return 0, fmt.Errorf("failed to delete by user ID: %w", err)
	}

	return result.Deleted, nil
}

// Clear removes all documents from the index
func (e *ElasticsearchEngine) Clear() error {
	ctx := context.Background()

	query := elastic.NewMatchAllQuery()

	_, err := e.client.DeleteByQuery().
		Index(e.index).
		Query(query).
		Do(ctx)

	if err != nil {
		return fmt.Errorf("failed to clear index: %w", err)
	}

	log.WithField("index", e.index).Info("Cleared all documents")
	return nil
}

// Ping checks the health and returns stats
func (e *ElasticsearchEngine) Ping() (*models.PingResponse, error) {
	ctx := context.Background()

	// Get ES info (includes version and health)
	info, code, err := e.client.Ping(e.client.String()).Do(ctx)
	if err != nil || code != 200 {
		return &models.PingResponse{
			Status: "error",
			Engine: "elasticsearch",
		}, err
	}

	// Get document count
	count, err := e.client.Count(e.index).Do(ctx)
	if err != nil {
		count = 0
	}

	// Extract version
	version := ""
	if info != nil {
		version = info.Version.Number
	}

	return &models.PingResponse{
		Status:         "ok",
		Engine:         "elasticsearch",
		Version:        version,
		TotalDocuments: count,
		UptimeSeconds:  int64(time.Since(e.startTime).Seconds()),
	}, nil
}

// Stats returns detailed statistics
func (e *ElasticsearchEngine) Stats() (*models.StatsResponse, error) {
	ctx := context.Background()

	// Total documents
	totalDocs, err := e.client.Count(e.index).Do(ctx)
	if err != nil {
		totalDocs = 0
	}

	// Unique chats count (aggregation)
	chatsAgg := elastic.NewCardinalityAggregation().Field("chat.id")
	chatsResult, err := e.client.Search().
		Index(e.index).
		Size(0).
		Aggregation("unique_chats", chatsAgg).
		Do(ctx)

	var totalChats int64 = 0
	if err == nil {
		if agg, found := chatsResult.Aggregations.Cardinality("unique_chats"); found {
			totalChats = int64(*agg.Value)
		}
	}

	// Unique users count (aggregation)
	usersAgg := elastic.NewCardinalityAggregation().Field("from_user.id")
	usersResult, err := e.client.Search().
		Index(e.index).
		Size(0).
		Aggregation("unique_users", usersAgg).
		Do(ctx)

	var totalUsers int64 = 0
	if err == nil {
		if agg, found := usersResult.Aggregations.Cardinality("unique_users"); found {
			totalUsers = int64(*agg.Value)
		}
	}

	// Get index stats
	indexStats, err := e.client.IndexStats(e.index).Do(ctx)
	var indexSize int64 = 0
	if err == nil {
		if stats, found := indexStats.Indices[e.index]; found {
			indexSize = stats.Total.Store.SizeInBytes
		}
	}

	return &models.StatsResponse{
		TotalDocuments:    totalDocs,
		TotalChats:        totalChats,
		TotalUsers:        totalUsers,
		IndexSizeBytes:    indexSize,
		RequestsTotal:     0, // TODO: Implement request counter
		RequestsPerMinute: 0, // TODO: Implement request rate tracking
	}, nil
}

// Dedup removes duplicate messages (keeps latest by timestamp)
func (e *ElasticsearchEngine) Dedup() (*models.DedupResponse, error) {
	ctx := context.Background()

	log.Info("Starting deduplication process...")

	// Use aggregations to find duplicates by chat_id + message_id
	compositeAgg := elastic.NewCompositeAggregation().
		Size(1000).
		Sources(
			elastic.NewCompositeAggregationTermsValuesSource("chat_id").Field("chat.id"),
			elastic.NewCompositeAggregationTermsValuesSource("message_id").Field("message_id"),
		)

	topHitsAgg := elastic.NewTopHitsAggregation().
		Size(100).
		Sort("timestamp", false) // Sort by timestamp descending

	compositeAgg.SubAggregation("docs", topHitsAgg)

	var duplicatesFound int64 = 0
	var duplicatesRemoved int64 = 0
	var afterKey map[string]interface{} = nil

	// Process all composite aggregation pages
	for {
		if afterKey != nil {
			compositeAgg.AggregateAfter(afterKey)
		}

		searchResult, err := e.client.Search().
			Index(e.index).
			Size(0).
			Aggregation("duplicates", compositeAgg).
			Do(ctx)

		if err != nil {
			return nil, fmt.Errorf("failed to search for duplicates: %w", err)
		}

		// Parse composite aggregation
		compAgg, found := searchResult.Aggregations.Composite("duplicates")
		if !found {
			break
		}

		// Process each bucket (unique chat_id + message_id combination)
		for _, bucket := range compAgg.Buckets {
			// Get top hits for this bucket
			topHits, found := bucket.Aggregations.TopHits("docs")
			if !found || topHits == nil || topHits.Hits == nil {
				continue
			}

			hitCount := len(topHits.Hits.Hits)
			if hitCount <= 1 {
				// No duplicates for this message
				continue
			}

			// Found duplicates! Keep the first one (latest timestamp), delete the rest
			duplicatesFound += int64(hitCount - 1)

			// Collect document IDs to delete (skip the first one)
			bulkDelete := e.client.Bulk().Index(e.index)
			for i := 1; i < hitCount; i++ {
				docID := topHits.Hits.Hits[i].Id
				deleteReq := elastic.NewBulkDeleteRequest().Id(docID)
				bulkDelete.Add(deleteReq)
			}

			// Execute bulk delete
			if bulkDelete.NumberOfActions() > 0 {
				bulkResp, err := bulkDelete.Do(ctx)
				if err != nil {
					log.WithError(err).Warn("Failed to delete duplicate documents")
					continue
				}

				if !bulkResp.Errors {
					duplicatesRemoved += int64(bulkDelete.NumberOfActions())
				} else {
					// Count successful deletions
					for _, item := range bulkResp.Items {
						for _, result := range item {
							if result.Error == nil {
								duplicatesRemoved++
							}
						}
					}
				}
			}
		}

		// Check if there are more pages
		if compAgg.AfterKey == nil || len(compAgg.Buckets) == 0 {
			break
		}
		afterKey = compAgg.AfterKey
	}

	message := fmt.Sprintf("Deduplication complete: found %d duplicates, removed %d", duplicatesFound, duplicatesRemoved)
	log.Info(message)

	return &models.DedupResponse{
		Success:           true,
		DuplicatesFound:   duplicatesFound,
		DuplicatesRemoved: duplicatesRemoved,
		Message:           message,
	}, nil
}

// Close closes the connection to Elasticsearch
func (e *ElasticsearchEngine) Close() error {
	e.client.Stop()
	log.Info("Elasticsearch connection closed")
	return nil
}
