"""
ניהול ה-scheduler וה-jobs שרצים ברקע
"""
import logging
import json
import os
from pathlib import Path
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from app.services.bot_processor import process_waiting_for_bot_records
from app.jobs.classification_processor import process_waiting_classification_records
from app.constants import STATUS_READY_FOR_BOT_INTERVIEW, STATUS_READY_FOR_CLASSIFICATION

logger = logging.getLogger(__name__)

scheduler = None
_db_client = None

def load_scheduler_config():
    """
    טוען את כל הגדרות ה-scheduler מקובץ scheduler_config.json בתיקיית jobs
    מחזיר dict עם כל ההגדרות
    """
    # נתיב לקובץ הקונפיגורציה בתיקיית jobs
    config_path = Path(__file__).parent / "scheduler_config.json"
    default_config = {
        "bot_processor": {
            "enabled": True,
            "hour": 10,
            "minute": 0,
            "timezone": "UTC"
        },
        "classification_processor": {
            "interval_seconds": 10,
            "timezone": "UTC"
        }
    }
    
    if not config_path.exists():
        logger.warning(f"[CONFIG] scheduler_config.json not found at {config_path}, using default values")
        return default_config
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        result = {}
        
        # טען הגדרות bot_processor
        bot_config = config.get("bot_processor", {})
        result["bot_processor"] = {
            "enabled": bot_config.get("enabled", default_config["bot_processor"]["enabled"]),
            "hour": bot_config.get("hour", default_config["bot_processor"]["hour"]),
            "minute": bot_config.get("minute", default_config["bot_processor"]["minute"]),
            "timezone": bot_config.get("timezone", default_config["bot_processor"]["timezone"])
        }
        
        # בדיקת תקינות bot_processor
        if not (0 <= result["bot_processor"]["hour"] <= 23):
            logger.warning(f"[CONFIG] Invalid hour value {result['bot_processor']['hour']}, using default")
            result["bot_processor"]["hour"] = default_config["bot_processor"]["hour"]
        
        if not (0 <= result["bot_processor"]["minute"] <= 59):
            logger.warning(f"[CONFIG] Invalid minute value {result['bot_processor']['minute']}, using default")
            result["bot_processor"]["minute"] = default_config["bot_processor"]["minute"]
        
        # טען הגדרות classification_processor
        classification_config = config.get("classification_processor", {})
        result["classification_processor"] = {
            "interval_seconds": classification_config.get("interval_seconds", default_config["classification_processor"]["interval_seconds"]),
            "timezone": classification_config.get("timezone", default_config["classification_processor"]["timezone"])
        }
        
        # בדיקת תקינות classification_processor
        if result["classification_processor"]["interval_seconds"] <= 0:
            logger.warning(f"[CONFIG] Invalid interval_seconds value {result['classification_processor']['interval_seconds']}, using default")
            result["classification_processor"]["interval_seconds"] = default_config["classification_processor"]["interval_seconds"]
        
        logger.info(f"[CONFIG] Loaded scheduler config: {result}")
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"[CONFIG] Error parsing config.json: {str(e)}, using default values")
        return default_config
    except Exception as e:
        logger.error(f"[CONFIG] Error loading config.json: {str(e)}, using default values")
        return default_config

async def scheduled_bot_processor():
    """פונקציה שרצה על ידי ה-scheduler כל יום לפי ההגדרות"""
    global _db_client
    logger.info("[SCHEDULER] Starting scheduled bot processor job (triggered by daily scheduler)")
    try:
        results = await process_waiting_for_bot_records(_db_client, trigger_source="scheduled")
        logger.info(f"[SCHEDULER] Scheduled job completed: {results}")
    except Exception as e:
        logger.error(f"[SCHEDULER] Error in scheduled job: {str(e)}", exc_info=True)

async def scheduled_classification_processor():
    """פונקציה שרצה על ידי ה-scheduler כל X שניות לפי ההגדרות"""
    global _db_client
    logger.info("[SCHEDULER] Starting scheduled classification processor job (triggered by interval scheduler)")
    try:
        results = await process_waiting_classification_records(_db_client)
        logger.info(f"[SCHEDULER] Classification job completed: {results}")
    except Exception as e:
        logger.error(f"[SCHEDULER] Error in classification job: {str(e)}", exc_info=True)

def setup_scheduler(db_client):
    """
    מגדיר ומתחיל את ה-scheduler
    טוען את הגדרות הזמן מקובץ scheduler_config.json
    """
    global scheduler, _db_client
    _db_client = db_client
    
    # טען את כל הגדרות ה-scheduler מקובץ הקונפיגורציה
    config = load_scheduler_config()
    
    # הגדר timezone (משתמש ב-timezone של bot_processor, או של classification_processor אם לא קיים)
    timezone = config.get("bot_processor", {}).get("timezone") or config.get("classification_processor", {}).get("timezone", "UTC")
    
    scheduler = AsyncIOScheduler(timezone=timezone)
    
    # הוסף job ל-bot_processor (יומי) - רק אם enabled בקונפיגורציה
    bot_config = config.get("bot_processor", {})
    if bot_config.get("enabled", True):
        hour = bot_config.get("hour", 10)
        minute = bot_config.get("minute", 0)
        scheduler.add_job(
            scheduled_bot_processor,
            trigger=CronTrigger(hour=hour, minute=minute),
            id="daily_bot_processor",
            name=f"Process {STATUS_READY_FOR_BOT_INTERVIEW} records daily at {hour:02d}:{minute:02d}",
            replace_existing=True
        )
        logger.info(f"[STARTUP]   - Bot processor: daily at {hour:02d}:{minute:02d} {timezone}")
    else:
        logger.info(f"[STARTUP]   - Bot processor: DISABLED (enabled=false in config)")
    
    # הוסף job ל-classification_processor (כל X שניות)
    classification_config = config.get("classification_processor", {})
    interval_seconds = classification_config.get("interval_seconds", 10)
    scheduler.add_job(
        scheduled_classification_processor,
        trigger=IntervalTrigger(seconds=interval_seconds),
        id="classification_processor",
        name=f"Process {STATUS_READY_FOR_CLASSIFICATION} records every {interval_seconds} seconds",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info(f"[STARTUP] Scheduler started:")
    logger.info(f"[STARTUP]   - Classification processor: every {interval_seconds} seconds")
    return scheduler

def shutdown_scheduler():
    """
    עוצר את ה-scheduler
    """
    global scheduler
    if scheduler:
        scheduler.shutdown()
        logger.info("[SHUTDOWN] Scheduler stopped")

