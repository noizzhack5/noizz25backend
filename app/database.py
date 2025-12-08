"""
Database connection module
Uses configuration from app.core.config
"""
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import MONGO_URI, DB_NAME, COLLECTION_NAME

# Re-export for backward compatibility
__all__ = ['get_database', 'MONGO_URI', 'DB_NAME', 'COLLECTION_NAME']


def get_database():
    """
    Get MongoDB database instance
    
    Returns:
        MongoDB database instance
    """
    client = AsyncIOMotorClient(MONGO_URI)
    return client[DB_NAME]
