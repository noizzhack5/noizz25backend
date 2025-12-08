"""
Repository for CV document database operations
This layer abstracts database access and provides clean interfaces
"""
from typing import List, Optional, Dict, Any
from bson import ObjectId
import datetime
from app.core.config import COLLECTION_NAME
from app.core.constants import STATUS_SUBMITTED
from app.utils.data_normalization import normalize_document


class CVRepository:
    """Repository for CV document operations"""
    
    def __init__(self, db):
        """
        Initialize repository with database connection
        
        Args:
            db: MongoDB database instance
        """
        self.db = db
        self.collection = db[COLLECTION_NAME]
    
    async def insert(self, doc: Dict[str, Any]) -> str:
        """
        Insert a new CV document
        
        Args:
            doc: Document dictionary to insert
            
        Returns:
            Inserted document ID as string
        """
        doc["is_deleted"] = False
        timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        doc["current_status"] = STATUS_SUBMITTED
        doc["status_history"] = [
            {
                "status": STATUS_SUBMITTED,
                "timestamp": timestamp
            }
        ]
        result = await self.collection.insert_one(doc)
        return str(result.inserted_id)
    
    async def find_by_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Find a document by ID (returns deleted documents too)
        
        Args:
            document_id: Document ID as string
            
        Returns:
            Document dictionary or None if not found
        """
        try:
            doc = await self.collection.find_one({"_id": ObjectId(document_id)})
            if doc:
                doc["id"] = str(doc["_id"])
                doc.pop("_id", None)
                doc = normalize_document(doc)
            return doc
        except Exception:
            return None
    
    async def find_all(self, deleted: Optional[bool] = None) -> List[Dict[str, Any]]:
        """
        Find all documents with optional filter for deleted status
        
        Args:
            deleted: None/False - only non-deleted (default)
                    True - only deleted
            
        Returns:
            List of document dictionaries
        """
        # Build query based on deleted parameter
        if deleted is True:
            query = {"is_deleted": True}
        else:
            query = {"is_deleted": {"$ne": True}}
        
        docs = []
        async for doc in self.collection.find(query):
            doc["id"] = str(doc["_id"])
            doc.pop("_id", None)
            doc = normalize_document(doc)
            docs.append(doc)
        return docs
    
    async def find_by_status(self, status: str) -> List[Dict[str, Any]]:
        """
        Find all documents with a specific status
        
        Args:
            status: Status string to filter by
            
        Returns:
            List of document dictionaries
        """
        query = {
            "current_status": status,
            "is_deleted": {"$ne": True}
        }
        docs = []
        async for doc in self.collection.find(query):
            doc["id"] = str(doc["_id"])
            doc.pop("_id", None)
            doc = normalize_document(doc)
            docs.append(doc)
        return docs
    
    async def search(self, search_term: str) -> List[Dict[str, Any]]:
        """
        Search documents by text term
        
        Args:
            search_term: Text to search for
            
        Returns:
            List of matching document dictionaries
        """
        query = {
            "$and": [
                {"is_deleted": {"$ne": True}},
                {"$or": [
                    {"extracted_text": {"$regex": search_term, "$options": "i"}},
                    {"file_metadata.filename": {"$regex": search_term, "$options": "i"}},
                    {"file_metadata.content_type": {"$regex": search_term, "$options": "i"}},
                    {"known_data.name": {"$regex": search_term, "$options": "i"}},
                    {"known_data.phone_number": {"$regex": search_term, "$options": "i"}},
                    {"known_data.email": {"$regex": search_term, "$options": "i"}},
                    {"known_data.campaign": {"$regex": search_term, "$options": "i"}},
                    {"known_data.notes": {"$regex": search_term, "$options": "i"}},
                    {"known_data.job_type": {"$regex": search_term, "$options": "i"}},
                    {"known_data.match_score": {"$regex": search_term, "$options": "i"}},
                    {"known_data.class_explain": {"$regex": search_term, "$options": "i"}},
                    {"current_status": {"$regex": search_term, "$options": "i"}},
                ]}
            ]
        }
        
        docs = []
        async for doc in self.collection.find(query):
            doc["id"] = str(doc["_id"])
            doc.pop("_id", None)
            doc = normalize_document(doc)
            docs.append(doc)
        return docs
    
    async def update_status(self, document_id: str, status: str) -> bool:
        """
        Update document status (current_status and status_history)
        
        Args:
            document_id: Document ID as string
            status: New status string
            
        Returns:
            True if update was successful, False otherwise
        """
        timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        status_entry = {
            "status": status,
            "timestamp": timestamp
        }
        
        result = await self.collection.update_one(
            {"_id": ObjectId(document_id)},
            {
                "$set": {"current_status": status},
                "$push": {"status_history": status_entry}
            }
        )
        return result.modified_count > 0
    
    async def add_status_to_history(self, document_id: str, status: str) -> bool:
        """
        Add status to history without updating current_status
        
        Args:
            document_id: Document ID as string
            status: Status string to add to history
            
        Returns:
            True if update was successful, False otherwise
        """
        timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        status_entry = {
            "status": status,
            "timestamp": timestamp
        }
        
        result = await self.collection.update_one(
            {"_id": ObjectId(document_id)},
            {"$push": {"status_history": status_entry}}
        )
        return result.modified_count > 0
    
    async def update_fields(self, document_id: str, update_data: Dict[str, Any]) -> bool:
        """
        Update only the fields provided in update_data
        
        Args:
            document_id: Document ID as string
            update_data: Dictionary of fields to update
            
        Returns:
            True if update was successful, False otherwise
        """
        # Check document exists and is not deleted
        doc = await self.collection.find_one({
            "_id": ObjectId(document_id),
            "is_deleted": {"$ne": True}
        })
        if not doc:
            return False
        
        # Normalize unknown values
        update_data = update_data.copy()
        for key, value in update_data.items():
            if isinstance(value, str) and value.lower() == "unknown":
                update_data[key] = None
        
        # Remove protected fields
        update_data.pop("status", None)
        update_data.pop("current_status", None)
        update_data.pop("status_history", None)
        update_data.pop("phone_number", None)
        
        if not update_data:
            return True
        
        # Build update for known_data fields
        known_data_updates = {}
        if "known_data" not in doc:
            doc["known_data"] = {}
        
        # All additional fields are stored under known_data
        all_fields = [
            "latin_name", "hebrew_name", "email", "campaign",
            "age", "nationality", "can_travel_europe",
            "can_visit_israel", "lives_in_europe", "native_israeli",
            "english_level", "remembers_job_application", "skills_summary",
            "job_type", "match_score", "class_explain"
        ]
        
        # Update only fields present in update_data
        for field in all_fields:
            if field in update_data:
                value = update_data[field]
                if isinstance(value, str) and value.lower() == "unknown":
                    value = None
                known_data_updates[field] = value
        
        if not known_data_updates:
            return True
        
        # Merge with existing known_data
        existing_known_data = doc.get("known_data", {})
        existing_known_data.update(known_data_updates)
        
        result = await self.collection.update_one(
            {"_id": ObjectId(document_id)},
            {"$set": {"known_data": existing_known_data}}
        )
        return result.modified_count > 0
    
    async def delete(self, document_id: str) -> bool:
        """
        Soft delete a document (set is_deleted to True)
        
        Args:
            document_id: Document ID as string
            
        Returns:
            True if update was successful, False otherwise
        """
        result = await self.collection.update_one(
            {"_id": ObjectId(document_id)},
            {"$set": {"is_deleted": True}}
        )
        return result.modified_count > 0
    
    async def restore(self, document_id: str) -> bool:
        """
        Restore a deleted document (set is_deleted to False)
        
        Args:
            document_id: Document ID as string
            
        Returns:
            True if update was successful, False otherwise
        """
        result = await self.collection.update_one(
            {"_id": ObjectId(document_id)},
            {"$set": {"is_deleted": False}}
        )
        return result.modified_count > 0

