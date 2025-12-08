"""
Custom exceptions for the application
"""
from fastapi import HTTPException, status


class DocumentNotFoundError(HTTPException):
    """Exception raised when a document is not found"""
    def __init__(self, document_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {document_id}"
        )


class InvalidStatusError(HTTPException):
    """Exception raised when an invalid status is provided"""
    def __init__(self, status_id: int, available_statuses: dict):
        status_list = ", ".join([f"{sid}={sname}" for sid, sname in available_statuses.items()])
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status_id: {status_id}. Available statuses: {status_list}"
        )


class ValidationError(HTTPException):
    """Exception raised when validation fails"""
    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )

