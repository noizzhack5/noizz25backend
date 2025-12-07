from fastapi import FastAPI, File, UploadFile, Form, HTTPException, status, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient
from app.models import CVDocumentInDB, CVUploadResponse
from app.database import get_database
from app.services.pdf_parser import extract_text_from_pdf
from app.services.storage import insert_cv_document, get_all_documents, get_document_by_id, delete_document_by_id, search_documents, update_webhook_status
import datetime
import os
import httpx
import logging

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
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                WEBHOOK_URL,
                json={"id": document_id},
                headers={"Content-Type": "application/json"}
            )
            status_code = response.status_code
            status_text = response.text[:200] if response.text else None
            await update_webhook_status(db_client, document_id, status_code, status_text)
            logging.info(f"Webhook called for {document_id}, status: {status_code}")
    except Exception as e:
        logging.error(f"Webhook error for {document_id}: {e}")
        await update_webhook_status(db_client, document_id, 0, str(e)[:200])

@app.post("/upload-cv", response_model=CVUploadResponse)
async def upload_cv(
    file: Optional[UploadFile] = File(None),
    name: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    notes: Optional[str] = Form(None)
):
    if not file and not any([name, phone, notes]):
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
            "phone": phone,
            "notes": notes
        },
        "processing": {
            "parse_success": parse_success,
            "error_message": error_message
        }
    }

    inserted_id = await insert_cv_document(db_client, document)
    
    # קריאה ל-webhook אחרי השמירה
    await call_webhook(inserted_id)
    
    return {"id": str(inserted_id), "status": "stored"}

@app.get("/cv")
async def get_all():
    return await get_all_documents(db_client)

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

# אפשרות להרצה ישירה עבור Render, Heroku או לוקאלי:
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
