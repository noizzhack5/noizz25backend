from fastapi import FastAPI, File, UploadFile, Form, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient
from app.models import CVDocumentInDB, CVUploadResponse, CVUpdateRequest, StatusUpdateRequest
from app.database import get_database
from app.services.pdf_parser import extract_text_from_pdf
from app.services.storage import insert_cv_document, get_all_documents, get_document_by_id, delete_document_by_id, search_documents, add_status_to_history, update_document_partial, update_document_status
from app.services.bot_processor import process_waiting_for_bot_records
from app.constants import (
    STATUS_EXTRACTING,
    STATUS_WAITING_BOT_INTERVIEW,
    STATUS_PROCESSING_SUCCESS,
    STATUS_PROCESSING_FAILED,
    DocumentStatus,
    get_processing_error_status,
    get_webhook_status,
    get_webhook_error_status
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import datetime
import os
import httpx
import logging

# הגדרת logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()

# הוסף CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # מאפשר מכל מקור - לפרודקשן כדאי להגביל ל-domains ספציפיים
    allow_credentials=True,
    allow_methods=["*"],  # מאפשר כל ה-HTTP methods
    allow_headers=["*"],  # מאפשר כל ה-headers
)

db_client = None
scheduler = None

WEBHOOK_URL = "https://noizzhack5.app.n8n.cloud/webhook/cc359f5c-9c54-454f-bd71-28f3af0aacaf"

async def scheduled_bot_processor():
    """פונקציה שרצה על ידי ה-scheduler כל יום ב-10:00"""
    global db_client
    logger.info("[SCHEDULER] Starting scheduled bot processor job (triggered by daily scheduler at 10:00 AM)")
    try:
        results = await process_waiting_for_bot_records(db_client, trigger_source="scheduled")
        logger.info(f"[SCHEDULER] Scheduled job completed: {results}")
    except Exception as e:
        logger.error(f"[SCHEDULER] Error in scheduled job: {str(e)}", exc_info=True)

@app.on_event("startup")
async def startup_event():
    global db_client, scheduler
    db_client = get_database()
    
    # הגדר את ה-scheduler
    scheduler = AsyncIOScheduler()
    # הרץ כל יום ב-10:00 בבוקר (UTC)
    scheduler.add_job(
        scheduled_bot_processor,
        trigger=CronTrigger(hour=10, minute=0),
        id="daily_bot_processor",
        name=f"Process {STATUS_WAITING_BOT_INTERVIEW} records daily at 10 AM",
        replace_existing=True
    )
    scheduler.start()
    logger.info("[STARTUP] Scheduler started - bot processor will run daily at 10:00 AM UTC")

@app.on_event("shutdown")
async def shutdown_event():
    global scheduler
    if scheduler:
        scheduler.shutdown()
        logger.info("[SHUTDOWN] Scheduler stopped")

async def call_webhook(document_id: str):
    """קורא ל-webhook עם ה-ID של המסמך"""
    logger.info(f"[WEBHOOK] Starting webhook call for document_id: {document_id}")
    logger.info(f"[WEBHOOK] URL: {WEBHOOK_URL}")
    logger.info(f"[WEBHOOK] Payload: {{'id': '{document_id}'}}")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.info(f"[WEBHOOK] Sending POST request to webhook...")
            response = await client.post(
                WEBHOOK_URL,
                json={"id": document_id},
                headers={"Content-Type": "application/json"}
            )
            status_code = response.status_code
            status_text = response.text[:500] if response.text else None
            
            logger.info(f"[WEBHOOK] Response status code: {status_code}")
            logger.info(f"[WEBHOOK] Response headers: {dict(response.headers)}")
            logger.info(f"[WEBHOOK] Response text (first 500 chars): {status_text}")
            
            # הוסף סטטוס webhook ל-history
            webhook_status = get_webhook_status(status_code, status_text)
            await add_status_to_history(db_client, document_id, webhook_status)
            logger.info(f"[WEBHOOK] Added webhook_status to history for {document_id} with status {status_code}")
            
            # אם הקריאה הצליחה (status code 2xx), עדכן סטטוס ל-"extracting"
            if 200 <= status_code < 300:
                await update_document_status(db_client, document_id, STATUS_EXTRACTING)
                logger.info(f"[WEBHOOK] Updated document {document_id} status to '{STATUS_EXTRACTING}'")
            
    except httpx.TimeoutException as e:
        error_msg = f"Webhook timeout: {str(e)}"
        logger.error(f"[WEBHOOK] {error_msg}")
        await add_status_to_history(db_client, document_id, get_webhook_error_status(error_msg))
    except httpx.RequestError as e:
        error_msg = f"Webhook request error: {str(e)}"
        logger.error(f"[WEBHOOK] {error_msg}")
        await add_status_to_history(db_client, document_id, get_webhook_error_status(error_msg))
    except Exception as e:
        error_msg = f"Webhook unexpected error: {str(e)}"
        logger.error(f"[WEBHOOK] {error_msg}", exc_info=True)
        await add_status_to_history(db_client, document_id, get_webhook_error_status(error_msg))

