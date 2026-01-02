"""
Mirror Manager

Manages channel mirroring tasks on userbot side:
- Monitors source channels for new messages
- Downloads media files
- Sends to bot for processing via HTTP API
"""

import logging
import os
import tempfile
from typing import Dict, List, Optional
from pyrogram import Client, filters
from pyrogram.types import Message
from .mirror_models import MirrorTask, MirrorMessage, MediaType
from .mirror_http_client import MirrorHTTPClient
from .config_loader import get_config

logger = logging.getLogger(__name__)


class MirrorManager:
    """
    Manages mirror tasks on userbot side.

    Monitors source channels and sends messages to bot for mirroring.
    """

    def __init__(self, bot_api_base_url: Optional[str] = None):
        """
        Initialize mirror manager.

        Args:
            bot_api_base_url: Bot API base URL (default from config)
        """
        self.tasks: Dict[str, MirrorTask] = {}
        self.source_channel_map: Dict[int, str] = {}  # source_chat_id -> task_id

        # Load configuration
        config = get_config()

        # Bot API URL
        if not bot_api_base_url:
            bot_api_base_url = config.get("services.bot.base_url", "http://127.0.0.1:8081")

        # HTTP client for sending to bot
        self.http_client = MirrorHTTPClient(base_url=bot_api_base_url)

        # Check if mirror is enabled
        self.enabled = config.get_bool("mirror.enabled", False)

        # Load tasks from config
        if self.enabled:
            self._load_tasks_from_config()

        logger.info(f"MirrorManager initialized with {len(self.tasks)} tasks (enabled: {self.enabled})")

    def _load_tasks_from_config(self):
        """Load mirror tasks from configuration."""
        config = get_config()
        task_configs = config.get("mirror.tasks", [])

        for task_config in task_configs:
            try:
                task = MirrorTask.from_dict(task_config)
                self.add_task(task)
                logger.info(f"Loaded mirror task: {task.id} ({task.source_channel} → {task.target_channel})")
            except Exception as e:
                logger.error(f"Failed to load mirror task: {e}", exc_info=True)

    def add_task(self, task: MirrorTask):
        """
        Add a mirror task.

        Args:
            task: Mirror task to add
        """
        self.tasks[task.id] = task
        self.source_channel_map[task.source_channel] = task.id
        logger.info(f"Added mirror task: {task.id}")

    def remove_task(self, task_id: str):
        """
        Remove a mirror task.

        Args:
            task_id: Task ID to remove
        """
        task = self.tasks.pop(task_id, None)
        if task:
            self.source_channel_map.pop(task.source_channel, None)
            logger.info(f"Removed mirror task: {task_id}")

    def get_task(self, task_id: str) -> Optional[MirrorTask]:
        """Get task by ID."""
        return self.tasks.get(task_id)

    def get_task_for_channel(self, channel_id: int) -> Optional[MirrorTask]:
        """
        Get task for source channel.

        Args:
            channel_id: Source channel ID

        Returns:
            MirrorTask if found, None otherwise
        """
        task_id = self.source_channel_map.get(channel_id)
        if task_id:
            return self.tasks.get(task_id)
        return None

    def pause_task(self, task_id: str):
        """Pause a mirror task."""
        task = self.tasks.get(task_id)
        if task:
            task.pause()
            logger.info(f"Paused task: {task_id}")

    def resume_task(self, task_id: str):
        """Resume a paused mirror task."""
        task = self.tasks.get(task_id)
        if task:
            task.resume()
            logger.info(f"Resumed task: {task_id}")

    def get_all_tasks(self) -> List[MirrorTask]:
        """Get all mirror tasks."""
        return list(self.tasks.values())

    def get_monitored_channels(self) -> List[int]:
        """Get list of all monitored source channels."""
        return list(self.source_channel_map.keys())

    async def handle_message(self, client: Client, message: Message):
        """
        Handle incoming message from monitored channel.

        This is called by Pyrogram message handler.

        Args:
            client: Pyrogram client
            message: Incoming message
        """
        if not self.enabled:
            return

        # Get task for this channel
        task = self.get_task_for_channel(message.chat.id)
        if not task or not task.is_active():
            return

        try:
            # Process message
            await self._process_message(client, message, task)

        except Exception as e:
            logger.error(f"Error handling mirror message: {e}", exc_info=True)
            task.update_stats("failed", error=str(e))

    async def _process_message(self, client: Client, message: Message, task: MirrorTask):
        """
        Process and send message for mirroring.

        Args:
            client: Pyrogram client
            message: Source message
            task: Mirror task
        """
        logger.debug(f"Processing message {message.id} from {message.chat.id} for task {task.id}")

        # Check content filters
        if not task.mirror_text and not message.media:
            logger.debug("Message has only text, but mirror_text is disabled")
            return

        if not task.mirror_media and message.media:
            logger.debug("Message has media, but mirror_media is disabled")
            return

        # Extract text content
        text = message.text or message.caption

        # Download media if present
        file_bytes = None
        media_type = None
        file_size = None
        file_name = None

        if message.media and task.mirror_media:
            try:
                media_type = self._get_media_type(message)
                file_size = self._get_file_size(message)

                # Download media
                logger.info(f"Downloading media ({media_type}, {file_size} bytes)...")
                temp_path = await client.download_media(message)

                if temp_path:
                    # Read file
                    with open(temp_path, 'rb') as f:
                        file_bytes = f.read()

                    # Get filename
                    file_name = os.path.basename(temp_path)
                    if hasattr(message, media_type):
                        media_obj = getattr(message, media_type)
                        if hasattr(media_obj, 'file_name') and media_obj.file_name:
                            file_name = media_obj.file_name

                    # Clean up temp file
                    try:
                        os.remove(temp_path)
                    except:
                        pass

                    logger.info(f"Downloaded media: {file_name} ({len(file_bytes)} bytes)")

            except Exception as e:
                logger.error(f"Failed to download media: {e}", exc_info=True)
                # Continue without media if download fails
                file_bytes = None

        # Create mirror message
        mirror_message = MirrorMessage(
            task_id=task.id,
            source_chat_id=message.chat.id,
            source_msg_id=message.id,
            text=text,
            caption=message.caption if message.media else None,
            has_media=file_bytes is not None,
            media_type=media_type,
            file_size=len(file_bytes) if file_bytes else None,
            file_name=file_name,
            file_data=file_bytes
        )

        # Send to bot for processing
        try:
            logger.info(f"Sending message to bot for mirroring (task: {task.id})")
            result = self.http_client.send_for_mirroring(mirror_message)

            status = result.get("status")
            if status == "success":
                logger.info(f"Message mirrored successfully: {result}")
            elif status == "skipped":
                logger.info(f"Message skipped: {result.get('reason')}")
            else:
                logger.warning(f"Mirror failed: {result}")

        except Exception as e:
            logger.error(f"Failed to send message to bot: {e}", exc_info=True)

    def _get_media_type(self, message: Message) -> Optional[str]:
        """Get media type from message."""
        if message.photo:
            return MediaType.PHOTO
        elif message.video:
            return MediaType.VIDEO
        elif message.document:
            return MediaType.DOCUMENT
        elif message.animation:
            return MediaType.ANIMATION
        elif message.voice:
            return MediaType.VOICE
        elif message.video_note:
            return MediaType.VIDEO_NOTE
        elif message.sticker:
            return MediaType.STICKER
        elif message.audio:
            return MediaType.AUDIO
        return None

    def _get_file_size(self, message: Message) -> Optional[int]:
        """Get file size from message."""
        if message.photo:
            # Get largest photo size
            return max((p.file_size for p in message.photo.thumbs if hasattr(p, 'file_size')), default=0)
        elif message.video:
            return message.video.file_size
        elif message.document:
            return message.document.file_size
        elif message.animation:
            return message.animation.file_size
        elif message.voice:
            return message.voice.file_size
        elif message.video_note:
            return message.video_note.file_size
        elif message.audio:
            return message.audio.file_size
        return None

    def get_stats(self) -> Dict:
        """
        Get statistics for all mirror tasks.

        Returns:
            Dict with aggregated statistics
        """
        total_processed = 0
        total_mirrored = 0
        total_filtered = 0
        total_failed = 0
        active_tasks = 0
        paused_tasks = 0

        for task in self.tasks.values():
            total_processed += task.total_processed
            total_mirrored += task.total_mirrored
            total_filtered += task.total_filtered
            total_failed += task.total_failed

            if task.status == "active":
                active_tasks += 1
            elif task.status == "paused":
                paused_tasks += 1

        return {
            "total_tasks": len(self.tasks),
            "active_tasks": active_tasks,
            "paused_tasks": paused_tasks,
            "total_processed": total_processed,
            "total_mirrored": total_mirrored,
            "total_filtered": total_filtered,
            "total_failed": total_failed,
        }

    def close(self):
        """Clean up resources."""
        if self.http_client:
            self.http_client.close()


def create_mirror_filter():
    """
    Create Pyrogram filter for mirror handler.

    Returns:
        Pyrogram filter that matches monitored channels
    """
    def filter_func(_, __, message: Message):
        # This will be set dynamically when handler is registered
        return True

    return filters.create(filter_func)


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    manager = MirrorManager()

    print(f"Mirror enabled: {manager.enabled}")
    print(f"Loaded tasks: {len(manager.tasks)}")

    for task in manager.get_all_tasks():
        print(f"  - {task.id}: {task.source_channel} → {task.target_channel}")
        print(f"    LLM: {task.llm_enabled} ({task.llm_mode})")
        print(f"    Keywords: whitelist={len(task.keyword_whitelist)}, blacklist={len(task.keyword_blacklist)}")

    stats = manager.get_stats()
    print(f"\nStatistics: {stats}")

    manager.close()
