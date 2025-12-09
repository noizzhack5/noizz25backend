# תיעוד מודולים וקבצים

## סקירה כללית

מסמך זה מתאר את אחריות כל מודול וקובץ במערכת, כולל פונקציות, מחלקות, ותלויות.

---

## `app/main.py`

**תפקיד**: נקודת הכניסה הראשית של המערכת - FastAPI application

**תלויות**:
- `app.models`
- `app.database`
- `app.services.*`
- `app.jobs.*`
- `app.constants`

**פונקציות עיקריות**:

### `startup_event()`
- **תפקיד**: אתחול המערכת בעת הפעלה
- **פעולות**:
  - יצירת חיבור למסד הנתונים
  - הפעלת scheduler

### `shutdown_event()`
- **תפקיד**: ניקוי בעת כיבוי
- **פעולות**:
  - עצירת scheduler

### `call_webhook(document_id: str)`
- **תפקיד**: קריאה ל-webhook לאחר העלאת CV
- **תהליך**:
  - טוען URL מ-config
  - שולח POST עם `{"id": document_id}`
  - אם הצליח: מעדכן סטטוס ל-"Extracting"
  - מתועד ב-history

### `upload_cv()`
- **Endpoint**: `POST /upload-cv`
- **תפקיד**: העלאת CV חדש
- **תהליך**: ראה [תרחיש 1 ב-data-flow.md](data-flow.md#תרחיש-1-העלאת-cv-חדש)

### `get_all()`
- **Endpoint**: `GET /cv`
- **תפקיד**: קבלת כל המסמכים
- **פרמטרים**: `deleted` (optional)

### `get_cv_by_id(id: str)`
- **Endpoint**: `GET /cv/{id}`
- **תפקיד**: קבלת מסמך לפי ID
- **הערה**: מחזיר גם מסמכים מחוקים

### `delete_cv_by_id(id: str)`
- **Endpoint**: `DELETE /cv/{id}`
- **תפקיד**: מחיקת מסמך (soft delete)

### `restore_cv_by_id(id: str)`
- **Endpoint**: `POST /cv/{id}/restore`
- **תפקיד**: שחזור מסמך שנמחק

### `search_cv(query: str)`
- **Endpoint**: `GET /cv/search`
- **תפקיד**: חיפוש מסמכים לפי טקסט

### `update_cv(id: str, update_data: CVUpdateRequest)`
- **Endpoint**: `PATCH /cv/{id}`
- **תפקיד**: עדכון שדות של מסמך
- **לוגיקה מותנית**: ראה [תרחיש 4 ב-data-flow.md](data-flow.md#תרחיש-4-עדכון-מסמך)

### `update_cv_status(id: str, status_data: StatusUpdateRequest)`
- **Endpoint**: `PATCH /cv/{id}/status`
- **תפקיד**: עדכון סטטוס לפי ID

### `trigger_bot_processor()`
- **Endpoint**: `POST /process-waiting-for-bot`
- **תפקיד**: הפעלה ידנית של bot processor

### `trigger_classification_processor()`
- **Endpoint**: `POST /process-waiting-classification`
- **תפקיד**: הפעלה ידנית של classification processor

---

## `app/models.py`

**תפקיד**: הגדרת Pydantic models לבדיקת נתונים

**Models**:

### `FileMetadataModel`
- **תפקיד**: מטא-דאטה של קובץ
- **שדות**:
  - `filename: str`
  - `size_bytes: int`
  - `content_type: str`
  - `uploaded_at: str`

### `KnownDataModel`
- **תפקיד**: נתונים ידועים של מועמד
- **שדות**: כל השדות אופציונליים
- **שדות מיוחדים**: `job_type`, `match_score`, `class_explain` (default: None)

### `StatusHistoryItem`
- **תפקיד**: פריט בהיסטוריית סטטוס
- **שדות**:
  - `status: str`
  - `timestamp: str`

### `CVDocumentInDB`
- **תפקיד**: מודל למסמך CV במסד הנתונים
- **שדות**:
  - `id: Optional[Any]`
  - `file_metadata: Optional[FileMetadataModel]`
  - `extracted_text: Optional[str]`
  - `known_data: KnownDataModel`
  - `current_status: str`
  - `status_history: List[StatusHistoryItem]`

### `CVUploadResponse`
- **תפקיד**: תגובה להעלאת CV
- **שדות**:
  - `id: str`
  - `status: str`

### `StatusUpdateRequest`
- **תפקיד**: בקשה לעדכון סטטוס
- **שדות**:
  - `status_id: int` (1-7)
- **Validation**: `ge=1, le=7`

### `CVUpdateRequest`
- **תפקיד**: בקשה לעדכון מסמך
- **הגבלות**: לא כולל `phone_number` (לא ניתן לעדכן)
- **כל השדות אופציונליים**

---

## `app/constants.py`

**תפקיד**: ניהול מרכזי של סטטוסים וקבועים

**קבועים**:

### סטטוסים ראשיים
- `STATUS_SUBMITTED = "Submitted"`
- `STATUS_EXTRACTING = "Extracting"`
- `STATUS_READY_FOR_BOT_INTERVIEW = "Ready For Bot Interview"`
- `STATUS_BOT_INTERVIEW = "Bot Interview"`
- `STATUS_READY_FOR_RECRUIT = "Ready For Recruit"`
- `STATUS_READY_FOR_CLASSIFICATION = "Ready For Classification"`
- `STATUS_IN_CLASSIFICATION = "In Classification"`

### מיפוי ID לסטטוס
- `STATUS_ID_MAP`: Dictionary שממפה ID (1-7) לסטטוס
- `STATUS_TO_ID_MAP`: מיפוי הפוך (סטטוס → ID)

### סטטוסי Processing
- `STATUS_PROCESSING_SUCCESS = "processing_success"`
- `STATUS_PROCESSING_FAILED = "processing_failed"`
- `STATUS_PROCESSING_ERROR = "processing_error"` (עם error message)

### סטטוסי Webhook
- `STATUS_WEBHOOK_PREFIX = "webhook_status"` (עם status code)
- `STATUS_WEBHOOK_ERROR = "webhook_error"` (עם error message)

**פונקציות**:

### `get_status_by_id(status_id: int) -> str`
- **תפקיד**: מחזיר שם סטטוס לפי ID
- **מחזיר**: שם הסטטוס או `None`

### `get_all_statuses() -> list`
- **תפקיד**: מחזיר רשימה של כל הסטטוסים עם ID שלהם

### `get_processing_error_status(error_message: str) -> str`
- **תפקיד**: יוצר סטטוס error עם הודעת שגיאה
- **פורמט**: `"processing_error: {error_message[:100]}"`

### `get_webhook_status(status_code: int, status_text: str = None) -> str`
- **תפקיד**: יוצר סטטוס webhook עם status code
- **פורמט**: `"webhook_status_{status_code}"` או `"webhook_status_{status_code}: {status_text[:100]}"`

### `get_webhook_error_status(error_message: str) -> str`
- **תפקיד**: יוצר סטטוס webhook error
- **פורמט**: `"webhook_error: {error_message[:100]}"`

**Enums**:

### `DocumentStatus(str, Enum)`
- **תפקיד**: Enum לסטטוסים תקפים
- **שימוש**: Validation ב-API

---

## `app/database.py`

**תפקיד**: הגדרת חיבור למסד הנתונים

**קבועים**:
- `MONGO_URI`: Connection string ל-MongoDB Atlas
- `DB_NAME = "noizz25HR"`
- `COLLECTION_NAME = "basicHR"`

**פונקציות**:

### `get_database()`
- **תפקיד**: מחזיר database object
- **מחזיר**: `AsyncIOMotorDatabase`

---

## `app/services/storage.py`

**תפקיד**: כל פעולות ה-CRUD למסד הנתונים

**תלויות**:
- `app.constants`
- `bson.ObjectId`
- `motor`

**פונקציות**:

### `normalize_unknown_values(doc: dict) -> dict`
- **תפקיד**: ממיר "unknown" ל-None ב-known_data
- **מתי נקרא**: בכל קריאה למסד הנתונים

### `insert_cv_document(db, doc: dict) -> str`
- **תפקיד**: הוספת מסמך חדש
- **פעולות**:
  - מגדיר `is_deleted = False`
  - מגדיר `current_status = "Submitted"`
  - יוצר `status_history` עם סטטוס ראשוני
- **מחזיר**: ID של המסמך

### `update_document_status(db, id: str, status: str) -> bool`
- **תפקיד**: עדכון סטטוס (current_status + history)
- **פעולות**:
  - מעדכן `current_status`
  - מוסיף פריט ל-`status_history` עם timestamp
- **מחזיר**: `True` אם הצליח

### `get_all_documents(db, deleted: Optional[bool] = None) -> List[dict]`
- **תפקיד**: קבלת כל המסמכים
- **פרמטרים**:
  - `deleted=None/False`: רק לא מחוקים
  - `deleted=True`: רק מחוקים
- **פעולות**:
  - נרמול "unknown" → None
  - וידוא שדות job_type, match_score, class_explain קיימים

### `get_document_by_id(db, id: str) -> Optional[dict]`
- **תפקיד**: קבלת מסמך לפי ID
- **הערה**: מחזיר גם מסמכים מחוקים
- **פעולות**: נרמול ווידוא שדות

### `delete_document_by_id(db, id: str) -> bool`
- **תפקיד**: מחיקת מסמך (soft delete)
- **פעולות**: מעדכן `is_deleted = True`

### `restore_document_by_id(db, id: str) -> bool`
- **תפקיד**: שחזור מסמך
- **פעולות**: מעדכן `is_deleted = False`

### `add_status_to_history(db, id: str, status: str) -> bool`
- **תפקיד**: הוספת סטטוס ל-history בלבד (לא מעדכן current_status)
- **שימוש**: webhook statuses, processing statuses

### `update_document_full(db, id: str, update_data: dict) -> bool`
- **תפקיד**: עדכון כל השדות (לא בשימוש נוכחי)
- **הערה**: פונקציה ישנה, הוחלפה ב-`update_document_fields_only`

### `update_document_fields_only(db, id: str, update_data: dict) -> bool`
- **תפקיד**: עדכון רק שדות שנשלחו
- **פעולות**:
  - המרת "unknown" → None
  - הסרת שדות מוגנים (status, phone_number)
  - עדכון רק שדות שנשלחו
- **מחזיר**: `True` אם הצליח

### `update_document_partial(db, id: str, update_data: dict) -> bool`
- **תפקיד**: עדכון רק שדות שלא קיימים או ריקים
- **הערה**: לא בשימוש נוכחי

### `search_documents(db, term: str) -> list`
- **תפקיד**: חיפוש טקסטואלי במסמכים
- **חיפוש ב**: extracted_text, file_metadata, known_data, current_status
- **פעולות**: נרמול ווידוא שדות

### `get_documents_by_status(db, status: str) -> List[dict]`
- **תפקיד**: קבלת מסמכים לפי סטטוס
- **שימוש**: bot_processor, classification_processor
- **פעולות**: נרמול ווידוא שדות

---

## `app/services/pdf_parser.py`

**תפקיד**: חילוץ טקסט מקבצי PDF

**תלויות**:
- `pdfminer.six`
- `io.BytesIO`

**פונקציות**:

### `extract_text_from_pdf(pdf_bytes: bytes) -> Tuple[str, str]`
- **תפקיד**: חילוץ טקסט מ-PDF
- **פרמטרים**: `pdf_bytes` - תוכן הקובץ
- **מחזיר**: `(extracted_text, error_message)`
  - אם הצליח: `(text, None)`
  - אם נכשל: `("", error_message)`
- **טיפול בשגיאות**: לוגים שגיאות, מחזיר הודעת שגיאה

---

## `app/services/bot_processor.py`

**תפקיד**: עיבוד רשומות עם סטטוס "Ready For Bot Interview"

**תלויות**:
- `app.services.storage`
- `app.services.config_loader`
- `app.constants`
- `httpx`

**פונקציות**:

### `get_bot_webhook_url() -> str`
- **תפקיד**: מחזיר URL של bot webhook מהקונפיגורציה

### `process_waiting_for_bot_records(db, trigger_source: str = "unknown") -> Dict[str, any]`
- **תפקיד**: עיבוד כל הרשומות עם סטטוס "Ready For Bot Interview"
- **פרמטרים**:
  - `db`: מסד הנתונים
  - `trigger_source`: "scheduled" או "manual"
- **תהליך**:
  1. מוצא כל המסמכים עם הסטטוס
  2. לכל מסמך: קורא ל-webhook
  3. אם הצליח: מעדכן סטטוס ל-"Bot Interview"
- **מחזיר**: Dictionary עם סטטיסטיקות

### `call_bot_webhook(db, record_id: str, phone_number: str, latin_name: str) -> bool`
- **תפקיד**: קריאה ל-webhook עם נתוני הרשומה
- **Payload**: `{"id": "...", "phone_number": "...", "latin_name": "..."}`
- **לוגיקה**:
  - בודק שדה `success` בתגובה (boolean או string)
  - אם string: ממיר "true"/"false" לבוליאני
  - אם חסר: משתמש ב-HTTP status code כגיבוי
- **מחזיר**: `True` אם הצליח, `False` אחרת
- **טיפול בשגיאות**: מתועד ב-history

---

## `app/jobs/classification_processor.py`

**תפקיד**: עיבוד רשומות עם סטטוס "Ready For Classification"

**תלויות**:
- `app.services.storage`
- `app.services.config_loader`
- `app.constants`
- `httpx`

**פונקציות**:

### `get_classification_webhook_url() -> str`
- **תפקיד**: מחזיר URL של classification webhook מהקונפיגורציה

### `process_waiting_classification_records(db) -> Dict[str, any]`
- **תפקיד**: עיבוד כל הרשומות עם סטטוס "Ready For Classification"
- **תהליך**:
  1. מוצא כל המסמכים עם הסטטוס
  2. לכל מסמך: קורא ל-webhook
  3. אם HTTP 2xx: מעדכן סטטוס ל-"In Classification"
- **מחזיר**: Dictionary עם סטטיסטיקות

### `call_classification_webhook(db, record_id: str) -> bool`
- **תפקיד**: קריאה ל-webhook עם ID של הרשומה
- **Payload**: `{"id": "..."}`
- **לוגיקה**: בודק HTTP status code (2xx = success)
- **מחזיר**: `True` אם הצליח, `False` אחרת
- **טיפול בשגיאות**: מתועד ב-history

---

## `app/jobs/scheduler.py`

**תפקיד**: ניהול scheduler ו-background jobs

**תלויות**:
- `apscheduler`
- `app.services.bot_processor`
- `app.jobs.classification_processor`
- `app.constants`

**משתנים גלובליים**:
- `scheduler`: AsyncIOScheduler instance
- `_db_client`: Database client (נשמר גלובלית)

**פונקציות**:

### `load_scheduler_config()`
- **תפקיד**: טעינת קונפיגורציה מ-`scheduler_config.json`
- **מחזיר**: Dictionary עם הגדרות bot_processor ו-classification_processor
- **ערכים דיפולטיביים**: אם הקובץ לא קיים או לא תקין

### `scheduled_bot_processor()`
- **תפקיד**: Job function שרצה יומית
- **תהליך**: קורא ל-`process_waiting_for_bot_records()` עם `trigger_source="scheduled"`

### `scheduled_classification_processor()`
- **תפקיד**: Job function שרצה כל X דקות
- **תהליך**: קורא ל-`process_waiting_classification_records()`

### `setup_scheduler(db_client)`
- **תפקיד**: הגדרת והפעלת scheduler
- **תהליך**:
  1. טוען קונפיגורציה
  2. יוצר AsyncIOScheduler
  3. מוסיף job יומי (Cron) ל-bot processor
  4. מוסיף job תקופתי (Interval) ל-classification processor
  5. מפעיל את ה-scheduler

### `shutdown_scheduler()`
- **תפקיד**: עצירת scheduler בעת כיבוי

---

## `app/services/config_loader.py`

**תפקיד**: טעינת קונפיגורציה של שירותים חיצוניים

**תלויות**:
- `json`
- `pathlib.Path`

**Exceptions**:

### `ConfigError(Exception)`
- **תפקיד**: Exception מותאם אישית לשגיאות קונפיגורציה

**פונקציות**:

### `load_services_config() -> Dict`
- **תפקיד**: טעינת קונפיגורציה מ-`services_config.json`
- **בדיקות**:
  - קובץ קיים
  - JSON תקין
  - סעיף "webhooks" קיים
  - כל השדות הנדרשים קיימים
- **מעלה**: `ConfigError` אם יש בעיה
- **מחזיר**: Dictionary עם base_url ו-webhook paths

### `get_webhook_url(webhook_name: str) -> str`
- **תפקיד**: בניית URL מלא של webhook
- **פרמטרים**: `webhook_name` - שם ה-webhook
- **תהליך**:
  1. טוען קונפיגורציה
  2. בונה URL: `{base_url}/{webhook_path}`
  3. מנקה slashes
- **מעלה**: `ConfigError` אם webhook לא נמצא
- **מחזיר**: URL מלא

---

## קבצי קונפיגורציה

### `services_config.json` (בשורש)
**תפקיד**: הגדרת webhooks חיצוניים

**מבנה**:
```json
{
  "webhooks": {
    "base_url": "https://...",
    "bot_processor": "path",
    "classification_processor": "path",
    "upload_cv": "path"
  }
}
```

**חובה**: חייב להיות תקין, ללא ערכים דיפולטיביים

### `app/jobs/scheduler_config.json`
**תפקיד**: הגדרות scheduler

**מבנה**:
```json
{
  "bot_processor": {
    "hour": 10,
    "minute": 0,
    "timezone": "UTC"
  },
  "classification_processor": {
    "interval_minutes": 5,
    "timezone": "UTC"
  }
}
```

---

## תלויות בין מודולים

```
main.py
  ├─ models.py (validation)
  ├─ database.py (connection)
  ├─ services/
  │   ├─ storage.py
  │   │   └─ constants.py
  │   ├─ bot_processor.py
  │   │   ├─ storage.py
  │   │   ├─ config_loader.py
  │   │   └─ constants.py
  │   ├─ pdf_parser.py
  │   └─ config_loader.py
  └─ jobs/
      ├─ scheduler.py
      │   ├─ bot_processor.py
      │   ├─ classification_processor.py
      │   └─ constants.py
      └─ classification_processor.py
          ├─ storage.py
          ├─ config_loader.py
          └─ constants.py
```

---

## ראו גם
- [ארכיטקטורה](architecture.md)
- [לוגיקה עסקית](logic.md)
- [תיעוד API](api.md)
- [תזרימי מידע](data-flow.md)

