from fastapi import FastAPI, File, UploadFile, Form, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient
from app.models import CVDocumentInDB, CVUploadResponse, CVUpdateRequest, StatusUpdateRequest, RecruitNoteRequest, BulkUploadResponse
from app.database import get_database
from app.services.pdf_parser import extract_text_from_pdf
from app.services.excel_processor import parse_excel_file, parse_csv_file
from app.services.storage import insert_cv_document, get_all_documents, get_document_by_id, delete_document_by_id, restore_document_by_id, add_status_to_history, update_document_full, update_document_status, update_document_fields_only, search_documents_advanced
from app.services.bot_processor import process_waiting_for_bot_records, process_single_bot_record
from app.services.chat_service import get_chat_history_by_id
from app.jobs.classification_processor import process_waiting_classification_records
from app.jobs.scheduler import setup_scheduler, shutdown_scheduler
from app.services.config_loader import get_webhook_url
from app.core.constants import (
    STATUS_EXTRACTING,
    STATUS_READY_FOR_BOT_INTERVIEW,
    STATUS_IN_CLASSIFICATION,
    STATUS_READY_FOR_RECRUIT,
    STATUS_PROCESSING_SUCCESS,
    STATUS_PROCESSING_FAILED,
    DocumentStatus,
    get_processing_error_status,
    get_webhook_status,
    get_webhook_error_status,
    get_status_by_id,
    get_all_statuses,
    STATUS_ID_MAP
)
from app.core.config import (
    CORS_ALLOW_ORIGINS,
    CORS_ALLOW_CREDENTIALS,
    CORS_ALLOW_METHODS,
    CORS_ALLOW_HEADERS,
    get_port
)
from app.core.exceptions import DocumentNotFoundError, InvalidStatusError, ValidationError
import datetime
import logging

# הגדרת logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=CORS_ALLOW_METHODS,
    allow_headers=CORS_ALLOW_HEADERS,
)

db_client = None

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
    """
    Call webhook with document ID
    Uses webhook_client utility for making HTTP requests
    """
    from app.utils.webhook_client import webhook_client
    
    webhook_url = get_webhook_url("upload_cv")
    payload = {"id": document_id}
    
    # Use webhook client (standard HTTP status code check)
    success, status_code, response_text = await webhook_client.call_webhook(
        url=webhook_url,
        payload=payload,
        webhook_name="upload_cv"
    )
    
    # Add webhook status to history
    if status_code > 0:
        webhook_status = get_webhook_status(status_code, response_text)
    else:
        webhook_status = get_webhook_error_status(response_text or "Unknown error")
    
    await add_status_to_history(db_client, document_id, webhook_status)
    
    # If successful, update status to "Extracting"
    if success:
        await update_document_status(db_client, document_id, STATUS_EXTRACTING)
        logger.info(f"[WEBHOOK] Updated document {document_id} status to '{STATUS_EXTRACTING}'")

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
    """
    Upload a new CV document
    
    Accepts either a PDF file or metadata (or both)
    """
    if not file and not any([name, phone, email, campaign, notes]):
        raise ValidationError("Must provide either PDF file or metadata")

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

