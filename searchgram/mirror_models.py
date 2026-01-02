"""
Data Models for Channel Mirroring

Defines data structures for mirror tasks, logs, and configurations.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from enum import Enum
import time


class MirrorStatus(str, Enum):
    """Mirror task status."""
    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    FAILED = "failed"


class LLMMode(str, Enum):
    """LLM processing mode."""
    REWRITE = "rewrite"
    FILTER = "filter"
    CATEGORIZE = "categorize"
    DISABLED = "disabled"


class MediaType(str, Enum):
    """Supported media types."""
    PHOTO = "photo"
    VIDEO = "video"
    DOCUMENT = "document"
    ANIMATION = "animation"
    VOICE = "voice"
    VIDEO_NOTE = "video_note"
    STICKER = "sticker"
    AUDIO = "audio"


class ProcessingAction(str, Enum):
    """Processing action taken on message."""
    MIRRORED = "mirrored"
    REWRITTEN = "rewritten"
    CATEGORIZED = "categorized"
    FILTERED_LLM = "filtered_llm"
    FILTERED_KEYWORD = "filtered_keyword"
    SKIPPED_NO_CONTENT = "skipped_no_content"
    FAILED = "failed"


@dataclass
class MirrorTask:
    """
    Configuration for a single mirror task.

    Represents a source → target channel mapping with processing rules.
    """
    id: str
    source_channel: int
    target_channel: int

    # Content options
    mirror_media: bool = True
    mirror_text: bool = True
    forward_mode: bool = False  # True = forward, False = copy

    # LLM processing
    llm_enabled: bool = False
    llm_mode: str = LLMMode.DISABLED
    llm_temperature: float = 0.7
    llm_max_tokens: Optional[int] = None
    llm_custom_prompt: Optional[str] = None

    # Keyword filtering
    keyword_whitelist: List[str] = field(default_factory=list)
    keyword_blacklist: List[str] = field(default_factory=list)
    keyword_case_sensitive: bool = False
    keyword_use_regex: bool = False

    # Task state
    status: str = MirrorStatus.ACTIVE
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # Statistics
    total_processed: int = 0
    total_mirrored: int = 0
    total_filtered: int = 0
    total_failed: int = 0
    last_message_time: Optional[float] = None
    last_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MirrorTask":
        """Create from dictionary."""
        # Handle default values for new fields
        return cls(**{
            k: v for k, v in data.items()
            if k in cls.__dataclass_fields__
        })

    def update_stats(
        self,
        action: ProcessingAction,
        error: Optional[str] = None
    ):
        """
        Update task statistics.

        Args:
            action: Processing action taken
            error: Error message if failed
        """
        self.total_processed += 1
        self.last_message_time = time.time()
        self.updated_at = time.time()

        if action in (ProcessingAction.MIRRORED, ProcessingAction.REWRITTEN,
                      ProcessingAction.CATEGORIZED):
            self.total_mirrored += 1
        elif action in (ProcessingAction.FILTERED_LLM, ProcessingAction.FILTERED_KEYWORD):
            self.total_filtered += 1
        elif action == ProcessingAction.FAILED:
            self.total_failed += 1
            self.last_error = error

    def is_active(self) -> bool:
        """Check if task is active."""
        return self.status == MirrorStatus.ACTIVE

    def pause(self):
        """Pause task."""
        self.status = MirrorStatus.PAUSED
        self.updated_at = time.time()

    def resume(self):
        """Resume task."""
        self.status = MirrorStatus.ACTIVE
        self.updated_at = time.time()

    def mark_failed(self, error: str):
        """Mark task as failed."""
        self.status = MirrorStatus.FAILED
        self.last_error = error
        self.updated_at = time.time()


@dataclass
class MirrorLog:
    """
    Log entry for a mirrored message.

    Stored in SQLite database for tracking and analytics.
    """
    task_id: str
    source_chat_id: int
    source_msg_id: int

    # Target information
    target_chat_id: int
    target_msg_id: Optional[int] = None

    # Content information
    has_media: bool = False
    media_type: Optional[str] = None
    text_length: int = 0

    # Processing information
    llm_action: Optional[str] = None
    keyword_match: Optional[str] = None  # Matched keyword (if any)
    processing_action: str = ProcessingAction.MIRRORED

    # Result
    status: str = "success"  # "success", "failed", "skipped"
    error_message: Optional[str] = None

    # Timing
    timestamp: float = field(default_factory=time.time)
    processing_time_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MirrorLog":
        """Create from dictionary."""
        return cls(**{
            k: v for k, v in data.items()
            if k in cls.__dataclass_fields__
        })


@dataclass
class MirrorMessage:
    """
    Message data sent from userbot to bot for mirroring.

    Transmitted via HTTP API.
    """
    task_id: str
    source_chat_id: int
    source_msg_id: int

    # Content
    text: Optional[str] = None
    caption: Optional[str] = None

    # Media information
    has_media: bool = False
    media_type: Optional[str] = None
    file_size: Optional[int] = None
    file_name: Optional[str] = None

    # File data (base64-encoded when transmitted)
    file_data: Optional[bytes] = None

    # Metadata
    timestamp: float = field(default_factory=time.time)

    def to_api_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for HTTP API transmission.

        File data should be base64-encoded by the caller.
        """
        import base64

        data = {
            "task_id": self.task_id,
            "source_chat_id": self.source_chat_id,
            "source_msg_id": self.source_msg_id,
            "text": self.text,
            "caption": self.caption,
            "has_media": self.has_media,
            "media_type": self.media_type,
            "file_size": self.file_size,
            "file_name": self.file_name,
            "timestamp": self.timestamp,
        }

        # Encode file data if present
        if self.file_data:
            data["file_data"] = base64.b64encode(self.file_data).decode("utf-8")

        return data

    @classmethod
    def from_api_dict(cls, data: Dict[str, Any]) -> "MirrorMessage":
        """
        Create from HTTP API dictionary.

        File data should be base64-decoded by the caller.
        """
        import base64

        # Decode file data if present
        file_data = None
        if data.get("file_data"):
            file_data = base64.b64decode(data["file_data"])

        return cls(
            task_id=data["task_id"],
            source_chat_id=data["source_chat_id"],
            source_msg_id=data["source_msg_id"],
            text=data.get("text"),
            caption=data.get("caption"),
            has_media=data.get("has_media", False),
            media_type=data.get("media_type"),
            file_size=data.get("file_size"),
            file_name=data.get("file_name"),
            file_data=file_data,
            timestamp=data.get("timestamp", time.time()),
        )

    def get_content_text(self) -> Optional[str]:
        """Get text content (prefer caption for media, otherwise text)."""
        return self.caption or self.text

    def has_content(self) -> bool:
        """Check if message has any content."""
        return bool(self.text or self.caption or self.has_media)


