from pydantic import BaseModel, Field
from typing import Optional, Any

class FileMetadataModel(BaseModel):
    filename: str
    size_bytes: int
    content_type: str
    uploaded_at: str

class KnownDataModel(BaseModel):
    name: Optional[str]
    phone: Optional[str]
    notes: Optional[str]

class ProcessingModel(BaseModel):
    parse_success: bool
    error_message: Optional[str] = None

class CVDocumentInDB(BaseModel):
    id: Optional[Any] = Field(alias="_id")
    file_metadata: Optional[FileMetadataModel] = None
    extracted_text: Optional[str] = ""
    known_data: KnownDataModel
    processing: ProcessingModel

class CVUploadResponse(BaseModel):
    id: str
    status: str
