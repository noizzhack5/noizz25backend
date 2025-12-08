"""
שירות לעיבוד רשומות עם סטטוס waiting_classification
"""
import httpx
import logging
from typing import Dict
from app.services.storage import get_documents_by_status, add_status_to_history, update_document_status
from app.services.config_loader import get_webhook_url
from app.constants import (
    STATUS_WAITING_CLASSIFICATION,
    STATUS_IN_CLASSIFICATION,
    get_webhook_status,
    get_webhook_error_status
)

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
    logger.info(f"[CLASSIFICATION_PROCESSOR] Starting to process {STATUS_WAITING_CLASSIFICATION} records")
    
    # קבל את כל הרשומות עם סטטוס waiting_classification
    records = await get_documents_by_status(db, STATUS_WAITING_CLASSIFICATION)
    logger.info(f"[CLASSIFICATION_PROCESSOR] Found {len(records)} records with status '{STATUS_WAITING_CLASSIFICATION}'")
    
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
    
    Args:
        db: מסד הנתונים
        record_id: מזהה הרשומה
    
    Returns:
        True אם הקריאה הצליחה, False אחרת
    """
    logger.info(f"[CLASSIFICATION_WEBHOOK] Calling webhook for record {record_id}")
    
    payload = {
        "id": record_id
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            webhook_url = get_classification_webhook_url()
            response = await client.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            status_code = response.status_code
            status_text = response.text[:500] if response.text else None
            
            logger.info(
                f"[CLASSIFICATION_WEBHOOK] Response for record {record_id}: "
                f"status_code={status_code}, response_text={status_text}"
            )
            
            # הוסף סטטוס webhook ל-history
            webhook_status = get_webhook_status(status_code, status_text)
            await add_status_to_history(db, record_id, webhook_status)
            
            # אם הקריאה הצליחה (status code 2xx), החזר True
            if 200 <= status_code < 300:
                logger.info(f"[CLASSIFICATION_WEBHOOK] Webhook call successful for record {record_id}")
                return True
            else:
                logger.warning(f"[CLASSIFICATION_WEBHOOK] Webhook call failed for record {record_id} with status code {status_code}")
                return False
                
    except httpx.TimeoutException as e:
        error_msg = f"Webhook timeout: {str(e)}"
        logger.error(f"[CLASSIFICATION_WEBHOOK] {error_msg} for record {record_id}")
        await add_status_to_history(db, record_id, get_webhook_error_status(error_msg))
        return False
    except httpx.RequestError as e:
        error_msg = f"Webhook request error: {str(e)}"
        logger.error(f"[CLASSIFICATION_WEBHOOK] {error_msg} for record {record_id}")
        await add_status_to_history(db, record_id, get_webhook_error_status(error_msg))
        return False
    except Exception as e:
        error_msg = f"Webhook unexpected error: {str(e)}"
        logger.error(f"[CLASSIFICATION_WEBHOOK] {error_msg} for record {record_id}", exc_info=True)
        await add_status_to_history(db, record_id, get_webhook_error_status(error_msg))
        return False

