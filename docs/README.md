# תיעוד המערכת

ברוכים הבאים לתיעוד המלא של מערכת ניהול קורות חיים (CV Management System).

## קבצי תיעוד

### 📐 [ארכיטקטורה](architecture.md)
מבנה המערכת, טכנולוגיות, רכיבים, ותזרימי מידע בסיסיים.

### 🧠 [לוגיקה עסקית](logic.md)
תיאור מפורט של הלוגיקה העסקית, מחזור חיי מסמך, וניהול סטטוסים.

### 🔌 [תיעוד API](api.md)
תיעוד מלא של כל ה-endpoints, מבני נתונים, ושגיאות אפשריות.

### 🔄 [תזרימי מידע](data-flow.md)
תרחישי עבודה מלאים, תזרימי נתונים, ותרחישי קצה.

### 📦 [תיעוד מודולים](modules.md)
אחריות של כל מודול וקובץ, פונקציות, ותלויות.

### 📝 [Changelog](changelog.md)
רישום שינויים בפרויקט.

## התחלה מהירה

1. **להבנת המבנה הכללי**: התחל ב-[ארכיטקטורה](architecture.md)
2. **להבנת הלוגיקה**: המשך ל-[לוגיקה עסקית](logic.md)
3. **לשימוש ב-API**: עיין ב-[תיעוד API](api.md)
4. **להבנת תזרימי מידע**: ראה [תזרימי מידע](data-flow.md)
5. **לפיתוח/תחזוקה**: עיין ב-[תיעוד מודולים](modules.md)

## מבנה המערכת בקצרה

המערכת בנויה על:
- **FastAPI**: Framework ל-API
- **MongoDB**: מסד נתונים
- **APScheduler**: עבודות רקע
- **Webhooks**: אינטגרציה עם שירותים חיצוניים

## מחזור חיי מסמך

```
Submitted → Extracting → Ready For Bot Interview → Bot Interview 
→ Ready For Classification → In Classification → Ready For Recruit
```

## נקודות כניסה עיקריות

- **API**: `app/main.py`
- **Database**: `app/services/storage.py`
- **Background Jobs**: `app/jobs/scheduler.py`
- **Configuration**: `services_config.json`, `app/jobs/scheduler_config.json`

## קישורים מהירים

- [Swagger UI](http://localhost:8000/docs) - תיעוד אינטראקטיבי
- [ארכיטקטורה](architecture.md)
- [API Reference](api.md)
- [Data Flow](data-flow.md)

---

**עודכן לאחרונה**: דצמבר 2025