@app.post("/upload-cv", response_model=CVUploadResponse)
async def upload_cv(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    name: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    campaign: Optional[str] = Form(None),
    notes: Optional[str] = Form(None)
):
    if not file and not any([name, phone, email, campaign, notes]):
        raise HTTPException(status_code=400, detail="Must provide either PDF file or metadata")

    file_metadata = None
    extracted_text = ""
    parse_success = False
    error_message = None
    pdf_bytes = None

    if file is not None:
        pdf_bytes = await file.read()
        file_metadata = {
            "filename": file.filename,
            "size_bytes": len(pdf_bytes),
            "content_type": file.content_type,
            "uploaded_at": datetime.datetime.utcnow().isoformat() + "Z"
        }
        extracted_text, error_message = extract_text_from_pdf(pdf_bytes) if pdf_bytes else ("", "empty upload")
        parse_success = bool(extracted_text)

    document = {
        "file_metadata": file_metadata,
        "extracted_text": extracted_text,
        "known_data": {
            "name": name,
            "phone_number": phone,  # שמירה כ-phone_number במקום phone
            "email": email,
            "campaign": campaign,
            "notes": notes,
            "job_type": None,
            "match_score": None,
            "class_explain": None
        }
    }

    inserted_id = await insert_cv_document(db_client, document)
    logger.info(f"[UPLOAD] Document saved with ID: {inserted_id}")
    
    # הוסף סטטוס processing ל-history אחרי יצירת המסמך
    if error_message:
        processing_status = get_processing_error_status(error_message)
    elif parse_success:
        processing_status = STATUS_PROCESSING_SUCCESS
    else:
        processing_status = STATUS_PROCESSING_FAILED
    
    await add_status_to_history(db_client, inserted_id, processing_status)
    
    # קריאה ל-webhook אחרי השמירה (ב-background כדי לא לחסום את התגובה)
    background_tasks.add_task(call_webhook, inserted_id)
    logger.info(f"[UPLOAD] Webhook task added to background for document_id: {inserted_id}")
    
    return {"id": str(inserted_id), "status": "stored"}

@app.get("/cv")
async def get_all(deleted: Optional[bool] = Query(None, description="True - רק מחוקים, False/None - רק לא מחוקים")):
    """
    מחזיר את כל המסמכים
    - deleted=None או False: רק מסמכים שלא מחוקים (ברירת מחדל)
    - deleted=True: רק מסמכים מחוקים
    """
    return await get_all_documents(db_client, deleted)

@app.get("/cv/{id}")
async def get_cv_by_id(id: str):
    doc = await get_document_by_id(db_client, id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

@app.delete("/cv/{id}")
async def delete_cv_by_id(id: str):
    deleted = await delete_document_by_id(db_client, id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"status": "deleted"}

@app.get("/cv/search")
async def search_cv(query: str = Query(..., min_length=1)):
    return await search_documents(db_client, query)

@app.patch("/cv/{id}")
async def update_cv(id: str, update_data: CVUpdateRequest):
    """
    מעדכן מסמך - רק שדות שלא קיימים או ריקים
    מקבל JSON עם שדות נוספים על המועמד
    """
    # בדוק שהמסמך קיים
    doc = await get_document_by_id(db_client, id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # המר את ה-Pydantic model ל-dict (רק שדות שלא None)
    update_dict = update_data.model_dump(exclude_none=True)
    
    # הוסף את השדות job_type, match_score, class_explain תמיד (גם אם None)
    # שדות אלה נשמרים תמיד תחת known_data, גם אם הם NULL
    always_update_fields = ["job_type", "match_score", "class_explain"]
    for field in always_update_fields:
        if hasattr(update_data, field):
            update_dict[field] = getattr(update_data, field)
    
    # עדכן את המסמך
    updated = await update_document_partial(db_client, id, update_dict)
    
    if updated:
        # עדכן סטטוס ל-"waiting_bot_interview" אחרי עדכון מוצלח
        await update_document_status(db_client, id, STATUS_WAITING_BOT_INTERVIEW)
        logger.info(f"[UPDATE] Document {id} updated successfully, status set to '{STATUS_WAITING_BOT_INTERVIEW}'")
        return {"status": "updated", "id": id}
    else:
        # אם לא היה מה לעדכן (כל השדות כבר קיימים)
        logger.info(f"[UPDATE] Document {id} - no new fields to update")
        return {"status": "no_changes", "id": id, "message": "All fields already exist or are empty"}

@app.patch("/cv/{id}/status")
async def update_cv_status(id: str, status_data: StatusUpdateRequest):
    """
    מעדכן את הסטטוס של מסמך CV
    
    - מעדכן את current_status
    - מוסיף את הסטטוס החדש ל-status_history עם timestamp
    """
    # בדוק שהמסמך קיים
    doc = await get_document_by_id(db_client, id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # עדכן את הסטטוס (status_data.status הוא כבר DocumentStatus enum, נמיר ל-string)
    status_value = status_data.status.value if isinstance(status_data.status, DocumentStatus) else str(status_data.status)
    updated = await update_document_status(db_client, id, status_value)
    if updated:
        logger.info(f"[STATUS_UPDATE] Document {id} status updated to '{status_value}'")
        return {
            "status": "updated",
            "id": id,
            "current_status": status_value
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to update document status")

@app.post("/process-waiting-for-bot")
async def trigger_bot_processor():
    """
    מפעיל ידנית את השירות לעיבוד רשומות עם סטטוס waiting_for_bot
    שירות זה רץ אוטומטית כל יום ב-10:00 בבוקר, אבל ניתן להפעיל אותו ידנית דרך endpoint זה
    """
    logger.info("[MANUAL_TRIGGER] Manual trigger of bot processor requested (triggered by user via API endpoint)")
    try:
        results = await process_waiting_for_bot_records(db_client, trigger_source="manual")
        logger.info(f"[MANUAL_TRIGGER] Manual trigger completed: {results}")
        return {
            "status": "completed",
            "results": results
        }
    except Exception as e:
        logger.error(f"[MANUAL_TRIGGER] Error in manual trigger: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing records: {str(e)}")

# אפשרות להרצה ישירה עבור Render, Heroku או לוקאלי:
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
