"""
Application-wide constants
This file centralizes all status constants and related mappings
"""
from enum import Enum

# Main statuses
STATUS_SUBMITTED = "Submitted"
STATUS_EXTRACTING = "Extracting"
STATUS_WAITING_BOT_INTERVIEW = "Waiting Bot Interview"
STATUS_BOT_INTERVIEW = "Bot Interview"
STATUS_READY_FOR_RECRUIT = "Ready For Recruit"
STATUS_WAITING_CLASSIFICATION = "Waiting Classification"
STATUS_IN_CLASSIFICATION = "In Classification"

# Status ID mapping
STATUS_ID_MAP = {
    1: STATUS_SUBMITTED,
    2: STATUS_EXTRACTING,
    3: STATUS_WAITING_BOT_INTERVIEW,
    4: STATUS_BOT_INTERVIEW,
    5: STATUS_WAITING_CLASSIFICATION,
    6: STATUS_IN_CLASSIFICATION,
    7: STATUS_READY_FOR_RECRUIT,
}

# Reverse mapping (status name to ID)
STATUS_TO_ID_MAP = {v: k for k, v in STATUS_ID_MAP.items()}


def get_status_by_id(status_id: int) -> str:
    """
    Get status name by ID
    
    Args:
        status_id: The status ID (1-7)
        
    Returns:
        Status name string or None if not found
    """
    return STATUS_ID_MAP.get(status_id)


def get_all_statuses() -> list:
    """
    Get all available statuses with their IDs
    
    Returns:
        List of dictionaries with 'id' and 'name' keys
    """
    return [
        {"id": status_id, "name": status_name}
        for status_id, status_name in STATUS_ID_MAP.items()
    ]


class DocumentStatus(str, Enum):
    """Enum for valid document statuses"""
    SUBMITTED = STATUS_SUBMITTED
    EXTRACTING = STATUS_EXTRACTING
    WAITING_BOT_INTERVIEW = STATUS_WAITING_BOT_INTERVIEW
    BOT_INTERVIEW = STATUS_BOT_INTERVIEW
    READY_FOR_RECRUIT = STATUS_READY_FOR_RECRUIT
    WAITING_CLASSIFICATION = STATUS_WAITING_CLASSIFICATION
    IN_CLASSIFICATION = STATUS_IN_CLASSIFICATION


# Processing statuses
STATUS_PROCESSING_SUCCESS = "processing_success"
STATUS_PROCESSING_FAILED = "processing_failed"
STATUS_PROCESSING_ERROR = "processing_error"  # With error message appended

# Webhook statuses
STATUS_WEBHOOK_PREFIX = "webhook_status"  # With status code appended
STATUS_WEBHOOK_ERROR = "webhook_error"  # With error message appended


def get_processing_error_status(error_message: str) -> str:
    """
    Create a processing error status with error message
    
    Args:
        error_message: The error message (truncated to 100 chars)
        
    Returns:
        Status string in format: "processing_error: {error_message[:100]}"
    """
    from app.core.config import ERROR_MESSAGE_MAX_LENGTH
    return f"{STATUS_PROCESSING_ERROR}: {error_message[:ERROR_MESSAGE_MAX_LENGTH]}"


def get_webhook_status(status_code: int, status_text: str = None) -> str:
    """
    Create a webhook status with status code and optional status text
    
    Args:
        status_code: HTTP status code
        status_text: Optional response text (truncated to 100 chars)
        
    Returns:
        Status string in format: "webhook_status_{status_code}" or 
        "webhook_status_{status_code}: {status_text[:100]}"
    """
    from app.core.config import ERROR_MESSAGE_MAX_LENGTH
    status = f"{STATUS_WEBHOOK_PREFIX}_{status_code}"
    if status_text:
        status += f": {status_text[:ERROR_MESSAGE_MAX_LENGTH]}"
    return status


def get_webhook_error_status(error_message: str) -> str:
    """
    Create a webhook error status with error message
    
    Args:
        error_message: The error message (truncated to 100 chars)
        
    Returns:
        Status string in format: "webhook_error: {error_message[:100]}"
    """
    from app.core.config import ERROR_MESSAGE_MAX_LENGTH
    return f"{STATUS_WEBHOOK_ERROR}: {error_message[:ERROR_MESSAGE_MAX_LENGTH]}"

