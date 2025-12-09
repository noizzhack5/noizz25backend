"""
Service for processing records with waiting_classification status
Uses webhook client utility for making HTTP requests
"""
import logging
from typing import Dict
from app.services.storage import get_documents_by_status, add_status_to_history, update_document_status
from app.services.config_loader import get_webhook_url
from app.core.constants import (
    STATUS_READY_FOR_CLASSIFICATION,
    STATUS_IN_CLASSIFICATION,
    get_webhook_status,
    get_webhook_error_status
)
from app.utils.webhook_client import webhook_client

logger = logging.getLogger(__name__)

def get_classification_webhook_url() -> str:
    """מחזיר את ה-URL של classification webhook מהקונפיגורציה"""
    return get_webhook_url("classification_processor")

async def process_waiting_classification_records(db) -> Dict[str, any]:
    """
    מחפש רשומות עם סטטוס waiting_classification ומבצע קריאה ל-webhook עבור כל רשומה
    
    Args:
        db: מסד הנתונים
    
    Returns:
        dict עם סטטיסטיקות על העיבוד
    """
    logger.info(f"[CLASSIFICATION_PROCESSOR] Starting to process {STATUS_READY_FOR_CLASSIFICATION} records")
    
    # קבל את כל הרשומות עם סטטוס waiting_classification
    records = await get_documents_by_status(db, STATUS_READY_FOR_CLASSIFICATION)
    logger.info(f"[CLASSIFICATION_PROCESSOR] Found {len(records)} records with status '{STATUS_READY_FOR_CLASSIFICATION}'")
    
    if not records:
        return {
            "total": 0,
            "success": 0,
            "failed": 0,
            "details": []
        }
    
    results = {
        "total": len(records),
        "success": 0,
        "failed": 0,
        "details": []
    }
    
    # עבד כל רשומה
    for record in records:
        record_id = record.get("id")
        
        # בצע קריאה ל-webhook
        try:
            success = await call_classification_webhook(db, record_id)
            if success:
                results["success"] += 1
                results["details"].append({
                    "id": record_id,
                    "status": "success"
                })
                # עדכן סטטוס ל-STATUS_IN_CLASSIFICATION
                try:
                    await update_document_status(db, record_id, STATUS_IN_CLASSIFICATION)
                    logger.info(f"[CLASSIFICATION_PROCESSOR] Updated record {record_id} status to '{STATUS_IN_CLASSIFICATION}'")
                except Exception as e:
                    logger.error(f"[CLASSIFICATION_PROCESSOR] Failed to update status for record {record_id}: {str(e)}", exc_info=True)
            else:
                results["failed"] += 1
                results["details"].append({
                    "id": record_id,
                    "status": "failed"
                })
        except Exception as e:
            logger.error(f"[CLASSIFICATION_PROCESSOR] Error processing record {record_id}: {str(e)}", exc_info=True)
            results["failed"] += 1
            results["details"].append({
                "id": record_id,
                "status": "error",
                "error": str(e)
            })
    
    logger.info(
        f"[CLASSIFICATION_PROCESSOR] Processing completed. "
        f"Total: {results['total']}, Success: {results['success']}, "
        f"Failed: {results['failed']}"
    )
    
    return results

async def call_classification_webhook(db, record_id: str) -> bool:
    """
    קורא ל-webhook עם ה-ID של הרשומה
    משתמש ב-webhook_client utility לטיפול בקריאות HTTP
    
    Args:
        db: מסד הנתונים
        record_id: מזהה הרשומה
    
    Returns:
        True אם הקריאה הצליחה, False אחרת
    """
    webhook_url = get_classification_webhook_url()
    payload = {
        "id": record_id
    }
    
    # Use webhook client (standard HTTP status code check)
    success, status_code, response_text = await webhook_client.call_webhook(
        url=webhook_url,
        payload=payload,
        webhook_name="classification_webhook"
    )
    
    # Add webhook status to history
    if status_code > 0:
        webhook_status = get_webhook_status(status_code, response_text)
    else:
        webhook_status = get_webhook_error_status(response_text or "Unknown error")
    
    await add_status_to_history(db, record_id, webhook_status)
    
    return success

