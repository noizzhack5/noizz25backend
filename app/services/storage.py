from typing import Any, List, Optional
from bson import ObjectId

COLLECTION_NAME = "basicHR"

async def insert_cv_document(db, doc: dict) -> str:
    doc["is_deleted"] = False
    res = await db[COLLECTION_NAME].insert_one(doc)
    return str(res.inserted_id)

async def get_all_documents(db) -> List[dict]:
    docs = []
    async for doc in db[COLLECTION_NAME].find({"is_deleted": {"$ne": True}}):
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

async def search_documents(db, term: str) -> list:
    q = {
        "$and": [
            {"is_deleted": {"$ne": True}},
            {"$or": [
                {"extracted_text": {"$regex": term, "$options": "i"}},
                {"file_metadata.filename": {"$regex": term, "$options": "i"}},
                {"file_metadata.content_type": {"$regex": term, "$options": "i"}},
                {"known_data.name": {"$regex": term, "$options": "i"}},
                {"known_data.phone": {"$regex": term, "$options": "i"}},
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
