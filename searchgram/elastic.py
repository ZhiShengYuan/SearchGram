#!/usr/local/bin/python3
# coding: utf-8

# SearchGram - elastic.py
# Elasticsearch implementation for SearchGram
# Optimized for CJK (Chinese, Japanese, Korean) text search

__author__ = "Benny <benny.think@gmail.com>"

import logging
import math

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError

from config import ELASTIC_HOST, ELASTIC_USER, ELASTIC_PASS
from engine import BasicSearchEngine
from utils import sizeof_fmt


class SearchEngine(BasicSearchEngine):
    """
    Elasticsearch-based search engine with CJK optimization.

    Features:
    - CJK bigram tokenization for improved Asian language search
    - Mixed analyzer for multilingual content
    - Timestamp-based sorting for recency
    - Filterable chat metadata (type, username, ID)
    - Efficient bulk operations and pagination
    """

    def __init__(self):
        try:
            # Initialize Elasticsearch client with authentication
            self.client = Elasticsearch(
                [ELASTIC_HOST],
                basic_auth=(ELASTIC_USER, ELASTIC_PASS),
                request_timeout=30,
                max_retries=3,
                retry_on_timeout=True
            )

            self.index_name = "telegram"

            # Create index with CJK-optimized settings if it doesn't exist
            if not self.client.indices.exists(index=self.index_name):
                self._create_index()

            # Verify connection
            if not self.client.ping():
                raise ConnectionError("Failed to ping Elasticsearch")

            logging.info("Successfully connected to Elasticsearch at %s", ELASTIC_HOST)

        except Exception as e:
            logging.critical("Failed to connect to Elasticsearch: %s", e)
            raise

    def _create_index(self):
        """
        Create the Telegram index with CJK-optimized settings.

        Uses a custom analyzer combining:
        - CJK bigram tokenization for Chinese/Japanese/Korean
        - Standard tokenization for other languages
        - Lowercase normalization
        - CJK width normalization (full-width to half-width)
        """
        index_settings = {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,  # Adjust based on your needs
                "analysis": {
                    "analyzer": {
                        "cjk_analyzer": {
                            "type": "custom",
                            "tokenizer": "standard",
                            "filter": [
                                "cjk_width",
                                "lowercase",
                                "cjk_bigram"
                            ]
                        },
                        "exact_analyzer": {
                            "type": "custom",
                            "tokenizer": "keyword",
                            "filter": ["lowercase"]
                        }
                    }
                },
                "index": {
                    "max_result_window": 10000  # Allow deep pagination if needed
                }
            },
            "mappings": {
                "properties": {
                    "ID": {
                        "type": "keyword"  # Primary key: {chat_id}-{message_id}
                    },
                    "text": {
                        "type": "text",
                        "analyzer": "cjk_analyzer",  # CJK-optimized for fuzzy search
                        "fields": {
                            "exact": {
                                "type": "text",
                                "analyzer": "exact_analyzer"  # For exact matching
                            },
                            "keyword": {
                                "type": "keyword",
                                "ignore_above": 256
                            }
                        }
                    },
                    "timestamp": {
                        "type": "long"  # Unix timestamp for sorting
                    },
                    "date": {
                        "type": "date",
                        "format": "yyyy-MM-dd HH:mm:ss||epoch_second"
                    },
                    "chat": {
                        "properties": {
                            "id": {
                                "type": "long"
                            },
                            "username": {
                                "type": "keyword"
                            },
                            "type": {
                                "type": "keyword"  # ChatType.PRIVATE, GROUP, etc.
                            },
                            "first_name": {
                                "type": "text",
                                "analyzer": "cjk_analyzer"
                            },
                            "title": {
                                "type": "text",
                                "analyzer": "cjk_analyzer"
                            }
                        }
                    },
                    "from_user": {
                        "properties": {
                            "id": {
                                "type": "long"
                            },
                            "username": {
                                "type": "keyword"
                            },
                            "first_name": {
                                "type": "text",
                                "analyzer": "cjk_analyzer"
                            }
                        }
                    }
                }
            }
        }

        self.client.indices.create(index=self.index_name, body=index_settings)
        logging.info("Created Elasticsearch index '%s' with CJK optimization", self.index_name)

    def upsert(self, message):
        """
        Index or update a message in Elasticsearch.

        Args:
            message: Pyrogram message object
        """
        if self.check_ignore(message):
            return

        data = self.set_uid(message)

        try:
            # Use the ID as document ID for idempotent upserts
            self.client.index(
                index=self.index_name,
                id=data["ID"],
                document=data,
                refresh=False  # Don't force refresh for better performance
            )
        except Exception as e:
            logging.error("Failed to index message %s: %s", data.get("ID"), e)

    def search(self, keyword, _type=None, user=None, page=1, mode=None) -> dict:
        """
        Search messages with optional filters.

        Args:
            keyword: Search term
            _type: Chat type filter (BOT, CHANNEL, GROUP, PRIVATE, SUPERGROUP)
            user: Username or user ID filter
            page: Page number (1-indexed)
            mode: If set, use exact match search

        Returns:
            dict: Search results with hits, totalHits, totalPages, page, hitsPerPage
        """
        # Build the query
        must_clauses = []
        filter_clauses = []

        # Keyword search - use exact or fuzzy matching
        if keyword:
            if mode:
                # Exact match using the exact analyzer field
                must_clauses.append({
                    "match_phrase": {
                        "text.exact": keyword
                    }
                })
            else:
                # Fuzzy match using CJK analyzer
                must_clauses.append({
                    "match": {
                        "text": {
                            "query": keyword,
                            "operator": "and"  # All terms must match
                        }
                    }
                })

        # Chat type filter
        if _type:
            filter_clauses.append({
                "term": {"chat.type": f"ChatType.{_type}"}
            })

        # User filter (by username or ID)
        user = self.clean_user(user)
        if user:
            user_filter = {
                "bool": {
                    "should": [
                        {"term": {"chat.username": user}},
                        {"term": {"chat.id": user}}
                    ],
                    "minimum_should_match": 1
                }
            }
            filter_clauses.append(user_filter)

        # Build the final query
        query = {
            "bool": {
                "must": must_clauses if must_clauses else [{"match_all": {}}],
                "filter": filter_clauses
            }
        }

        # Pagination
        hits_per_page = 10
        from_offset = (page - 1) * hits_per_page

        # Execute search
        try:
            response = self.client.search(
                index=self.index_name,
                query=query,
                sort=[{"timestamp": {"order": "desc"}}],  # Sort by newest first
                from_=from_offset,
                size=hits_per_page,
                track_total_hits=True
            )

            total_hits = response["hits"]["total"]["value"]
            total_pages = math.ceil(total_hits / hits_per_page)

            # Extract documents from search results
            hits = [hit["_source"] for hit in response["hits"]["hits"]]

            return {
                "hits": hits,
                "query": keyword,
                "processingTimeMs": response["took"],
                "hitsPerPage": hits_per_page,
                "page": page,
                "totalPages": total_pages,
                "totalHits": total_hits,
            }

        except Exception as e:
            logging.error("Search failed: %s", e)
            return {
                "hits": [],
                "query": keyword,
                "processingTimeMs": 0,
                "hitsPerPage": hits_per_page,
                "page": page,
                "totalPages": 0,
                "totalHits": 0,
            }

    def ping(self) -> str:
        """
        Check Elasticsearch health and return statistics.

        Returns:
            str: Status message with document count and index size
        """
        try:
            # Get cluster health
            health = self.client.cluster.health()

            # Get index stats
            stats = self.client.indices.stats(index=self.index_name)

            # Extract metrics
            doc_count = stats["indices"][self.index_name]["total"]["docs"]["count"]
            store_size = stats["indices"][self.index_name]["total"]["store"]["size_in_bytes"]

            text = f"Pong! Elasticsearch is {health['status']}\n"
            text += f"Index {self.index_name} has {doc_count} documents\n"
            text += f"Index size: {sizeof_fmt(store_size)}\n"
            text += f"Cluster: {health['cluster_name']}\n"
            text += f"Nodes: {health['number_of_nodes']}\n"

            return text

        except Exception as e:
            logging.error("Ping failed: %s", e)
            return f"Failed to ping Elasticsearch: {e}"

    def clear_db(self):
        """
        Delete the entire Telegram index.

        Warning: This is irreversible!
        """
        try:
            self.client.indices.delete(index=self.index_name)
            logging.info("Deleted index '%s'", self.index_name)
            # Recreate the index with proper settings
            self._create_index()
        except NotFoundError:
            logging.warning("Index '%s' not found, nothing to delete", self.index_name)
        except Exception as e:
            logging.error("Failed to clear database: %s", e)

    def delete_user(self, user):
        """
        Delete all messages from a specific user/chat.

        Args:
            user: Username or user ID to delete
        """
        user = self.clean_user(user)

        # Build delete query
        query = {
            "bool": {
                "should": [
                    {"term": {"chat.username": user}},
                    {"term": {"chat.id": user}}
                ],
                "minimum_should_match": 1
            }
        }

        try:
            response = self.client.delete_by_query(
                index=self.index_name,
                query=query,
                refresh=True  # Make changes immediately visible
            )

            deleted_count = response.get("deleted", 0)
            logging.info("Deleted %d messages from user %s", deleted_count, user)

        except Exception as e:
            logging.error("Failed to delete user %s: %s", user, e)


if __name__ == "__main__":
    # Quick test
    search = SearchEngine()
    print(search.ping())
