"""
Chat service for retrieving chat history
"""
from typing import Optional, Dict, Any
from bson import ObjectId


async def get_chat_history_by_id(db, user_id: str) -> Optional[Dict[str, Any]]:
    """
    מחזיר את היסטוריית הצ'אט של משתמש לפי ID
    
    Args:
        db: MongoDB database instance
        user_id: מזהה המשתמש (יכול להיות ObjectId, phone_number, או string ID)
    
    Returns:
        Dictionary עם היסטוריית הצ'אט או None אם לא נמצא
    """
    # חיפוש באוסף WhatsAPP_DB בלבד
    chat_collection = db["WhatsAPP_DB"]
    
    # נסה למצוא לפי phone_number
    chat_doc = await chat_collection.find_one({"phone_number": user_id})
    
    # אם לא נמצא, נסה למצוא לפי _id (ObjectId)
    if not chat_doc:
        try:
            chat_doc = await chat_collection.find_one({"_id": ObjectId(user_id)})
        except Exception:
            pass
    
    # אם עדיין לא נמצא, נסה למצוא לפי user_id
    if not chat_doc:
        chat_doc = await chat_collection.find_one({"user_id": user_id})
    
    # אם עדיין לא נמצא, נסה למצוא לפי id (string)
    if not chat_doc:
        chat_doc = await chat_collection.find_one({"id": user_id})
    
    # אם עדיין לא נמצא, נסה למצוא לפי candidate_id
    if not chat_doc:
        chat_doc = await chat_collection.find_one({"candidate_id": user_id})
    
    # אם נמצא, החזר רק את השדה chat_history
    if chat_doc:
        chat_history = chat_doc.get("chat_history")
        if chat_history is not None:
            return {"chat_history": chat_history}
        # אם אין chat_history, החזר רשימה ריקה
        return {"chat_history": []}
    
    return None

