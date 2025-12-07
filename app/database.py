import os
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URI = "mongodb+srv://noizz25:noizz25!@cluster0.eccgr2j.mongodb.net/?appName=Cluster0&tlsAllowInvalidCertificates=true"
DB_NAME = "noizz25HR"
COLLECTION_NAME = "basicHR"


def get_database():
    client = AsyncIOMotorClient(MONGO_URI)
    return client[DB_NAME]
