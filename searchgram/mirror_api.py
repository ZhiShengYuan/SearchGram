"""
Mirror API

Flask HTTP API for mirror operations on bot side.
Receives messages from userbot and processes them for mirroring.

Note: Endpoints are registered on the bot_api Flask app, not a separate app.
"""

import logging
import time
from typing import Optional
from flask import request, jsonify
from .jwt_auth import require_jwt_auth
from .mirror_models import (
    MirrorMessage, MirrorLog, MirrorTask, ProcessingAction, MediaType
)
from .llm_client import LLMClient
from .keyword_filter import KeywordFilter
from .local_bot_api_client import LocalBotAPIClient
from .db_manager import DatabaseManager
from .config_loader import get_config
from io import BytesIO

logger = logging.getLogger(__name__)

# Global state (set by parent process via init_mirror_api)
_mirror_tasks = {}  # task_id -> MirrorTask
_bot_client = None  # Pyrogram bot client
_local_bot_api = None  # Local Bot API client
_llm_client = None  # LLM client
_db_manager = None  # Database manager
_jwt_auth = None  # JWT authentication


def init_mirror_api(
    flask_app,
    tasks: dict,
    bot_client,
    db_manager: DatabaseManager
):
    """
    Initialize mirror API and register endpoints on Flask app.

    Args:
        flask_app: Flask app instance (from bot_api)
        tasks: Dict of task_id -> MirrorTask
        bot_client: Pyrogram bot client instance
        db_manager: Database manager instance
    """
    global _mirror_tasks, _bot_client, _local_bot_api, _llm_client, _db_manager, _jwt_auth

    _mirror_tasks = tasks
    _bot_client = bot_client
    _db_manager = db_manager

    # Load configuration
    config = get_config()

    # Initialize Local Bot API client (if configured)
    local_bot_api_url = config.get("services.local_bot_api.base_url")
    bot_token = config.get("telegram.bot_token") or config.get("telegram.token")

    if local_bot_api_url and bot_token:
        try:
            _local_bot_api = LocalBotAPIClient(
                base_url=local_bot_api_url,
                token=bot_token
            )
            if _local_bot_api.test_connection():
                logger.info("Local Bot API client initialized")
            else:
                logger.warning("Local Bot API connection test failed, will use Pyrogram")
                _local_bot_api = None
        except Exception as e:
            logger.error(f"Failed to initialize Local Bot API client: {e}")
            _local_bot_api = None
    else:
        logger.info("Local Bot API not configured, will use Pyrogram for uploads")

    # Initialize LLM client (if configured)
    llm_config = config.get("services.llm", {})
    if llm_config.get("base_url") and llm_config.get("api_key"):
        try:
            _llm_client = LLMClient(
                base_url=llm_config["base_url"],
                api_key=llm_config["api_key"],
                model=llm_config.get("model", "gpt-3.5-turbo"),
                timeout=llm_config.get("timeout", 30)
            )
            if _llm_client.test_connection():
                logger.info("LLM client initialized")
            else:
                logger.warning("LLM connection test failed")
                _llm_client = None
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}")
            _llm_client = None
    else:
        logger.info("LLM not configured, LLM features will be disabled")

    # JWT auth is loaded by Flask app startup
    from .jwt_utils import load_jwt_auth_from_config
    _jwt_auth = load_jwt_auth_from_config(issuer="bot")

    # Register mirror endpoints on the Flask app
    _register_endpoints(flask_app)

    logger.info("Mirror API initialized and endpoints registered")


def _register_endpoints(flask_app):
    """Register mirror API endpoints on the Flask app."""

    # Register all endpoints defined below
    flask_app.add_url_rule(
        '/api/v1/mirror/process',
        'mirror_process',
        process_mirror,
        methods=['POST']
    )
    flask_app.add_url_rule(
        '/api/v1/mirror/task/<task_id>',
        'mirror_task_status',
        get_task_status,
        methods=['GET']
    )
    flask_app.add_url_rule(
        '/api/v1/mirror/pause',
        'mirror_pause',
        pause_task,
        methods=['POST']
    )
    flask_app.add_url_rule(
        '/api/v1/mirror/resume',
        'mirror_resume',
        resume_task,
        methods=['POST']
    )


