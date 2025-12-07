from typing import Any, List, Optional
from bson import ObjectId

COLLECTION_NAME = "basicHR"

async def insert_cv_document(db, doc: dict) -> str:
    doc["is_deleted"] = False
    doc["status"] = "received"  # סטטוס ראשוני: נקלט
    res = await db[COLLECTION_NAME].insert_one(doc)
    return str(res.inserted_id)

async def update_document_status(db, id: str, status: str) -> bool:
    """מעדכן את סטטוס המסמך"""
    res = await db[COLLECTION_NAME].update_one(
        {"_id": ObjectId(id)},
        {"$set": {"status": status}}
    )
    return res.modified_count > 0

async def get_all_documents(db, deleted: Optional[bool] = None) -> List[dict]:
    """
    מחזיר את כל המסמכים
    deleted: None/False - רק לא מחוקים (ברירת מחדל)
                   True - רק מחוקים
    """
    # בנה את ה-query בהתאם לפרמטר
    if deleted is True:
        # רק מחוקים
        query = {"is_deleted": True}
    elif deleted is False or deleted is None:
        # רק לא מחוקים (ברירת מחדל)
        query = {"is_deleted": {"$ne": True}}
    else:
        # אם משהו לא צפוי, ברירת מחדל - רק לא מחוקים
        query = {"is_deleted": {"$ne": True}}
    
    docs = []
    async for doc in db[COLLECTION_NAME].find(query):
        doc["id"] = str(doc["_id"])
        doc.pop("_id", None)
        docs.append(doc)
    return docs

async def get_document_by_id(db, id: str) -> Optional[dict]:
    doc = await db[COLLECTION_NAME].find_one({"_id": ObjectId(id), "is_deleted": {"$ne": True}})
    if doc:
        doc["id"] = str(doc["_id"])
        doc.pop("_id", None)
    return doc

async def delete_document_by_id(db, id: str) -> bool:
    res = await db[COLLECTION_NAME].update_one({"_id": ObjectId(id)}, {"$set": {"is_deleted": True}})
    return res.modified_count > 0

async def update_webhook_status(db, id: str, status_code: int, status_text: str = None) -> bool:
    """מעדכן את סטטוס ה-webhook במסמך"""
    update_data = {"webhook_status": {"status_code": status_code}}
    if status_text:
        update_data["webhook_status"]["status_text"] = status_text
    res = await db[COLLECTION_NAME].update_one(
        {"_id": ObjectId(id)},
        {"$set": update_data}
    )
    return res.modified_count > 0

async def update_document_partial(db, id: str, update_data: dict) -> bool:
    """מעדכן מסמך - רק שדות שלא קיימים או ריקים"""
    # קבל את המסמך הנוכחי
    doc = await db[COLLECTION_NAME].find_one({"_id": ObjectId(id), "is_deleted": {"$ne": True}})
    if not doc:
        return False
    
    # בנה את ה-update - רק שדות שלא קיימים או ריקים
    set_updates = {}
    
    # שדות ב-known_data
    known_data_updates = {}
    if "known_data" not in doc:
        doc["known_data"] = {}
    
    # כל השדות הנוספים יישמרו תחת known_data
    # השדות המשותפים (phone_number, email) - מעדכן רק אם לא קיימים או ריקים
    # שאר השדות - מעדכן רק אם לא קיימים או ריקים
    
    all_fields = [
        "latin_name", "hebrew_name", "phone_number", "email",
        "age", "nationality", "can_travel_europe", 
        "can_visit_israel", "lives_in_europe", "native_israeli",
        "english_level", "remembers_job_application", "skills_summary"
    ]
    
    for field in all_fields:
        if field in update_data:
            # עבור שדות ריקים - עדכן רק אם לא קיים
            # עבור שדות עם ערך - עדכן רק אם לא קיים או ריק
            value = update_data[field]
            current_value = doc.get("known_data", {}).get(field)
            
            # אם הערך ריק (""), עדכן רק אם השדה לא קיים
            if value == "":
                if current_value is None:
                    known_data_updates[field] = value
            # אם יש ערך, עדכן רק אם לא קיים או ריק
            elif value:
                if not current_value or current_value == "":
                    known_data_updates[field] = value
    
    # טיפול מיוחד: phone -> phone_number
    if "phone" in update_data and update_data["phone"]:
        current_phone_number = doc.get("known_data", {}).get("phone_number")
        if not current_phone_number or current_phone_number == "":
            known_data_updates["phone_number"] = update_data["phone"]
    
    # אם אין מה לעדכן, החזר True (כבר קיים)
    if not set_updates and not known_data_updates:
        return True
    
    # עדכן את המסמך
    # אם יש known_data_updates, צריך לעשות merge עם known_data הקיים
    if known_data_updates:
        existing_known_data = doc.get("known_data", {})
        existing_known_data.update(known_data_updates)
        set_updates["known_data"] = existing_known_data
    
    res = await db[COLLECTION_NAME].update_one(
        {"_id": ObjectId(id)},
        {"$set": set_updates}
    )
    return res.modified_count > 0

async def search_documents(db, term: str) -> list:
    q = {
        "$and": [
            {"is_deleted": {"$ne": True}},
            {"$or": [
                {"extracted_text": {"$regex": term, "$options": "i"}},
                {"file_metadata.filename": {"$regex": term, "$options": "i"}},
                {"file_metadata.content_type": {"$regex": term, "$options": "i"}},
                {"known_data.name": {"$regex": term, "$options": "i"}},
                {"known_data.phone_number": {"$regex": term, "$options": "i"}},
                {"known_data.email": {"$regex": term, "$options": "i"}},
                {"known_data.notes": {"$regex": term, "$options": "i"}},
                {"processing.error_message": {"$regex": term, "$options": "i"}},
            ]}
        ]
    }
    docs = []
    cursor = db[COLLECTION_NAME].find(q)
    async for doc in cursor:
        doc["id"] = str(doc["_id"])
        doc.pop("_id", None)
        docs.append(doc)
    return docs
