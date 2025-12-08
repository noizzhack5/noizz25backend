"""שירות לעיבוד רשומות עם סטטוס waiting_for_bot"""
import httpx
import logging
from typing import List, Dict
from app.services.storage import get_documents_by_status, add_status_to_history, update_document_status
from app.constants import (
    STATUS_WAITING_BOT_INTERVIEW,
    STATUS_BOT_INTERVIEW,
    get_webhook_status,
    get_webhook_error_status
)

logger = logging.getLogger(__name__)

BOT_WEBHOOK_URL = "https://noizzhack5.app.n8n.cloud/webhook/7a97c90a-6fe9-49e6-b713-7f77359582a7"

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
    logger.info(f"[BOT_PROCESSOR] Starting to process {STATUS_WAITING_BOT_INTERVIEW} records - Trigger: {source_label}")
    
    # קבל את כל הרשומות עם סטטוס waiting_bot_interview
    records = await get_documents_by_status(db, STATUS_WAITING_BOT_INTERVIEW)
    logger.info(f"[BOT_PROCESSOR] Found {len(records)} records with status '{STATUS_WAITING_BOT_INTERVIEW}'")
    
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
            
            # הוסף סטטוס webhook ל-history
            webhook_status = get_webhook_status(status_code, status_text)
            await add_status_to_history(db, record_id, webhook_status)
            
            # נסה לפרסר את ה-response כ-JSON ולבדוק את השדה success
            try:
                response_json = response.json()
                logger.info(
                    f"[BOT_WEBHOOK] Parsed response JSON for record {record_id}: {response_json}"
                )
                success_value = response_json.get("success", False)
                
                # המר string "true"/"false" לבוליאני
                if isinstance(success_value, str):
                    success_value_lower = success_value.lower().strip()
                    if success_value_lower == "true":
                        success_value = True
                        logger.info(
                            f"[BOT_WEBHOOK] Converted success string 'true' to boolean True for record {record_id}"
                        )
                    elif success_value_lower == "false":
                        success_value = False
                        logger.info(
                            f"[BOT_WEBHOOK] Converted success string 'false' to boolean False for record {record_id}"
                        )
                    else:
                        # אם הערך הוא string אבל לא "true" או "false", נשתמש ב-status code כגיבוי
                        logger.warning(
                            f"[BOT_WEBHOOK] Webhook response success field is string with unexpected value '{success_value}' for record {record_id}, "
                            f"using status code as fallback"
                        )
                        return 200 <= status_code < 300
                
                if isinstance(success_value, bool):
                    if success_value:
                        logger.info(
                            f"[BOT_WEBHOOK] Webhook returned success=True for record {record_id}"
                        )
                        return True
                    else:
                        logger.warning(
                            f"[BOT_WEBHOOK] Webhook returned success=False for record {record_id}"
                        )
                        return False
                else:
                    # אם success לא boolean ולא string, נשתמש ב-status code כגיבוי
                    logger.warning(
                        f"[BOT_WEBHOOK] Webhook response success field is not boolean or string for record {record_id} "
                        f"(type: {type(success_value).__name__}, value: {success_value}), "
                        f"using status code as fallback"
                    )
                    return 200 <= status_code < 300
            except (ValueError, KeyError) as e:
                # אם לא ניתן לפרסר JSON או אין שדה success, נשתמש ב-status code כגיבוי
                logger.warning(
                    f"[BOT_WEBHOOK] Could not parse response JSON or find 'success' field for record {record_id}: {str(e)}. "
                    f"Using status code as fallback"
                )
                return 200 <= status_code < 300
                
    except httpx.TimeoutException as e:
        error_msg = f"Webhook timeout: {str(e)}"
        logger.error(f"[BOT_WEBHOOK] {error_msg} for record {record_id}")
        await add_status_to_history(db, record_id, get_webhook_error_status(error_msg))
        return False
    except httpx.RequestError as e:
        error_msg = f"Webhook request error: {str(e)}"
        logger.error(f"[BOT_WEBHOOK] {error_msg} for record {record_id}")
        await add_status_to_history(db, record_id, get_webhook_error_status(error_msg))
        return False
    except Exception as e:
        error_msg = f"Webhook unexpected error: {str(e)}"
        logger.error(f"[BOT_WEBHOOK] {error_msg} for record {record_id}", exc_info=True)
        await add_status_to_history(db, record_id, get_webhook_error_status(error_msg))
        return False

