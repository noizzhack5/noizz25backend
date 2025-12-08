from fastapi import FastAPI, File, UploadFile, Form, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient
from app.models import CVDocumentInDB, CVUploadResponse, CVUpdateRequest, StatusUpdateRequest
from app.database import get_database
from app.services.pdf_parser import extract_text_from_pdf
from app.services.storage import insert_cv_document, get_all_documents, get_document_by_id, delete_document_by_id, search_documents, add_status_to_history, update_document_full, update_document_status, update_document_fields_only
from app.services.bot_processor import process_waiting_for_bot_records
from app.jobs.classification_processor import process_waiting_classification_records
from app.jobs.scheduler import setup_scheduler, shutdown_scheduler
from app.constants import (
    STATUS_EXTRACTING,
    STATUS_WAITING_BOT_INTERVIEW,
    STATUS_IN_CLASSIFICATION,
    STATUS_READY_FOR_RECRUIT,
    STATUS_PROCESSING_SUCCESS,
    STATUS_PROCESSING_FAILED,
    DocumentStatus,
    get_processing_error_status,
    get_webhook_status,
    get_webhook_error_status
)
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

WEBHOOK_URL = "https://noizzhack5.app.n8n.cloud/webhook/cc359f5c-9c54-454f-bd71-28f3af0aacaf"

@app.on_event("startup")
async def startup_event():
    global db_client
    db_client = get_database()
    
    # הגדר את ה-scheduler
    setup_scheduler(db_client)

@app.on_event("shutdown")
async def shutdown_event():
    shutdown_scheduler()

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
    מעדכן מסמך - מעדכן רק את השדות שמגיעים ב-body (למעט phone_number שאי אפשר לעדכן)
    מקבל JSON עם שדות לעדכון
    """
    # בדוק שהמסמך קיים
    doc = await get_document_by_id(db_client, id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # המר את ה-Pydantic model ל-dict - רק שדות שנשלחו (exclude_none=True)
    update_dict = update_data.model_dump(exclude_none=True)
    
    # הסר phone_number - לא ניתן לעדכן אותו
    update_dict.pop("phone_number", None)
    
    # אם אין שדות לעדכון, החזר הודעה
    if not update_dict:
        logger.info(f"[UPDATE] Document {id} - no fields to update")
        return {"status": "no_changes", "id": id, "message": "No fields to update"}
    
    # עדכן את המסמך - רק את השדות שנשלחו
    updated = await update_document_fields_only(db_client, id, update_dict)
    
    if updated:
        # בדוק את הסטטוס הנוכחי ועדכן בהתאם
        current_status = doc.get("current_status")
        
        # אם הסטטוס הנוכחי הוא EXTRACTING - עדכן ל-WAITING_BOT_INTERVIEW
        if current_status == STATUS_EXTRACTING:
            await update_document_status(db_client, id, STATUS_WAITING_BOT_INTERVIEW)
            logger.info(f"[UPDATE] Document {id} updated successfully, status changed from '{STATUS_EXTRACTING}' to '{STATUS_WAITING_BOT_INTERVIEW}'")
        # אם הסטטוס הנוכחי הוא IN_CLASSIFICATION - עדכן ל-READY_FOR_RECRUIT
        elif current_status == STATUS_IN_CLASSIFICATION:
            await update_document_status(db_client, id, STATUS_READY_FOR_RECRUIT)
            logger.info(f"[UPDATE] Document {id} updated successfully, status changed from '{STATUS_IN_CLASSIFICATION}' to '{STATUS_READY_FOR_RECRUIT}'")
        else:
            logger.info(f"[UPDATE] Document {id} updated successfully (current status: {current_status}, no status change needed)")
        
        return {"status": "updated", "id": id}
    else:
        logger.info(f"[UPDATE] Document {id} - no fields to update")
        return {"status": "no_changes", "id": id, "message": "No fields to update"}

@app.patch("/cv/{id}/status")
async def update_cv_status(id: str, status_data: StatusUpdateRequest):
    """
    מעדכן את הסטטוס של מסמך CV לפי ID של סטטוס
    
    - מעדכן את current_status
    - מוסיף את הסטטוס החדש ל-status_history עם timestamp
    
    **סטטוסים זמינים:**
    - 1: Submitted
    - 2: Extracting
    - 3: Waiting Bot Interview
    - 4: Bot Interview
    - 5: Waiting Classification
    - 6: In Classification
    - 7: Ready For Recruit
    """
    from app.constants import get_status_by_id, STATUS_ID_MAP
    
    # בדוק שהמסמך קיים
    doc = await get_document_by_id(db_client, id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # קבל את שם הסטטוס לפי ID
    status_value = get_status_by_id(status_data.status_id)
    if not status_value:
        available_statuses = ", ".join([f"{sid}={sname}" for sid, sname in STATUS_ID_MAP.items()])
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid status_id: {status_data.status_id}. Available statuses: {available_statuses}"
        )
    
    # עדכן את הסטטוס
    updated = await update_document_status(db_client, id, status_value)
    if updated:
        logger.info(f"[STATUS_UPDATE] Document {id} status updated to '{status_value}' (ID: {status_data.status_id})")
        return {
            "status": "updated",
            "id": id,
            "status_id": status_data.status_id,
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

@app.post("/process-waiting-classification")
async def trigger_classification_processor():
    """
    מפעיל ידנית את השירות לעיבוד רשומות עם סטטוס waiting_classification
    שירות זה רץ אוטומטית כל X דקות, אבל ניתן להפעיל אותו ידנית דרך endpoint זה
    """
    logger.info("[MANUAL_TRIGGER] Manual trigger of classification processor requested (triggered by user via API endpoint)")
    try:
        results = await process_waiting_classification_records(db_client)
        logger.info(f"[MANUAL_TRIGGER] Manual classification trigger completed: {results}")
        return {
            "status": "completed",
            "message": "Classification processor executed successfully",
            "results": results
        }
    except Exception as e:
        logger.error(f"[MANUAL_TRIGGER] Error in manual classification trigger: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error executing classification processor: {str(e)}")

# אפשרות להרצה ישירה עבור Render, Heroku או לוקאלי:
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
