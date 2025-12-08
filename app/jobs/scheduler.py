"""
ניהול ה-scheduler וה-jobs שרצים ברקע
"""
import logging
import json
import os
from pathlib import Path
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.services.bot_processor import process_waiting_for_bot_records
from app.constants import STATUS_WAITING_BOT_INTERVIEW

logger = logging.getLogger(__name__)

scheduler = None
_db_client = None

def load_scheduler_config():
    """
    טוען את הגדרות ה-scheduler מקובץ scheduler_config.json בתיקיית jobs
    מחזיר dict עם hour, minute, timezone
    """
    # נתיב לקובץ הקונפיגורציה בתיקיית jobs
    config_path = Path(__file__).parent / "scheduler_config.json"
    default_config = {
        "hour": 10,
        "minute": 0,
        "timezone": "UTC"
    }
    
    if not config_path.exists():
        logger.warning(f"[CONFIG] scheduler_config.json not found at {config_path}, using default values: {default_config}")
        return default_config
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        scheduler_config = config.get("bot_processor", {})
        
        # ודא שיש את כל הערכים הנדרשים
        result = {
            "hour": scheduler_config.get("hour", default_config["hour"]),
            "minute": scheduler_config.get("minute", default_config["minute"]),
            "timezone": scheduler_config.get("timezone", default_config["timezone"])
        }
        
        # בדיקת תקינות
        if not (0 <= result["hour"] <= 23):
            logger.warning(f"[CONFIG] Invalid hour value {result['hour']}, using default {default_config['hour']}")
            result["hour"] = default_config["hour"]
        
        if not (0 <= result["minute"] <= 59):
            logger.warning(f"[CONFIG] Invalid minute value {result['minute']}, using default {default_config['minute']}")
            result["minute"] = default_config["minute"]
        
        logger.info(f"[CONFIG] Loaded scheduler config: {result}")
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"[CONFIG] Error parsing config.json: {str(e)}, using default values")
        return default_config
    except Exception as e:
        logger.error(f"[CONFIG] Error loading config.json: {str(e)}, using default values")
        return default_config

async def scheduled_bot_processor():
    """פונקציה שרצה על ידי ה-scheduler כל יום ב-10:00"""
    global _db_client
    logger.info("[SCHEDULER] Starting scheduled bot processor job (triggered by daily scheduler at 10:00 AM)")
    try:
        results = await process_waiting_for_bot_records(_db_client, trigger_source="scheduled")
        logger.info(f"[SCHEDULER] Scheduled job completed: {results}")
    except Exception as e:
        logger.error(f"[SCHEDULER] Error in scheduled job: {str(e)}", exc_info=True)

def setup_scheduler(db_client):
    """
    מגדיר ומתחיל את ה-scheduler
    טוען את הגדרות הזמן מקובץ config.json
    """
    global scheduler, _db_client
    _db_client = db_client
    
    # טען את הגדרות ה-scheduler מקובץ הקונפיגורציה
    config = load_scheduler_config()
    hour = config["hour"]
    minute = config["minute"]
    timezone = config["timezone"]
    
    scheduler = AsyncIOScheduler(timezone=timezone)
    # הרץ כל יום לפי ההגדרות בקובץ הקונפיגורציה
    scheduler.add_job(
        scheduled_bot_processor,
        trigger=CronTrigger(hour=hour, minute=minute),
        id="daily_bot_processor",
        name=f"Process {STATUS_WAITING_BOT_INTERVIEW} records daily at {hour:02d}:{minute:02d}",
        replace_existing=True
    )
    scheduler.start()
    logger.info(f"[STARTUP] Scheduler started - bot processor will run daily at {hour:02d}:{minute:02d} {timezone}")
    return scheduler

def shutdown_scheduler():
    """
    עוצר את ה-scheduler
    """
    global scheduler
    if scheduler:
        scheduler.shutdown()
        logger.info("[SHUTDOWN] Scheduler stopped")

