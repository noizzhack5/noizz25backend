# Changelog

כל השינויים המשמעותיים בפרויקט יתועדו בקובץ זה.

הפורמט מבוסס על [Keep a Changelog](https://keepachangelog.com/he/1.0.0/),
והפרויקט עוקב אחר [Semantic Versioning](https://semver.org/lang/he/).

## [Unreleased]

### הוספו
- תיעוד מלא של המערכת ב-`/docs`
- מערכת ניהול סטטוסים עם `current_status` ו-`status_history`
- Scheduler לעבודות רקע (bot processor ו-classification processor)
- קונפיגורציה חיצונית ל-webhooks ו-scheduler
- API endpoints לעדכון סטטוס, שחזור מסמכים, והפעלה ידנית של processors
- נרמול ערכים "unknown" ל-`null`
- טיפול בשגיאות webhook מפורט
- **ארכיטקטורה משופרת**: יצירת מבנה שכבתי עם `app/core/`, `app/utils/`, `app/repositories/`
- **WebhookClient utility**: איחוד קוד כפול של קריאות webhook ל-utility משותף
- **Custom exceptions**: יצירת exception classes מותאמות אישית (`DocumentNotFoundError`, `InvalidStatusError`, `ValidationError`)
- **Configuration centralization**: העברת כל הקבועים וההגדרות ל-`app/core/config.py`
- **Data normalization utilities**: פונקציות עזר לנרמול נתונים ב-`app/utils/data_normalization.py`
- **Repository pattern**: יצירת `CVRepository` להפרדת גישת מסד נתונים (לא בשימוש פעיל עדיין, שמירה לתאימות עתידית)

### שונה
- מבנה סטטוסים: מ-`status` ל-`current_status` + `status_history`
- עדכון מסמכים: מעדכן רק שדות שנשלחו (לא מאפס שדות אחרים)
- סטטוס "Received" שונה ל-"Submitted"
- **Refactoring**: העברת constants מ-`app/constants.py` ל-`app/core/constants.py` (עם backward compatibility)
- **Refactoring**: העברת database config מ-`app/database.py` ל-`app/core/config.py`
- **Code deduplication**: איחוד לוגיקת webhook calls ב-`bot_processor.py` ו-`classification_processor.py` ל-`WebhookClient` utility
- **Magic numbers removal**: הוצאת magic numbers (30.0, 500, 200, 300) ל-constants ב-`app/core/config.py`
- **Error handling**: שימוש ב-custom exceptions במקום `HTTPException` ישיר
- **CORS configuration**: העברת הגדרות CORS ל-`app/core/config.py`
- **Storage service**: עדכון `storage.py` להשתמש ב-`normalize_document` utility במקום קוד כפול

### תוקן
- בעיית עדכון סטטוס אוטומטי שלא רצוי
- בעיית "unknown" שמוחזר במקום `null`

### שיפורי קוד (Clean Code & Maintainability)
- **Separation of concerns**: הפרדה ברורה בין layers (core, utils, repositories, services)
- **DRY principle**: איחוד קוד כפול של webhook calls
- **Single Responsibility**: כל מודול עכשיו ממוקד באחריות אחת
- **Configuration management**: כל הקונפיגורציות מרוכזות במקום אחד
- **Type hints**: שיפור type hints בכל הפונקציות
- **Docstrings**: הוספת docstrings מפורטים לכל הפונקציות החדשות
- **Naming conventions**: שיפור שמות משתנים ופונקציות להיות יותר משמעותיים

---

## הערות

קובץ זה ישמש לתיעוד שינויים עתידיים בפרויקט.

### קטגוריות שינויים:
- **הוספו**: תכונות חדשות
- **שונה**: שינויים בתכונות קיימות
- **הופסק**: תכונות שהוסרו
- **תוקן**: תיקוני באגים
- **אבטחה**: שינויים הקשורים לאבטחה

