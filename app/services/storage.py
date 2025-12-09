"""
Storage service for CV documents
This module provides database operations for CV documents
Maintains backward compatibility while using new utilities
"""
from typing import Any, List, Optional
from bson import ObjectId
import datetime
from app.core.constants import STATUS_SUBMITTED
from app.core.config import COLLECTION_NAME
from app.utils.data_normalization import normalize_document

# Backward compatibility: keep normalize_unknown_values for existing code
def normalize_unknown_values(doc: dict) -> dict:
    """
    ממיר את כל הערכים "unknown" ב-known_data ל-None
    מטפל גם ב-"Unknown", "UNKNOWN" וכל וריאציות אחרות
    
    Deprecated: Use normalize_document from app.utils.data_normalization instead
    """
    from app.utils.data_normalization import normalize_unknown_values as _normalize
    return _normalize(doc)

async def insert_cv_document(db, doc: dict) -> str:
    doc["is_deleted"] = False
    # צור current_status ו-status_history במקום status
    timestamp = datetime.datetime.utcnow().isoformat() + "Z"
    doc["current_status"] = STATUS_SUBMITTED
    doc["status_history"] = [
        {
            "status": STATUS_SUBMITTED,
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
        # Use normalize_document utility for consistent normalization
        doc = normalize_document(doc)
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
        # Use normalize_document utility for consistent normalization
        doc = normalize_document(doc)
    return doc

async def delete_document_by_id(db, id: str) -> bool:
    res = await db[COLLECTION_NAME].update_one({"_id": ObjectId(id)}, {"$set": {"is_deleted": True}})
    return res.modified_count > 0

async def restore_document_by_id(db, id: str) -> bool:
    """משחזר מסמך שנמחק על ידי עדכון is_deleted ל-False"""
    res = await db[COLLECTION_NAME].update_one({"_id": ObjectId(id)}, {"$set": {"is_deleted": False}})
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
        "job_type", "match_score", "class_explain", "recruit_note"
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

async def update_document_fields_only(db, id: str, update_data: dict) -> bool:
    """מעדכן מסמך - מעדכן רק את השדות שמגיעים ב-update_data"""
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
    
    # הסר את phone_number - לא ניתן לעדכן 
    update_data.pop("phone_number", None)
    
    # אם אין שדות לעדכון, החזר True
    if not update_data:
        return True
    
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
        "job_type", "match_score", "class_explain", "recruit_note"
    ]
    
    # עדכן רק את השדות שמגיעים ב-update_data
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
        # Use normalize_document utility for consistent normalization
        doc = normalize_document(doc)
        docs.append(doc)
    return docs

async def search_documents_advanced(
    db,
    free_text: Optional[str] = None,
    current_status: Optional[str] = None,
    job_type: Optional[str] = None,
    match_score: Optional[str] = None,
    campaign: Optional[str] = None,
    country: Optional[str] = None
) -> List[dict]:
    """
    חיפוש מתקדם במסמכים
    
    Args:
        free_text: חיפוש חופשי - יחפש את הערך בכל שדה במסמך
        current_status: חיפוש לפי סטטוס נוכחי
        job_type: חיפוש לפי סוג עבודה
        match_score: חיפוש לפי טווח ציון התאמה (below 70, 70-79, 80-89, 90-100, all match_score)
        campaign: חיפוש לפי קמפיין
        country: חיפוש לפי ארץ (nationality)
    
    Returns:
        רשימת מסמכים התואמים לקריטריוני החיפוש
    """
    # התחל עם query בסיסי - רק מסמכים לא מחוקים
    query_conditions = [{"is_deleted": {"$ne": True}}]
    
    # חיפוש חופשי - יחפש בכל השדות
    if free_text:
        free_text_conditions = {
            "$or": [
                {"extracted_text": {"$regex": free_text, "$options": "i"}},
                {"file_metadata.filename": {"$regex": free_text, "$options": "i"}},
                {"known_data.name": {"$regex": free_text, "$options": "i"}},
                {"known_data.phone_number": {"$regex": free_text, "$options": "i"}},
                {"known_data.email": {"$regex": free_text, "$options": "i"}},
                {"known_data.campaign": {"$regex": free_text, "$options": "i"}},
                {"known_data.notes": {"$regex": free_text, "$options": "i"}},
                {"known_data.job_type": {"$regex": free_text, "$options": "i"}},
                {"known_data.match_score": {"$regex": free_text, "$options": "i"}},
                {"known_data.class_explain": {"$regex": free_text, "$options": "i"}},
                {"known_data.latin_name": {"$regex": free_text, "$options": "i"}},
                {"known_data.hebrew_name": {"$regex": free_text, "$options": "i"}},
                {"known_data.nationality": {"$regex": free_text, "$options": "i"}},
                {"current_status": {"$regex": free_text, "$options": "i"}},
            ]
        }
        query_conditions.append(free_text_conditions)
    
    # חיפוש לפי שדות ספציפיים
    if current_status:
        query_conditions.append({"current_status": current_status})
    
    if job_type:
        query_conditions.append({"known_data.job_type": {"$regex": job_type, "$options": "i"}})
    
    if match_score:
        # טיפול מיוחד ב-match_score - טווחים
        match_score_conditions = []
        
        if match_score == "below 70":
            # כל הערכים מתחת ל-70: 0-69
            # נשתמש ב-regex patterns לכל המספרים מ-0 עד 69
            match_score_conditions = [
                {"known_data.match_score": {"$regex": r"^[0-6][0-9]$", "$options": "i"}},  # 00-69
                {"known_data.match_score": {"$regex": r"^[0-9]$", "$options": "i"}},  # 0-9
            ]
        elif match_score == "70-79":
            match_score_conditions = [
                {"known_data.match_score": {"$regex": r"^7[0-9]$", "$options": "i"}},
            ]
        elif match_score == "80-89":
            match_score_conditions = [
                {"known_data.match_score": {"$regex": r"^8[0-9]$", "$options": "i"}},
            ]
        elif match_score == "90-100":
            match_score_conditions = [
                {"known_data.match_score": {"$regex": r"^(9[0-9]|100)$", "$options": "i"}},
            ]
        elif match_score == "all match_score":
            # כל המסמכים שיש להם match_score (לא None)
            match_score_conditions = [
                {"known_data.match_score": {"$exists": True, "$ne": None}},
            ]
        
        if match_score_conditions:
            query_conditions.append({"$or": match_score_conditions})
    
    if campaign:
        query_conditions.append({"known_data.campaign": {"$regex": campaign, "$options": "i"}})
    
    if country:
        query_conditions.append({"known_data.nationality": {"$regex": country, "$options": "i"}})
    
    # בנה את ה-query הסופי
    query = {"$and": query_conditions} if len(query_conditions) > 1 else query_conditions[0]
    
    docs = []
    cursor = db[COLLECTION_NAME].find(query)
    async for doc in cursor:
        # טיפול מיוחד ב-match_score עבור "below 70" - סינון נוסף למקרים שלא נתפסו ב-regex
        if match_score == "below 70":
            match_score_value = doc.get("known_data", {}).get("match_score")
            if match_score_value is not None:
                score_str = str(match_score_value).strip()
                try:
                    # נסה להמיר למספר לבדיקה מדויקת
                    score_num = float(score_str)
                    if score_num >= 70:
                        continue  # דלג על מסמך זה
                except (ValueError, TypeError):
                    # אם לא ניתן להמיר, נבדוק אם זה מספר בעל 3 ספרות או יותר (100+)
                    if len(score_str) >= 3:
                        continue  # כנראה 100 או יותר
                    # אחרת, נכלול אותו (יכול להיות משהו כמו "65.5" או ערך לא מספרי)
        
        doc["id"] = str(doc["_id"])
        doc.pop("_id", None)
        # Use normalize_document utility for consistent normalization
        doc = normalize_document(doc)
        docs.append(doc)
    
    return docs