from fastapi import FastAPI, File, UploadFile, Form, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient
from app.models import CVDocumentInDB, CVUploadResponse, CVUpdateRequest
from app.database import get_database
from app.services.pdf_parser import extract_text_from_pdf
from app.services.storage import insert_cv_document, get_all_documents, get_document_by_id, delete_document_by_id, search_documents, update_webhook_status, update_document_partial
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
            
            await update_webhook_status(db_client, document_id, status_code, status_text)
            logger.info(f"[WEBHOOK] Successfully updated webhook_status for {document_id} with status {status_code}")
            
    except httpx.TimeoutException as e:
        error_msg = f"Webhook timeout: {str(e)}"
        logger.error(f"[WEBHOOK] {error_msg}")
        await update_webhook_status(db_client, document_id, 0, error_msg[:200])
    except httpx.RequestError as e:
        error_msg = f"Webhook request error: {str(e)}"
        logger.error(f"[WEBHOOK] {error_msg}")
        await update_webhook_status(db_client, document_id, 0, error_msg[:200])
    except Exception as e:
        error_msg = f"Webhook unexpected error: {str(e)}"
        logger.error(f"[WEBHOOK] {error_msg}", exc_info=True)
        await update_webhook_status(db_client, document_id, 0, error_msg[:200])

@app.post("/upload-cv", response_model=CVUploadResponse)
async def upload_cv(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    name: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    notes: Optional[str] = Form(None)
):
    if not file and not any([name, phone, email, notes]):
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
            "notes": notes
        },
        "processing": {
            "parse_success": parse_success,
            "error_message": error_message
        }
    }

    inserted_id = await insert_cv_document(db_client, document)
    logger.info(f"[UPLOAD] Document saved with ID: {inserted_id}")
    
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
    
    # עדכן את המסמך
    updated = await update_document_partial(db_client, id, update_dict)
    
    if updated:
        logger.info(f"[UPDATE] Document {id} updated successfully")
        return {"status": "updated", "id": id}
    else:
        # אם לא היה מה לעדכן (כל השדות כבר קיימים)
        logger.info(f"[UPDATE] Document {id} - no new fields to update")
        return {"status": "no_changes", "id": id, "message": "All fields already exist or are empty"}

# אפשרות להרצה ישירה עבור Render, Heroku או לוקאלי:
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
