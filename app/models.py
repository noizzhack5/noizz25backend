from pydantic import BaseModel, Field
from typing import Optional, Any, List
from app.constants import DocumentStatus

class FileMetadataModel(BaseModel):
    filename: str
    size_bytes: int
    content_type: str
    uploaded_at: str

class KnownDataModel(BaseModel):
    name: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    campaign: Optional[str]
    notes: Optional[str]
    job_type: Optional[str] = None
    match_score: Optional[str] = None
    class_explain: Optional[str] = None

class StatusHistoryItem(BaseModel):
    status: str
    timestamp: str

class CVDocumentInDB(BaseModel):
    id: Optional[Any] = Field(alias="_id")
    file_metadata: Optional[FileMetadataModel] = None
    extracted_text: Optional[str] = ""
    known_data: KnownDataModel
    current_status: str
    status_history: List[StatusHistoryItem]

class CVUploadResponse(BaseModel):
    id: str
    status: str

class StatusUpdateRequest(BaseModel):
    """Model לעדכון סטטוס מסמך"""
    status: DocumentStatus = Field(..., description="הסטטוס החדש לעדכון - חייב להיות אחד מהסטטוסים התקפים")

class CVUpdateRequest(BaseModel):
    """Model לעדכון מסמך CV - כל השדות אופציונליים"""
    latin_name: Optional[str] = Field(default=None, description="שם לטיני")
    hebrew_name: Optional[str] = Field(default=None, description="שם עברי")
    phone_number: Optional[str] = Field(default=None, description="מספר טלפון")
    phone: Optional[str] = Field(default=None, description="מספר טלפון (יומר ל-phone_number)")
    email: Optional[str] = Field(default=None, description="כתובת אימייל")
    campaign: Optional[str] = Field(default=None, description="קמפיין")
    age: Optional[str] = Field(default=None, description="גיל")
    nationality: Optional[str] = Field(default=None, description="לאום")
    can_travel_europe: Optional[str] = Field(default=None, description="יכול לנסוע לאירופה")
    can_visit_israel: Optional[str] = Field(default=None, description="יכול לבקר בישראל")
    lives_in_europe: Optional[str] = Field(default=None, description="גר באירופה")
    native_israeli: Optional[str] = Field(default=None, description="ישראלי יליד")
    english_level: Optional[str] = Field(default=None, description="רמת אנגלית")
    remembers_job_application: Optional[str] = Field(default=None, description="זוכר את בקשת העבודה")
    skills_summary: Optional[str] = Field(default=None, description="סיכום כישורים")
    job_type: Optional[str] = Field(default=None, description="סוג עבודה")
    match_score: Optional[str] = Field(default=None, description="ציון התאמה")
    class_explain: Optional[str] = Field(default=None, description="הסבר קלאסיפיקציה")
    
    class Config:
        json_schema_extra = {
            "example": {
                "latin_name": "John Doe",
                "hebrew_name": "יוחנן דו",
                "phone_number": "+1234567890",
                "email": "example@email.com",
                "campaign": "Summer 2024",
                "age": "30",
                "nationality": "Israeli",
                "can_travel_europe": "yes",
                "can_visit_israel": "yes",
                "lives_in_europe": "no",
                "native_israeli": "yes",
                "english_level": "Advanced",
                "remembers_job_application": "yes",
                "skills_summary": "Experienced professional with expertise in various fields. Strong background in technical and interpersonal skills."
            }
        }
