"""
קובץ constants לניהול כל הסטטוסים במערכת
"""
from enum import Enum

# סטטוסים ראשיים
STATUS_RECEIVED = "Received"
STATUS_EXTRACTING = "Extracting"
STATUS_WAITING_BOT_INTERVIEW = "Waiting Bot Interview"
STATUS_BOT_INTERVIEW = "Bot Interview"
STATUS_READY_FOR_RECRUIT = "Ready For Recruit"
STATUS_WAITING_CLASSIFICATION = "Waiting Classification"
STATUS_IN_CLASSIFICATION = "In Classification"

# מיפוי ID לסטטוס
STATUS_ID_MAP = {
    1: STATUS_RECEIVED,
    2: STATUS_EXTRACTING,
    3: STATUS_WAITING_BOT_INTERVIEW,
    4: STATUS_BOT_INTERVIEW,
    5: STATUS_WAITING_CLASSIFICATION,
    6: STATUS_IN_CLASSIFICATION,
    7: STATUS_READY_FOR_RECRUIT,
}

# מיפוי סטטוס ל-ID (reverse mapping)
STATUS_TO_ID_MAP = {v: k for k, v in STATUS_ID_MAP.items()}

def get_status_by_id(status_id: int) -> str:
    """מחזיר את שם הסטטוס לפי ID"""
    return STATUS_ID_MAP.get(status_id)

def get_all_statuses() -> list:
    """מחזיר רשימה של כל הסטטוסים הזמינים עם ID שלהם"""
    return [
        {"id": status_id, "name": status_name}
        for status_id, status_name in STATUS_ID_MAP.items()
    ]

class DocumentStatus(str, Enum):
    """Enum לסטטוסים תקפים של מסמכים"""
    RECEIVED = STATUS_RECEIVED
    EXTRACTING = STATUS_EXTRACTING
    WAITING_BOT_INTERVIEW = STATUS_WAITING_BOT_INTERVIEW
    BOT_INTERVIEW = STATUS_BOT_INTERVIEW
    READY_FOR_RECRUIT = STATUS_READY_FOR_RECRUIT
    WAITING_CLASSIFICATION = STATUS_WAITING_CLASSIFICATION
    IN_CLASSIFICATION = STATUS_IN_CLASSIFICATION

# סטטוסי processing
STATUS_PROCESSING_SUCCESS = "processing_success"
STATUS_PROCESSING_FAILED = "processing_failed"
STATUS_PROCESSING_ERROR = "processing_error"  # עם הוספת error message

# סטטוסי webhook
STATUS_WEBHOOK_PREFIX = "webhook_status"  # עם הוספת status_code
STATUS_WEBHOOK_ERROR = "webhook_error"  # עם הוספת error message

# פונקציות עזר ליצירת סטטוסים דינמיים
def get_processing_error_status(error_message: str) -> str:
    """מחזיר סטטוס processing_error עם הודעת שגיאה"""
    return f"{STATUS_PROCESSING_ERROR}: {error_message[:100]}"

def get_webhook_status(status_code: int, status_text: str = None) -> str:
    """מחזיר סטטוס webhook עם status code ואופציונלית status text"""
    status = f"{STATUS_WEBHOOK_PREFIX}_{status_code}"
    if status_text:
        status += f": {status_text[:100]}"
    return status

def get_webhook_error_status(error_message: str) -> str:
    """מחזיר סטטוס webhook_error עם הודעת שגיאה"""
    return f"{STATUS_WEBHOOK_ERROR}: {error_message[:100]}"

