"""
קובץ constants לניהול כל הסטטוסים במערכת
"""

# סטטוסים ראשיים
STATUS_RECEIVED = "received"
STATUS_EXTRACTING = "extracting"
STATUS_WAITING_BOT_INTERVIEW = "waiting_bot_interview"
STATUS_BOT_INTERVIEW = "bot_interview"

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

