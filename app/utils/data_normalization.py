"""
Data normalization utilities
"""
from typing import Dict, Any, List


def normalize_unknown_values(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert all "unknown" values in known_data to None
    Handles variations: "unknown", "Unknown", "UNKNOWN", etc.
    
    Args:
        doc: Document dictionary
        
    Returns:
        Document with normalized values
    """
    if "known_data" in doc and isinstance(doc["known_data"], dict):
        for key, value in doc["known_data"].items():
            if isinstance(value, str) and value.lower() == "unknown":
                doc["known_data"][key] = None
    return doc


def ensure_required_fields(doc: Dict[str, Any], required_fields: List[str]) -> Dict[str, Any]:
    """
    Ensure required fields exist in known_data with None as default
    
    Args:
        doc: Document dictionary
        required_fields: List of field names that must exist
        
    Returns:
        Document with all required fields present
    """
    if "known_data" not in doc:
        doc["known_data"] = {}
    
    for field in required_fields:
        if field not in doc["known_data"]:
            doc["known_data"][field] = None
    
    return doc


def normalize_document(doc: Dict[str, Any], required_fields: List[str] = None) -> Dict[str, Any]:
    """
    Normalize a document by converting unknown values and ensuring required fields
    
    Args:
        doc: Document dictionary
        required_fields: Optional list of required fields (default: job_type, match_score, class_explain)
        
    Returns:
        Normalized document
    """
    if required_fields is None:
        required_fields = ["job_type", "match_score", "class_explain"]
    
    doc = normalize_unknown_values(doc)
    doc = ensure_required_fields(doc, required_fields)
    return doc

