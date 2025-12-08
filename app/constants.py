"""
Constants module - backward compatibility wrapper
This module re-exports constants from app.core.constants for backward compatibility
New code should import directly from app.core.constants
"""
# Re-export all constants from core.constants for backward compatibility
from app.core.constants import (
    STATUS_SUBMITTED,
    STATUS_EXTRACTING,
    STATUS_WAITING_BOT_INTERVIEW,
    STATUS_BOT_INTERVIEW,
    STATUS_READY_FOR_RECRUIT,
    STATUS_WAITING_CLASSIFICATION,
    STATUS_IN_CLASSIFICATION,
    STATUS_ID_MAP,
    STATUS_TO_ID_MAP,
    STATUS_PROCESSING_SUCCESS,
    STATUS_PROCESSING_FAILED,
    STATUS_PROCESSING_ERROR,
    STATUS_WEBHOOK_PREFIX,
    STATUS_WEBHOOK_ERROR,
    DocumentStatus,
    get_status_by_id,
    get_all_statuses,
    get_processing_error_status,
    get_webhook_status,
    get_webhook_error_status,
)

