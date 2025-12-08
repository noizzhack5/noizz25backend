from typing import Any, List, Optional
from bson import ObjectId
import datetime
from app.constants import STATUS_RECEIVED

COLLECTION_NAME = "basicHR"

def normalize_unknown_values(doc: dict) -> dict:
    """
    ממיר את כל הערכים "unknown" ב-known_data ל-None
    מטפל גם ב-"Unknown", "UNKNOWN" וכל וריאציות אחרות
    """
    if "known_data" in doc and isinstance(doc["known_data"], dict):
        for key, value in doc["known_data"].items():
            # המר "unknown" (בכל וריאציה) ל-None
            if isinstance(value, str) and value.lower() == "unknown":
                doc["known_data"][key] = None
    return doc

async def insert_cv_document(db, doc: dict) -> str:
    doc["is_deleted"] = False
    # צור current_status ו-status_history במקום status
    timestamp = datetime.datetime.utcnow().isoformat() + "Z"
    doc["current_status"] = STATUS_RECEIVED
    doc["status_history"] = [
        {
            "status": STATUS_RECEIVED,
            "timestamp": timestamp
        }
    ]
    res = await db[COLLECTION_NAME].insert_one(doc)
    return str(res.inserted_id)

async def update_document_status(db, id: str, status: str) -> bool:
    """
    מעדכן את סטטוס המסמך
    מעדכן את current_status ומוסיף את הסטטוס החדש ל-status_history
    """
    timestamp = datetime.datetime.utcnow().isoformat() + "Z"
    status_entry = {
        "status": status,
        "timestamp": timestamp
    }
    
    res = await db[COLLECTION_NAME].update_one(
        {"_id": ObjectId(id)},
        {
            "$set": {"current_status": status},
            "$push": {"status_history": status_entry}
        }
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
        # וודא שהשדות job_type, match_score, class_explain קיימים תחת known_data (עם None אם לא קיימים)
        if "known_data" not in doc:
            doc["known_data"] = {}
        for field in ["job_type", "match_score", "class_explain"]:
            if field not in doc["known_data"]:
                doc["known_data"][field] = None
        # המר "unknown" ל-None
        doc = normalize_unknown_values(doc)
        docs.append(doc)
    return docs

async def get_document_by_id(db, id: str) -> Optional[dict]:
    """
    מחזיר מסמך לפי מזהה - ללא בדיקת is_deleted (מחזיר גם מסמכים מחוקים)
    """
    doc = await db[COLLECTION_NAME].find_one({"_id": ObjectId(id)})
    if doc:
        doc["id"] = str(doc["_id"])
        doc.pop("_id", None)
        # וודא שהשדות job_type, match_score, class_explain קיימים תחת known_data (עם None אם לא קיימים)
        if "known_data" not in doc:
            doc["known_data"] = {}
        for field in ["job_type", "match_score", "class_explain"]:
            if field not in doc["known_data"]:
                doc["known_data"][field] = None
        # המר "unknown" ל-None
        doc = normalize_unknown_values(doc)
    return doc

async def delete_document_by_id(db, id: str) -> bool:
    res = await db[COLLECTION_NAME].update_one({"_id": ObjectId(id)}, {"$set": {"is_deleted": True}})
    return res.modified_count > 0

async def add_status_to_history(db, id: str, status: str) -> bool:
    """
    מוסיף סטטוס ל-status_history (ללא עדכון current_status)
    משמש להוספת סטטוסים כמו webhook_status, processing וכו'
    """
    timestamp = datetime.datetime.utcnow().isoformat() + "Z"
    status_entry = {
        "status": status,
        "timestamp": timestamp
    }
    
    res = await db[COLLECTION_NAME].update_one(
        {"_id": ObjectId(id)},
        {"$push": {"status_history": status_entry}}
    )
    return res.modified_count > 0

async def update_document_full(db, id: str, update_data: dict) -> bool:
    """מעדכן מסמך - מעדכן את כל השדות תמיד (למעט phone_number)"""
    # קבל את המסמך הנוכחי
    doc = await db[COLLECTION_NAME].find_one({"_id": ObjectId(id), "is_deleted": {"$ne": True}})
    if not doc:
        return False
    
    # המר "unknown" ל-None בכל הערכים ב-update_data לפני העיבוד
    update_data = update_data.copy()  # עותק כדי לא לשנות את המקורי
    for key, value in update_data.items():
        if isinstance(value, str) and value.lower() == "unknown":
            update_data[key] = None
    
    # הסר שדות שצריכים להיות מעודכנים רק דרך update_document_status
    # כדי למנוע עדכון ישיר של status, current_status או status_history
    update_data.pop("status", None)
    update_data.pop("current_status", None)
    update_data.pop("status_history", None)
    
    # הסר את phone_number ו-phone - לא ניתן לעדכן אותם
    update_data.pop("phone_number", None)
    update_data.pop("phone", None)
    
    # בנה את ה-update
    set_updates = {}
    
    # שדות ב-known_data
    known_data_updates = {}
    if "known_data" not in doc:
        doc["known_data"] = {}
    
    # כל השדות הנוספים יישמרו תחת known_data
    all_fields = [
        "latin_name", "hebrew_name", "email", "campaign",
        "age", "nationality", "can_travel_europe", 
        "can_visit_israel", "lives_in_europe", "native_israeli",
        "english_level", "remembers_job_application", "skills_summary",
        "job_type", "match_score", "class_explain"
    ]
    
    # עדכן את כל השדות תמיד (למעט phone_number שכבר הוסר)
    for field in all_fields:
        if field in update_data:
            # המר "unknown" ל-None אם זה string
            value = update_data[field]
            if isinstance(value, str) and value.lower() == "unknown":
                value = None
            known_data_updates[field] = value
    
    # אם אין מה לעדכן, החזר True
    if not known_data_updates:
        return True
    
    # עדכן את המסמך
    # אם יש known_data_updates, צריך לעשות merge עם known_data הקיים
    existing_known_data = doc.get("known_data", {})
    existing_known_data.update(known_data_updates)
    set_updates["known_data"] = existing_known_data
    
    # ודא שלא מעדכנים status, current_status או status_history ישירות
    set_updates.pop("status", None)
    set_updates.pop("current_status", None)
    set_updates.pop("status_history", None)
    
    res = await db[COLLECTION_NAME].update_one(
        {"_id": ObjectId(id)},
        {"$set": set_updates}
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
        "latin_name", "hebrew_name", "phone_number", "email", "campaign",
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
    
    # שדות job_type, match_score, class_explain נשמרים תמיד, גם אם הם None/NULL
    # הם חלק מ-known_data, אבל נשמרים תמיד (לא רק אם לא קיימים)
    always_update_fields = ["job_type", "match_score", "class_explain"]
    for field in always_update_fields:
        if field in update_data:
            # שמור את הערך גם אם הוא None
            known_data_updates[field] = update_data[field] if update_data[field] is not None else None
    
    # אם אין מה לעדכן, החזר True (כבר קיים)
    if not set_updates and not known_data_updates:
        return True
    
    # עדכן את המסמך
    # אם יש known_data_updates, צריך לעשות merge עם known_data הקיים
    if known_data_updates:
        existing_known_data = doc.get("known_data", {})
        existing_known_data.update(known_data_updates)
        set_updates["known_data"] = existing_known_data
    
    # ודא שלא מעדכנים status, current_status או status_history ישירות
    # אלה צריכים להיות מעודכנים רק דרך update_document_status או add_status_to_history
    set_updates.pop("status", None)
    set_updates.pop("current_status", None)
    set_updates.pop("status_history", None)
    
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
                {"known_data.campaign": {"$regex": term, "$options": "i"}},
                {"known_data.notes": {"$regex": term, "$options": "i"}},
                {"known_data.job_type": {"$regex": term, "$options": "i"}},
                {"known_data.match_score": {"$regex": term, "$options": "i"}},
                {"known_data.class_explain": {"$regex": term, "$options": "i"}},
                {"current_status": {"$regex": term, "$options": "i"}},
            ]}
        ]
    }
    docs = []
    cursor = db[COLLECTION_NAME].find(q)
    async for doc in cursor:
        doc["id"] = str(doc["_id"])
        doc.pop("_id", None)
        # וודא שהשדות job_type, match_score, class_explain קיימים תחת known_data (עם None אם לא קיימים)
        if "known_data" not in doc:
            doc["known_data"] = {}
        for field in ["job_type", "match_score", "class_explain"]:
            if field not in doc["known_data"]:
                doc["known_data"][field] = None
        # המר "unknown" ל-None
        doc = normalize_unknown_values(doc)
        docs.append(doc)
    return docs

async def get_documents_by_status(db, status: str) -> List[dict]:
    """מחזיר את כל המסמכים עם סטטוס מסוים"""
    query = {
        "current_status": status,
        "is_deleted": {"$ne": True}
    }
    docs = []
    async for doc in db[COLLECTION_NAME].find(query):
        doc["id"] = str(doc["_id"])
        doc.pop("_id", None)
        # וודא שהשדות job_type, match_score, class_explain קיימים תחת known_data (עם None אם לא קיימים)
        if "known_data" not in doc:
            doc["known_data"] = {}
        for field in ["job_type", "match_score", "class_explain"]:
            if field not in doc["known_data"]:
                doc["known_data"][field] = None
        # המר "unknown" ל-None
        doc = normalize_unknown_values(doc)
        docs.append(doc)
    return docs