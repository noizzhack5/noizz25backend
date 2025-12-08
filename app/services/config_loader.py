"""
טעינת קונפיגורציה של שירותים חיצוניים
"""
import json
import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

class ConfigError(Exception):
    """שגיאה בטעינת קונפיגורציה"""
    pass

def load_services_config() -> Dict:
    """
    טוען את הגדרות השירותים החיצוניים מקובץ services_config.json
    מחזיר dict עם base_url ו-webhook paths
    מעלה ConfigError אם הקובץ לא קיים או אם חסרים ערכים
    """
    config_path = Path("services_config.json")
    
    if not config_path.exists():
        error_msg = f"services_config.json not found at {config_path.absolute()}"
        logger.error(f"[CONFIG] {error_msg}")
        raise ConfigError(error_msg)
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        error_msg = f"Error parsing services_config.json: {str(e)}"
        logger.error(f"[CONFIG] {error_msg}")
        raise ConfigError(error_msg)
    except Exception as e:
        error_msg = f"Error loading services_config.json: {str(e)}"
        logger.error(f"[CONFIG] {error_msg}")
        raise ConfigError(error_msg)
    
    # ודא שיש את כל הערכים הנדרשים
    webhooks_config = config.get("webhooks")
    if not webhooks_config:
        error_msg = "Missing 'webhooks' section in services_config.json"
        logger.error(f"[CONFIG] {error_msg}")
        raise ConfigError(error_msg)
    
    required_fields = ["base_url", "bot_processor", "classification_processor", "upload_cv"]
    missing_fields = [field for field in required_fields if not webhooks_config.get(field)]
    
    if missing_fields:
        error_msg = f"Missing required fields in services_config.json webhooks section: {', '.join(missing_fields)}"
        logger.error(f"[CONFIG] {error_msg}")
        raise ConfigError(error_msg)
    
    result = {
        "webhooks": {
            "base_url": webhooks_config["base_url"],
            "bot_processor": webhooks_config["bot_processor"],
            "classification_processor": webhooks_config["classification_processor"],
            "upload_cv": webhooks_config["upload_cv"]
        }
    }
    
    logger.info(f"[CONFIG] Loaded services config from {config_path}")
    return result

def get_webhook_url(webhook_name: str) -> str:
    """
    מחזיר URL מלא של webhook לפי שם
    
    Args:
        webhook_name: שם ה-webhook (bot_processor, classification_processor, upload_cv)
    
    Returns:
        URL מלא של ה-webhook
    
    Raises:
        ConfigError: אם הקונפיגורציה לא תקינה או אם webhook_name לא נמצא
    """
    config = load_services_config()
    base_url = config["webhooks"]["base_url"]
    webhook_path = config["webhooks"].get(webhook_name)
    
    if not webhook_path:
        error_msg = f"Webhook '{webhook_name}' not found in services_config.json"
        logger.error(f"[CONFIG] {error_msg}")
        raise ConfigError(error_msg)
    
    # ודא שה-base_url לא מסתיים ב-/ וה-webhook_path לא מתחיל ב-/
    base_url = base_url.rstrip("/")
    webhook_path = webhook_path.lstrip("/")
    
    return f"{base_url}/{webhook_path}"