# Example usage
if __name__ == "__main__":
    # Example 1: Create a mirror task
    task = MirrorTask(
        id="task_1",
        source_channel=-1001234567890,
        target_channel=-1009876543210,
        mirror_media=True,
        mirror_text=True,
        llm_enabled=True,
        llm_mode=LLMMode.REWRITE,
        keyword_whitelist=["crypto", "bitcoin"],
        keyword_blacklist=["scam"]
    )

    print("=== Mirror Task ===")
    print(f"Task ID: {task.id}")
    print(f"Source: {task.source_channel}")
    print(f"Target: {task.target_channel}")
    print(f"LLM Mode: {task.llm_mode}")
    print(f"Status: {task.status}")

    # Update stats
    task.update_stats(ProcessingAction.MIRRORED)
    task.update_stats(ProcessingAction.FILTERED_KEYWORD)
    print(f"\nStats: {task.total_processed} processed, {task.total_mirrored} mirrored, "
          f"{task.total_filtered} filtered")

    # Example 2: Create a mirror log entry
    log = MirrorLog(
        task_id="task_1",
        source_chat_id=-1001234567890,
        source_msg_id=12345,
        target_chat_id=-1009876543210,
        target_msg_id=67890,
        has_media=True,
        media_type=MediaType.PHOTO,
        text_length=150,
        llm_action=LLMMode.REWRITE,
        processing_action=ProcessingAction.REWRITTEN,
        processing_time_ms=1250
    )

    print("\n=== Mirror Log ===")
    print(f"Task: {log.task_id}")
    print(f"Source: {log.source_chat_id}/{log.source_msg_id}")
    print(f"Target: {log.target_chat_id}/{log.target_msg_id}")
    print(f"Action: {log.processing_action}")
    print(f"Processing time: {log.processing_time_ms}ms")

    # Example 3: Create a mirror message for API transmission
    message = MirrorMessage(
        task_id="task_1",
        source_chat_id=-1001234567890,
        source_msg_id=12345,
        text="Bitcoin price is up!",
        has_media=True,
        media_type=MediaType.PHOTO,
        file_data=b"\x89PNG\r\n\x1a\n...",  # Example PNG header
        file_size=1024000,
        file_name="chart.png"
    )

    print("\n=== Mirror Message ===")
    print(f"Task: {message.task_id}")
    print(f"Text: {message.get_content_text()}")
    print(f"Has media: {message.has_media} ({message.media_type})")
    print(f"File size: {message.file_size} bytes")

    # Convert to API dict (would be sent via HTTP)
    api_dict = message.to_api_dict()
    print(f"API dict keys: {list(api_dict.keys())}")
    print(f"File data encoded: {len(api_dict.get('file_data', ''))} chars")