@app.post("/upload-cv-excel", response_model=BulkUploadResponse)
async def upload_cv_excel(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="קובץ אקסל או CSV עם רשומות מועמדים")
):
    """
    העלאת קובץ אקסל או CSV עם ריבוי רשומות מועמדים
    
    הקובץ צריך להכיל שורת headers עם העמודות:
    - name (חובה)
    - phone_number או phone (חובה)
    - email (אופציונלי)
    - campaign (אופציונלי)
    - notes (אופציונלי)
    
    כל שורה בקובץ תיצור מסמך CV חדש במערכת.
    
    תומך בפורמטים: .xlsx, .xls, .csv
    """
    # בדוק שהקובץ הוא אקסל או CSV
    if not file.filename:
        raise ValidationError("יש לספק קובץ")
    
    file_extension = file.filename.lower().split('.')[-1] if '.' in file.filename else ""
    if file_extension not in ['xlsx', 'xls', 'csv']:
        raise ValidationError("הקובץ חייב להיות בפורמט Excel (.xlsx או .xls) או CSV (.csv)")
    
    try:
        # קרא את הקובץ
        file_bytes = await file.read()
        
        # פרסר את הקובץ לפי סוג הקובץ
        if file_extension == 'csv':
            records = parse_csv_file(file_bytes)
        else:
            records = parse_excel_file(file_bytes)
        
        if not records:
            raise ValidationError("לא נמצאו רשומות בקובץ")
        
        # עבד כל רשומה ויצור מסמך
        successful = 0
        failed = 0
        document_ids = []
        errors = []
        
        for idx, record in enumerate(records, start=1):
            try:
                # בדוק שיש לפחות name או phone_number
                if not record.get("name") and not record.get("phone_number"):
                    errors.append({
                        "row": idx + 1,  # +1 כי idx מתחיל מ-1, ויש גם שורת headers
                        "error": "רשומה ללא name או phone_number",
                        "record": record
                    })
                    failed += 1
                    continue
                
                # צור מסמך עבור הרשומה
                document = {
                    "file_metadata": None,
                    "extracted_text": "",
                    "known_data": {
                        "name": record.get("name"),
                        "phone_number": record.get("phone_number"),
                        "email": record.get("email"),
                        "campaign": record.get("campaign"),
                        "notes": record.get("notes"),
                        "job_type": None,
                        "match_score": None,
                        "class_explain": None
                    }
                }
                
                inserted_id = await insert_cv_document(db_client, document)
                document_ids.append(str(inserted_id))
                
                # הוסף סטטוס processing ל-history
                await add_status_to_history(db_client, inserted_id, STATUS_PROCESSING_FAILED)
                
                # קריאה ל-webhook אחרי השמירה (ב-background)
                background_tasks.add_task(call_webhook, inserted_id)
                
                successful += 1
                logger.info(f"[BULK_UPLOAD] Record {idx} saved with ID: {inserted_id}")
                
            except Exception as e:
                failed += 1
                error_msg = str(e)
                errors.append({
                    "row": idx + 1,
                    "error": error_msg,
                    "record": record
                })
                logger.error(f"[BULK_UPLOAD] Error processing record {idx}: {error_msg}", exc_info=True)
        
        logger.info(f"[BULK_UPLOAD] Completed: {successful} successful, {failed} failed out of {len(records)} total")
        
        return {
            "total_records": len(records),
            "successful": successful,
            "failed": failed,
            "document_ids": document_ids,
            "errors": errors if errors else []
        }
        
    except ValueError as e:
        # שגיאת פרסור
        raise ValidationError(str(e))
    except Exception as e:
        logger.error(f"[BULK_UPLOAD] Error processing file: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"שגיאה בעיבוד הקובץ: {str(e)}")

@app.get("/cv")
async def get_all(deleted: Optional[bool] = Query(None, description="True - רק מחוקים, False/None - רק לא מחוקים")):
    """
    מחזיר את כל המסמכים
    - deleted=None או False: רק מסמכים שלא מחוקים (ברירת מחדל)
    - deleted=True: רק מסמכים מחוקים
    """
    return await get_all_documents(db_client, deleted)

@app.get("/statuses")
async def get_statuses():
    """
    מחזיר את כל הסטטוסים הזמינים במערכת
    
    מחזיר רשימה של כל הסטטוסים עם המזהה והשם שלהם.
    """
    return get_all_statuses()

@app.get("/cv/search")
async def search_cv(
    free_text: Optional[str] = Query(None, description="חיפוש חופשי - יחפש את הערך בכל שדה במסמך"),
    current_status: Optional[str] = Query(None, description="חיפוש לפי סטטוס נוכחי"),
    job_type: Optional[str] = Query(None, description="חיפוש לפי סוג עבודה"),
    match_score: Optional[str] = Query(
        None,
        description="חיפוש לפי טווח ציון התאמה: 'below 70', '70-79', '80-89', '90-100', 'all match_score'"
    ),
    campaign: Optional[str] = Query(None, description="חיפוש לפי קמפיין"),
    country: Optional[str] = Query(None, description="חיפוש לפי ארץ (nationality)")
):
    """
    חיפוש מתקדם במסמכי CV
    
    תומך בחיפוש חופשי (בכל השדות) ובחיפוש לפי שדות ספציפיים:
    - current_status: סטטוס נוכחי
    - job_type: סוג עבודה
    - match_score: טווח ציון התאמה (below 70, 70-79, 80-89, 90-100, all match_score)
    - campaign: קמפיין
    - country: ארץ (nationality)
    
    ניתן לשלב מספר קריטריונים - החיפוש יחזיר מסמכים התואמים לכל הקריטריונים.
    """
    # בדוק שיש לפחות קריטריון חיפוש אחד
    if not any([free_text, current_status, job_type, match_score, campaign, country]):
        raise ValidationError("יש לספק לפחות קריטריון חיפוש אחד")
    
    # בדוק שהערך של match_score תקף
    if match_score and match_score not in ["below 70", "70-79", "80-89", "90-100", "all match_score"]:
        raise ValidationError(
            f"ערך לא תקף ל-match_score: '{match_score}'. "
            "הערכים התקפים: 'below 70', '70-79', '80-89', '90-100', 'all match_score'"
        )
    
    results = await search_documents_advanced(
        db_client,
        free_text=free_text,
        current_status=current_status,
        job_type=job_type,
        match_score=match_score,
        campaign=campaign,
        country=country
    )
    
    return results

@app.get("/cv/{id}")
async def get_cv_by_id(id: str):
    """Get a CV document by ID (returns deleted documents too)"""
    doc = await get_document_by_id(db_client, id)
    if not doc:
        raise DocumentNotFoundError(id)
    return doc

@app.delete("/cv/{id}")
async def delete_cv_by_id(id: str):
    """
    Soft delete a document by setting is_deleted to True
    """
    deleted = await delete_document_by_id(db_client, id)
    if not deleted:
        raise DocumentNotFoundError(id)
    return {"status": "deleted"}

@app.post("/cv/{id}/restore")
async def restore_cv_by_id(id: str):
    """
    Restore a deleted document by setting is_deleted to False
    """
    restored = await restore_document_by_id(db_client, id)
    if not restored:
        raise DocumentNotFoundError(id)
    return {"status": "restored", "id": id}

@app.patch("/cv/{id}")
async def update_cv(id: str, update_data: CVUpdateRequest):
    """
    Update a document - updates only fields provided in body (except phone_number which cannot be updated)
    Accepts JSON with fields to update
    """
    # Check document exists
    doc = await get_document_by_id(db_client, id)
    if not doc:
        raise DocumentNotFoundError(id)
    
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
        
        # אם הסטטוס הנוכחי הוא EXTRACTING - עדכן ל-READY_FOR_BOT_INTERVIEW
        if current_status == STATUS_EXTRACTING:
            await update_document_status(db_client, id, STATUS_READY_FOR_BOT_INTERVIEW)
            logger.info(f"[UPDATE] Document {id} updated successfully, status changed from '{STATUS_EXTRACTING}' to '{STATUS_READY_FOR_BOT_INTERVIEW}'")
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
    Update document status by status ID
    
    - Updates current_status
    - Adds new status to status_history with timestamp
    
    **Available statuses:**
    - 1: Submitted
    - 2: Extracting
    - 3: Ready For Bot Interview
    - 4: Bot Interview
    - 5: Ready For Classification
    - 6: In Classification
    - 7: Ready For Recruit
    """
    # Check document exists
    doc = await get_document_by_id(db_client, id)
    if not doc:
        raise DocumentNotFoundError(id)
    
    # Get status name by ID
    status_value = get_status_by_id(status_data.status_id)
    if not status_value:
        raise InvalidStatusError(status_data.status_id, STATUS_ID_MAP)
    
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

@app.patch("/cv/{id}/recruit-note")
async def update_recruit_note(id: str, note_data: RecruitNoteRequest):
    """
    שמירת הערת recruit עבור מסמך
    
    שומר את ההערה תחת known_data.recruit_note
    """
    # בדוק שהמסמך קיים
    doc = await get_document_by_id(db_client, id)
    if not doc:
        raise DocumentNotFoundError(id)
    
    # עדכן את ההערה
    update_dict = {"recruit_note": note_data.recruit_note}
    updated = await update_document_fields_only(db_client, id, update_dict)
    
    if updated:
        logger.info(f"[RECRUIT_NOTE] Document {id} - recruit note updated successfully")
        return {
            "status": "updated",
            "id": id,
            "recruit_note": note_data.recruit_note
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to update recruit note")

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

@app.post("/process-bot/{id}")
async def trigger_single_bot_processor(id: str):
    """
    מפעיל עיבוד עבור רשומה ספציפית לפי ID
    
    - בודק שהרשומה קיימת
    - בודק שהרשומה בסטטוס "Ready For Bot Interview"
    - אם כן, מפעיל את הקריאה ל-webhook
    - אם הקריאה הצליחה, מעדכן את הסטטוס ל-"Bot Interview"
    """
    logger.info(f"[MANUAL_TRIGGER] Manual trigger of single bot processor for record {id}")
    try:
        result = await process_single_bot_record(db_client, id)
        logger.info(f"[MANUAL_TRIGGER] Single bot processor completed for record {id}: {result}")
        
        # אם הרשומה לא נמצאה או לא בסטטוס הנכון, החזר שגיאה מתאימה
        if result.get("status") == "not_found":
            raise DocumentNotFoundError(id)
        elif result.get("status") == "invalid_status":
            raise HTTPException(
                status_code=400,
                detail=result.get("message", f"Record {id} is not in the correct status")
            )
        elif not result.get("success"):
            # אם יש שגיאה אחרת, החזר אותה
            raise HTTPException(
                status_code=500,
                detail=result.get("message", f"Error processing record {id}")
            )
        
        return result
    except DocumentNotFoundError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MANUAL_TRIGGER] Error in single bot processor for record {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing record {id}: {str(e)}")

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

@app.get("/chat-history/{id}")
async def get_chat_history(id: str):
    """
    מחזיר את היסטוריית הצ'אט של משתמש לפי ID
    
    Args:
        id: מזהה המשתמש (יכול להיות ObjectId, phone_number, או string ID)
    
    Returns:
        Dictionary עם היסטוריית הצ'אט של המשתמש
    """
    logger.info(f"[CHAT_HISTORY] Requesting chat history for user ID: {id}")
    try:
        chat_history = await get_chat_history_by_id(db_client, id)
        
        if not chat_history:
            logger.warning(f"[CHAT_HISTORY] Chat history not found for user ID: {id}")
            raise HTTPException(
                status_code=404,
                detail=f"Chat history not found for user ID: {id}"
            )
        
        logger.info(f"[CHAT_HISTORY] Successfully retrieved chat history for user ID: {id}")
        return chat_history
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CHAT_HISTORY] Error retrieving chat history for user ID {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving chat history: {str(e)}")

# Direct execution option for Render, Heroku or local:
if __name__ == "__main__":
    import uvicorn
    port = get_port()
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
