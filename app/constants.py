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

