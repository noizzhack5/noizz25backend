"""
Configuration constants and settings
"""
import os
from typing import Optional

# HTTP Configuration
HTTP_SUCCESS_MIN = 200
HTTP_SUCCESS_MAX = 299
HTTP_TIMEOUT_SECONDS = 30.0
RESPONSE_TEXT_MAX_LENGTH = 500
ERROR_MESSAGE_MAX_LENGTH = 100

# Default Port
DEFAULT_PORT = 8000

# MongoDB Configuration
MONGO_URI: str = os.environ.get(
    "MONGO_URI",
    "mongodb+srv://noizz25:noizz25!@cluster0.eccgr2j.mongodb.net/?appName=Cluster0&tlsAllowInvalidCertificates=true"
)
DB_NAME = "noizz25HR"
COLLECTION_NAME = "basicHR"

# CORS Configuration
CORS_ALLOW_ORIGINS = ["*"]  # In production, restrict to specific domains
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ["*"]
CORS_ALLOW_HEADERS = ["*"]

def get_port() -> int:
    """Get the port from environment variable or return default"""
    return int(os.environ.get("PORT", DEFAULT_PORT))

