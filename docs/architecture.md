# ארכיטקטורת המערכת

## סקירה כללית

מערכת ניהול קורות חיים (CV Management System) בנויה על FastAPI, MongoDB, ומשלבת עיבוד אוטומטי של מסמכים, אינטגרציה עם שירותים חיצוניים דרך webhooks, ומערכת scheduling לעבודות רקע.

## מבנה תיקיות

```
noizz25backend/
├── app/                          # תיקיית האפליקציה הראשית
│   ├── __init__.py
│   ├── main.py                   # נקודת הכניסה הראשית - FastAPI app
│   ├── models.py                 # Pydantic models לבדיקת נתונים
│   ├── constants.py              # קבועים וסטטוסים מרכזיים
│   ├── database.py               # הגדרת חיבור MongoDB
│   ├── services/                 # שירותים עסקיים
│   │   ├── storage.py            # CRUD operations למסד הנתונים
│   │   ├── pdf_parser.py         # חילוץ טקסט מ-PDF
│   │   ├── bot_processor.py      # עיבוד רשומות לשליחת בוט
│   │   └── config_loader.py      # טעינת קונפיגורציה של שירותים חיצוניים
│   └── jobs/                     # עבודות רקע (background jobs)
│       ├── __init__.py
│       ├── scheduler.py          # ניהול scheduler ו-jobs
│       ├── classification_processor.py  # עיבוד classification
│       └── scheduler_config.json # קונפיגורציה של scheduler
├── docs/                         # תיעוד המערכת
├── services_config.json          # קונפיגורציה של webhooks חיצוניים
├── requirements.txt              # תלויות Python
└── README.md                     # מדריך התקנה בסיסי
```

## טכנולוגיות עיקריות

### Backend Framework
- **FastAPI**: Framework מודרני לבניית APIs עם תמיכה אוטומטית ב-OpenAPI/Swagger
- **Uvicorn**: ASGI server להרצת FastAPI

### Database
- **MongoDB Atlas**: מסד נתונים NoSQL בענן
- **Motor**: Async MongoDB driver עבור Python

### Libraries עיקריות
- **Pydantic**: Validation ו-serialization של נתונים
- **httpx**: Async HTTP client לקריאות חיצוניות
- **APScheduler**: מערכת scheduling לעבודות רקע
- **pdfminer.six**: חילוץ טקסט מקבצי PDF

## רכיבי המערכת

### 1. API Layer (`app/main.py`)
- נקודת הכניסה הראשית של המערכת
- מגדיר את כל ה-endpoints
- מטפל ב-CORS, logging, ו-lifecycle events
- מפעיל background tasks ו-scheduler

### 2. Data Models (`app/models.py`)
- **CVDocumentInDB**: מודל למסמך CV במסד הנתונים
- **CVUploadResponse**: תגובה להעלאת CV
- **CVUpdateRequest**: מודל לעדכון מסמך
- **StatusUpdateRequest**: מודל לעדכון סטטוס
- **KnownDataModel**: מודל לנתונים ידועים של מועמד

### 3. Constants (`app/constants.py`)
- ניהול מרכזי של כל הסטטוסים במערכת
- מיפוי ID לסטטוסים
- Enum לבדיקת תקינות סטטוסים
- פונקציות עזר ליצירת סטטוסים דינמיים

### 4. Database Layer (`app/database.py`)
- חיבור ל-MongoDB Atlas
- הגדרת database ו-collection names

### 5. Storage Service (`app/services/storage.py`)
- כל פעולות ה-CRUD למסד הנתונים
- ניהול סטטוסים והיסטוריית סטטוסים
- חיפוש מסמכים
- נרמול ערכים ("unknown" → None)

### 6. PDF Parser (`app/services/pdf_parser.py`)
- חילוץ טקסט מקבצי PDF
- טיפול בשגיאות חילוץ

### 7. Bot Processor (`app/services/bot_processor.py`)
- עיבוד רשומות עם סטטוס "Ready For Bot Interview"
- קריאה ל-webhook חיצוני
- עדכון סטטוס לאחר הצלחה

### 8. Classification Processor (`app/jobs/classification_processor.py`)
- עיבוד רשומות עם סטטוס "Ready For Classification"
- קריאה ל-webhook חיצוני
- עדכון סטטוס לאחר הצלחה

### 9. Scheduler (`app/jobs/scheduler.py`)
- ניהול עבודות רקע
- Job יומי לעיבוד בוט (Cron)
- Job תקופתי לעיבוד classification (Interval)
- טעינת קונפיגורציה מקובץ JSON

### 10. Config Loader (`app/services/config_loader.py`)
- טעינת קונפיגורציה של webhooks חיצוניים
- בדיקת תקינות קונפיגורציה
- בניית URLs מלאים מ-base URL ו-paths

## תזרים מידע

### תזרים בסיסי
```
Client Request → FastAPI → Service Layer → Database
                                    ↓
                            External Webhooks
```

### תזרים ספציפי - העלאת CV
```
POST /upload-cv
  → Extract PDF text (if file provided)
  → Insert to MongoDB
  → Add processing status to history
  → Background task: Call webhook
  → Webhook success → Update status to "Extracting"
```

### תזרים - עיבוד בוט
```
Scheduler (daily) / Manual trigger
  → Get documents with "Ready For Bot Interview"
  → For each document:
      → Call bot webhook
      → Check response.success field
      → If success: Update status to "Bot Interview"
      → Add webhook status to history
```

### תזרים - עיבוד Classification
```
Scheduler (every X minutes) / Manual trigger
  → Get documents with "Ready For Classification"
  → For each document:
      → Call classification webhook
      → If HTTP 2xx: Update status to "In Classification"
      → Add webhook status to history
```

## יחסי תלות

```
main.py
  ├── models.py
  ├── database.py
  ├── services/
  │   ├── storage.py → constants.py
  │   ├── bot_processor.py → storage.py, config_loader.py, constants.py
  │   └── config_loader.py
  └── jobs/
      ├── scheduler.py → bot_processor.py, classification_processor.py
      └── classification_processor.py → storage.py, config_loader.py, constants.py
```

## קונפיגורציה

### קבצי קונפיגורציה

1. **`services_config.json`** (בשורש הפרויקט)
   - מכיל base URL ו-paths של webhooks חיצוניים
   - נדרש להפעלת המערכת
   - ללא ערכים דיפולטיביים - חייב להיות תקין

2. **`app/jobs/scheduler_config.json`**
   - הגדרות scheduler:
     - `bot_processor`: hour, minute, timezone (Cron job)
     - `classification_processor`: interval_minutes, timezone (Interval job)

### משתני סביבה
- `MONGO_URI`: חיבור ל-MongoDB (מוגדר ב-`database.py`)

## אבטחה

- **CORS**: מוגדר לאפשר מכל מקור (לפרודקשן כדאי להגביל)
- **Validation**: Pydantic models בודקים את כל הקלטים
- **Error Handling**: טיפול בשגיאות בכל הרמות
- **Logging**: לוגים מפורטים לכל פעולה

## Scalability

- **Async/Await**: כל הפעולות I/O הן async
- **Background Tasks**: קריאות webhook לא חוסמות את התגובה
- **Scheduler**: עיבוד אוטומטי ללא התערבות ידנית
- **MongoDB**: מסד נתונים scalable בענן

## ראו גם
- [תיעוד API](api.md)
- [לוגיקה עסקית](logic.md)
- [תזרימי מידע](data-flow.md)
- [תיעוד מודולים](modules.md)