@require_jwt_auth(allowed_issuers=["userbot"])
def process_mirror():
    """
    Process a message for mirroring.

    Expected JSON payload:
    {
        "task_id": "task_1",
        "source_chat_id": -1001234567890,
        "source_msg_id": 12345,
        "text": "...",
        "caption": "...",
        "has_media": true,
        "media_type": "photo",
        "file_data": "base64...",
        "file_size": 1024,
        "file_name": "image.jpg",
        "timestamp": 1234567890.123
    }

    Returns:
    {
        "status": "success" | "skipped" | "failed",
        "reason": "...",
        "target_msg_id": 123,
        "processing_time_ms": 1234
    }
    """
    start_time = time.time()

    try:
        # Parse request
        data = request.get_json()
        if not data:
            return jsonify({"status": "failed", "reason": "invalid_json"}), 400

        # Parse message
        try:
            message = MirrorMessage.from_api_dict(data)
        except Exception as e:
            logger.error(f"Failed to parse mirror message: {e}")
            return jsonify({"status": "failed", "reason": "invalid_message"}), 400

        # Get task
        task = _mirror_tasks.get(message.task_id)
        if not task:
            logger.warning(f"Unknown task ID: {message.task_id}")
            return jsonify({"status": "failed", "reason": "unknown_task"}), 404

        # Check if task is active
        if not task.is_active():
            logger.info(f"Task {message.task_id} is not active (status: {task.status})")
            return jsonify({"status": "skipped", "reason": "task_not_active"})

        # Check content
        if not message.has_content():
            logger.info("Message has no content, skipping")
            _log_mirror(message, task, ProcessingAction.SKIPPED_NO_CONTENT, None)
            task.update_stats(ProcessingAction.SKIPPED_NO_CONTENT)
            return jsonify({"status": "skipped", "reason": "no_content"})

        # Get content text for filtering/processing
        content_text = message.get_content_text()

        # Apply keyword filter
        if content_text and (task.keyword_whitelist or task.keyword_blacklist):
            keyword_filter = KeywordFilter(
                whitelist=task.keyword_whitelist,
                blacklist=task.keyword_blacklist,
                case_sensitive=task.keyword_case_sensitive,
                use_regex=task.keyword_use_regex
            )

            filter_result = keyword_filter.check(content_text)
            if not filter_result.should_mirror:
                logger.info(f"Message filtered by keywords: {filter_result.reason}")
                _log_mirror(
                    message, task, ProcessingAction.FILTERED_KEYWORD, None,
                    keyword_match=str(filter_result.matched_keywords)
                )
                task.update_stats(ProcessingAction.FILTERED_KEYWORD)
                return jsonify({
                    "status": "skipped",
                    "reason": "keyword_filter",
                    "matched_keywords": filter_result.matched_keywords
                })

        # Apply LLM processing
        processed_text = content_text
        llm_action = None

        if task.llm_enabled and _llm_client and content_text:
            try:
                processed_text = _llm_client.process(
                    text=content_text,
                    mode=task.llm_mode,
                    temperature=task.llm_temperature,
                    max_tokens=task.llm_max_tokens,
                    custom_prompt=task.llm_custom_prompt
                )

                if processed_text is None:
                    # LLM filtered out the message
                    logger.info("Message filtered by LLM")
                    _log_mirror(message, task, ProcessingAction.FILTERED_LLM, None, llm_action=task.llm_mode)
                    task.update_stats(ProcessingAction.FILTERED_LLM)
                    return jsonify({"status": "skipped", "reason": "llm_filter"})

                llm_action = task.llm_mode
                logger.info(f"LLM processed text (mode: {task.llm_mode})")

            except Exception as e:
                logger.error(f"LLM processing failed: {e}", exc_info=True)
                # Fallback to original text on LLM failure
                processed_text = content_text
                llm_action = "failed"

        # Upload to target channel
        try:
            target_msg_id = _upload_to_channel(task, message, processed_text)

            # Log success
            processing_action = ProcessingAction.MIRRORED
            if llm_action and llm_action != "failed":
                processing_action = ProcessingAction.REWRITTEN if llm_action == "rewrite" else ProcessingAction.CATEGORIZED

            _log_mirror(
                message, task, processing_action, target_msg_id,
                llm_action=llm_action
            )
            task.update_stats(processing_action)

            processing_time_ms = int((time.time() - start_time) * 1000)
            logger.info(f"Message mirrored successfully to {task.target_channel} (msg_id: {target_msg_id})")

            return jsonify({
                "status": "success",
                "target_msg_id": target_msg_id,
                "processing_time_ms": processing_time_ms
            })

        except Exception as e:
            logger.error(f"Upload to channel failed: {e}", exc_info=True)
            error_msg = str(e)
            _log_mirror(message, task, ProcessingAction.FAILED, None, error=error_msg)
            task.update_stats(ProcessingAction.FAILED, error=error_msg)

            return jsonify({
                "status": "failed",
                "reason": "upload_failed",
                "error": error_msg
            }), 500

    except Exception as e:
        logger.error(f"Mirror processing error: {e}", exc_info=True)
        return jsonify({
            "status": "failed",
            "reason": "internal_error",
            "error": str(e)
        }), 500


