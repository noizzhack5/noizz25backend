from fastapi import FastAPI, File, UploadFile, Form, HTTPException, status
from fastapi.responses import JSONResponse
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient
from app.models import CVDocumentInDB, CVUploadResponse
from app.database import get_database
from app.services.pdf_parser import extract_text_from_pdf
from app.services.storage import insert_cv_document, get_all_documents, get_document_by_id, delete_document_by_id
import datetime
import os

app = FastAPI()

db_client = None

@app.on_event("startup")
async def startup_event():
    global db_client
    db_client = get_database()

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
