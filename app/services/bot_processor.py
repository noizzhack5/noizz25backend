"""שירות לעיבוד רשומות עם סטטוס waiting_for_bot"""
import httpx
import logging
from typing import List, Dict
from app.services.storage import get_documents_by_status, update_webhook_status, update_document_status

logger = logging.getLogger(__name__)

BOT_WEBHOOK_URL = "https://noizzhack5.app.n8n.cloud/webhook/7a97c90a-6fe9-49e6-b713-7f77359582a7"

async def process_waiting_for_bot_records(db, trigger_source: str = "unknown") -> Dict[str, any]:
    """
    מחפש רשומות עם סטטוס waiting_for_bot ומבצע קריאה ל-webhook עבור כל רשומה
    
    Args:
        db: מסד הנתונים
        trigger_source: מקור ההפעלה - "scheduled" (מוזמן) או "manual" (ידני)
    
    Returns:
        dict עם סטטיסטיקות על העיבוד
    """
    source_label = "SCHEDULED (10:00 AM daily)" if trigger_source == "scheduled" else "MANUAL (user triggered)"
    logger.info(f"[BOT_PROCESSOR] Starting to process waiting_for_bot records - Trigger: {source_label}")
    
    # קבל את כל הרשומות עם סטטוס waiting_for_bot
    records = await get_documents_by_status(db, "waiting_for_bot")
    logger.info(f"[BOT_PROCESSOR] Found {len(records)} records with status 'waiting_for_bot'")
    
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
        if not phone_number or not latin_name:
            logger.warning(
                f"[BOT_PROCESSOR] Skipping record {record_id}: missing phone_number or latin_name. "
                f"phone_number={phone_number}, latin_name={latin_name}"
            )
            results["skipped"] += 1
            results["details"].append({
                "id": record_id,
                "status": "skipped",
                "reason": "missing phone_number or latin_name"
            })
            continue
        
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
                await update_document_status(db, record_id, "in_conversation_with_bot")
                logger.info(f"[BOT_PROCESSOR] Updated record {record_id} status to 'in_conversation_with_bot'")
            except Exception as e:
                logger.error(f"[BOT_PROCESSOR] Failed to update status for record {record_id}: {str(e)}", exc_info=True)
    
    return results

async def call_bot_webhook(db, record_id: str, phone_number: str, latin_name: str) -> bool:
    """
    קורא ל-webhook עם הנתונים של הרשומה
    
    Args:
        db: מסד הנתונים
        record_id: מזהה הרשומה
        phone_number: מספר טלפון
        latin_name: שם לטיני
    
    Returns:
        True אם הקריאה הצליחה, False אחרת
    """
    logger.info(
        f"[BOT_WEBHOOK] Calling webhook for record {record_id}. "
        f"phone_number={phone_number}, latin_name={latin_name}"
    )
    
    payload = {
        "id": record_id,
        "phone_number": phone_number,
        "latin_name": latin_name
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                BOT_WEBHOOK_URL,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            status_code = response.status_code
            status_text = response.text[:500] if response.text else None
            
            logger.info(
                f"[BOT_WEBHOOK] Response for record {record_id}: "
                f"status_code={status_code}, response_text={status_text}"
            )
            
            # עדכן את סטטוס ה-webhook
            await update_webhook_status(db, record_id, status_code, status_text)
            
            # אם הקריאה הצליחה (status code 2xx), החזר True
            # הסטטוס יעודכן בסוף העיבוד של כל הרשומות
            if 200 <= status_code < 300:
                return True
            else:
                logger.warning(
                    f"[BOT_WEBHOOK] Webhook returned non-success status code {status_code} "
                    f"for record {record_id}"
                )
                return False
                
    except httpx.TimeoutException as e:
        error_msg = f"Webhook timeout: {str(e)}"
        logger.error(f"[BOT_WEBHOOK] {error_msg} for record {record_id}")
        await update_webhook_status(db, record_id, 0, error_msg[:200])
        return False
    except httpx.RequestError as e:
        error_msg = f"Webhook request error: {str(e)}"
        logger.error(f"[BOT_WEBHOOK] {error_msg} for record {record_id}")
        await update_webhook_status(db, record_id, 0, error_msg[:200])
        return False
    except Exception as e:
        error_msg = f"Webhook unexpected error: {str(e)}"
        logger.error(f"[BOT_WEBHOOK] {error_msg} for record {record_id}", exc_info=True)
        await update_webhook_status(db, record_id, 0, error_msg[:200])
        return False