def _upload_to_channel(
    task: MirrorTask,
    message: MirrorMessage,
    text: Optional[str]
) -> int:
    """
    Upload message to target channel.

    Args:
        task: Mirror task configuration
        message: Source message
        text: Processed text to send

    Returns:
        Target message ID

    Raises:
        Exception: On upload failure
    """
    target_channel = task.target_channel

    # Prepare file if present
    file_obj = None
    if message.has_media and message.file_data:
        file_obj = BytesIO(message.file_data)
        file_obj.name = message.file_name or "file.bin"

    # Choose upload method: Local Bot API (preferred) or Pyrogram
    if _local_bot_api and message.has_media:
        # Use local Bot API for media uploads (supports large files)
        logger.debug("Using Local Bot API for upload")

        if message.media_type == MediaType.PHOTO:
            result = _local_bot_api.send_photo(
                chat_id=target_channel,
                photo=file_obj,
                caption=text,
                disable_notification=False
            )
        elif message.media_type == MediaType.VIDEO:
            result = _local_bot_api.send_video(
                chat_id=target_channel,
                video=file_obj,
                caption=text,
                disable_notification=False
            )
        else:
            result = _local_bot_api.send_document(
                chat_id=target_channel,
                document=file_obj,
                caption=text,
                filename=message.file_name,
                disable_notification=False
            )

        return result["message_id"]

    else:
        # Use Pyrogram (standard MTProto)
        logger.debug("Using Pyrogram for upload")

        if message.has_media and file_obj:
            if message.media_type == MediaType.PHOTO:
                sent_msg = _bot_client.send_photo(
                    chat_id=target_channel,
                    photo=file_obj,
                    caption=text
                )
            elif message.media_type == MediaType.VIDEO:
                sent_msg = _bot_client.send_video(
                    chat_id=target_channel,
                    video=file_obj,
                    caption=text
                )
            else:
                sent_msg = _bot_client.send_document(
                    chat_id=target_channel,
                    document=file_obj,
                    caption=text,
                    file_name=message.file_name
                )
        else:
            # Text only
            sent_msg = _bot_client.send_message(
                chat_id=target_channel,
                text=text or "(empty message)"
            )

        return sent_msg.id


def _log_mirror(
    message: MirrorMessage,
    task: MirrorTask,
    action: ProcessingAction,
    target_msg_id: Optional[int],
    error: Optional[str] = None,
    llm_action: Optional[str] = None,
    keyword_match: Optional[str] = None
):
    """Log mirror operation to database."""
    if not _db_manager:
        return

    try:
        log = MirrorLog(
            task_id=message.task_id,
            source_chat_id=message.source_chat_id,
            source_msg_id=message.source_msg_id,
            target_chat_id=task.target_channel,
            target_msg_id=target_msg_id,
            has_media=message.has_media,
            media_type=message.media_type,
            text_length=len(message.get_content_text() or ""),
            llm_action=llm_action,
            keyword_match=keyword_match,
            processing_action=action,
            status="success" if target_msg_id else ("skipped" if "SKIP" in action else "failed"),
            error_message=error
        )

        _db_manager.log_mirror(log.to_dict())

    except Exception as e:
        logger.error(f"Failed to log mirror operation: {e}", exc_info=True)


@require_jwt_auth(allowed_issuers=["userbot", "bot"])
def get_task_status(task_id: str):
    """Get status of a mirror task."""
    task = _mirror_tasks.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    return jsonify(task.to_dict())


@require_jwt_auth(allowed_issuers=["userbot", "bot"])
def pause_task():
    """Pause a mirror task."""
    data = request.get_json()
    task_id = data.get("task_id")

    task = _mirror_tasks.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    task.pause()
    logger.info(f"Task {task_id} paused")

    return jsonify({"status": "ok", "task_id": task_id})


@require_jwt_auth(allowed_issuers=["userbot", "bot"])
def resume_task():
    """Resume a paused mirror task."""
    data = request.get_json()
    task_id = data.get("task_id")

    task = _mirror_tasks.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    task.resume()
    logger.info(f"Task {task_id} resumed")

    return jsonify({"status": "ok", "task_id": task_id})
