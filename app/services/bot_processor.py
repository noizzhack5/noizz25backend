"""
Service for processing records with waiting_for_bot status
Uses webhook client utility for making HTTP requests
"""
import logging
from typing import Dict
from app.services.storage import get_documents_by_status, add_status_to_history, update_document_status
from app.services.config_loader import get_webhook_url
from app.core.constants import (
    STATUS_READY_FOR_BOT_INTERVIEW,
    STATUS_BOT_INTERVIEW,
    get_webhook_status,
    get_webhook_error_status
)
from app.utils.webhook_client import webhook_client

logger = logging.getLogger(__name__)

def get_bot_webhook_url() -> str:
    """מחזיר את ה-URL של bot webhook מהקונפיגורציה"""
    return get_webhook_url("bot_processor")

async def process_waiting_for_bot_records(db, trigger_source: str = "unknown") -> Dict[str, any]:
    """
    מחפש רשומות עם סטטוס waiting_bot_interview ומבצע קריאה ל-webhook עבור כל רשומה
    
    Args:
        db: מסד הנתונים
        trigger_source: מקור ההפעלה - "scheduled" (מוזמן) או "manual" (ידני)
    
    Returns:
        dict עם סטטיסטיקות על העיבוד
    """
    source_label = "SCHEDULED (10:00 AM daily)" if trigger_source == "scheduled" else "MANUAL (user triggered)"
    logger.info(f"[BOT_PROCESSOR] Starting to process {STATUS_READY_FOR_BOT_INTERVIEW} records - Trigger: {source_label}")
    
    # קבל את כל הרשומות עם סטטוס waiting_bot_interview
    records = await get_documents_by_status(db, STATUS_READY_FOR_BOT_INTERVIEW)
    logger.info(f"[BOT_PROCESSOR] Found {len(records)} records with status '{STATUS_READY_FOR_BOT_INTERVIEW}'")
    
    if not records:
        return {
            "total": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "details": []
        }
    
    results = {
        "total": len(records),
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "details": []
    }
    
    # עבד כל רשומה
    for record in records:
        record_id = record.get("id")
        known_data = record.get("known_data", {})
        phone_number = known_data.get("phone_number")
        latin_name = known_data.get("latin_name")
        
        # בדוק שיש את כל הנתונים הנדרשים
        # if not phone_number or not latin_name:
        #     logger.warning(
        #         f"[BOT_PROCESSOR] Skipping record {record_id}: missing phone_number or latin_name. "
        #         f"phone_number={phone_number}, latin_name={latin_name}"
        #     )
        #     results["skipped"] += 1
        #     results["details"].append({
        #         "id": record_id,
        #         "status": "skipped",
        #         "reason": "missing phone_number or latin_name"
        #     })
        #     continue
        
        # בצע קריאה ל-webhook
        try:
            success = await call_bot_webhook(db, record_id, phone_number, latin_name)
            if success:
                results["success"] += 1
                results["details"].append({
                    "id": record_id,
                    "status": "success"
                })
            else:
                results["failed"] += 1
                results["details"].append({
                    "id": record_id,
                    "status": "failed"
                })
        except Exception as e:
            logger.error(f"[BOT_PROCESSOR] Error processing record {record_id}: {str(e)}", exc_info=True)
            results["failed"] += 1
            results["details"].append({
                "id": record_id,
                "status": "error",
                "error": str(e)
            })
    
    source_label = "SCHEDULED (10:00 AM daily)" if trigger_source == "scheduled" else "MANUAL (user triggered)"
    logger.info(
        f"[BOT_PROCESSOR] Processing completed ({source_label}). "
        f"Total: {results['total']}, Success: {results['success']}, "
        f"Failed: {results['failed']}, Skipped: {results['skipped']}"
    )
    
    # עדכן סטטוס עבור כל רשומה שהצליחה
    for detail in results["details"]:
        if detail.get("status") == "success":
            record_id = detail.get("id")
            try:
                await update_document_status(db, record_id, STATUS_BOT_INTERVIEW)
                logger.info(f"[BOT_PROCESSOR] Updated record {record_id} status to '{STATUS_BOT_INTERVIEW}'")
            except Exception as e:
                logger.error(f"[BOT_PROCESSOR] Failed to update status for record {record_id}: {str(e)}", exc_info=True)
    
    return results

async def call_bot_webhook(db, record_id: str, phone_number: str, latin_name: str) -> bool:
    """
    קורא ל-webhook עם הנתונים של הרשומה
    משתמש ב-webhook_client utility לטיפול בקריאות HTTP
    
    Args:
        db: מסד הנתונים
        record_id: מזהה הרשומה
        phone_number: מספר טלפון
        latin_name: שם לטיני
    
    Returns:
        True אם הקריאה הצליחה, False אחרת
    """
    webhook_url = get_bot_webhook_url()
    payload = {
        "id": record_id,
        "phone_number": phone_number,
        "latin_name": latin_name
    }
    
    # Use webhook client with success field checking
    success, status_code, response_text = await webhook_client.call_webhook_with_success_field(
        url=webhook_url,
        payload=payload,
        webhook_name="bot_webhook"
    )
    
    # Add webhook status to history
    if status_code > 0:
        webhook_status = get_webhook_status(status_code, response_text)
    else:
        webhook_status = get_webhook_error_status(response_text or "Unknown error")
    
    await add_status_to_history(db, record_id, webhook_status)
    
    return success

