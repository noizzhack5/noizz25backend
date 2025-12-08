# לוגיקה עסקית

## סקירה כללית

מערכת ניהול קורות חיים המטפלת בכל מחזור החיים של מסמך CV - מהעלאה, דרך עיבוד אוטומטי, ועד לסטטוס סופי.

## מחזור חיי מסמך

### 1. שלב העלאה (Submission)
**סטטוס התחלתי**: `Submitted`

**תהליך**:
1. לקוח מעלה CV דרך `POST /upload-cv`
2. המערכת מחלצת טקסט מ-PDF (אם קיים)
3. המסמך נשמר במסד הנתונים עם סטטוס `Submitted`
4. סטטוס `processing_success` או `processing_failed` מתווסף ל-history
5. קריאה ל-webhook חיצוני מתבצעת ב-background
6. אם webhook מצליח (HTTP 2xx), הסטטוס משתנה ל-`Extracting`

**קובץ**: `app/main.py` - `upload_cv()`

### 2. שלב חילוץ (Extraction)
**סטטוס**: `Extracting`

**תהליך**:
- המסמך ממתין לעיבוד חיצוני
- כאשר משתמש מעדכן את המסמך (`PATCH /cv/{id}`) והסטטוס הוא `Extracting`, הסטטוס משתנה אוטומטית ל-`Waiting Bot Interview`

**קובץ**: `app/main.py` - `update_cv()`

### 3. שלב המתנה לבוט (Waiting Bot Interview)
**סטטוס**: `Waiting Bot Interview`

**תהליך**:
- Scheduler רץ כל יום בשעה מוגדרת (ברירת מחדל: 10:00 UTC)
- או הפעלה ידנית דרך `POST /process-waiting-for-bot`
- המערכת מוצאת כל המסמכים עם סטטוס זה
- לכל מסמך:
  - קריאה ל-webhook עם: `id`, `phone_number`, `latin_name`
  - בדיקת שדה `success` בתגובה (boolean או string "true"/"false")
  - אם הצליח: עדכון סטטוס ל-`Bot Interview`
  - הוספת סטטוס webhook ל-history

**קובץ**: `app/services/bot_processor.py`

### 4. שלב שיחה עם בוט (Bot Interview)
**סטטוס**: `Bot Interview`

**תהליך**:
- המסמך נמצא בתהליך שיחה עם בוט
- אין עיבוד אוטומטי בשלב זה
- ניתן לעדכן ידנית דרך `PATCH /cv/{id}/status`

### 5. שלב המתנה לקלסיפיקציה (Waiting Classification)
**סטטוס**: `Waiting Classification`

**תהליך**:
- Scheduler רץ כל X דקות (ברירת מחדל: 5 דקות)
- או הפעלה ידנית דרך `POST /process-waiting-classification`
- המערכת מוצאת כל המסמכים עם סטטוס זה
- לכל מסמך:
  - קריאה ל-webhook עם: `id`
  - אם HTTP status code הוא 2xx: עדכון סטטוס ל-`In Classification`
  - הוספת סטטוס webhook ל-history

**קובץ**: `app/jobs/classification_processor.py`

### 6. שלב קלסיפיקציה (In Classification)
**סטטוס**: `In Classification`

**תהליך**:
- המסמך נמצא בתהליך קלסיפיקציה
- כאשר משתמש מעדכן את המסמך (`PATCH /cv/{id}`) והסטטוס הוא `In Classification`, הסטטוס משתנה אוטומטית ל-`Ready For Recruit`

**קובץ**: `app/main.py` - `update_cv()`

### 7. שלב מוכן לגיוס (Ready For Recruit)
**סטטוס**: `Ready For Recruit`

**תהליך**:
- זהו הסטטוס הסופי
- המסמך מוכן לגיוס
- אין עיבוד אוטומטי נוסף

## ניהול סטטוסים

### מבנה סטטוס
כל מסמך מכיל:
- **`current_status`**: הסטטוס הנוכחי (string)
- **`status_history`**: מערך של כל הסטטוסים שהיו למסמך
  - כל פריט: `{status: string, timestamp: ISO datetime}`

### עדכון סטטוס
**פונקציה**: `update_document_status()` ב-`app/services/storage.py`

**תהליך**:
1. מעדכן את `current_status` לסטטוס החדש
2. מוסיף פריט חדש ל-`status_history` עם timestamp

### הוספת סטטוס ל-history בלבד
**פונקציה**: `add_status_to_history()` ב-`app/services/storage.py`

**שימוש**:
- הוספת סטטוסי webhook (`webhook_status_200`, `webhook_error`)
- הוספת סטטוסי processing (`processing_success`, `processing_failed`)
- לא משנה את `current_status`

## עיבוד PDF

### תהליך חילוץ
**קובץ**: `app/services/pdf_parser.py`

**פונקציה**: `extract_text_from_pdf(pdf_bytes: bytes) -> Tuple[str, str]`

**תהליך**:
1. בודק שהקובץ לא ריק
2. משתמש ב-`pdfminer.six` לחילוץ טקסט
3. מחזיר: `(extracted_text, error_message)`
   - אם הצליח: `(text, None)`
   - אם נכשל: `("", error_message)`

**שימוש**: נקרא מ-`upload_cv()` ב-`app/main.py`

## עדכון מסמכים

### עדכון חלקי (`PATCH /cv/{id}`)
**קובץ**: `app/main.py` - `update_cv()`

**לוגיקה**:
1. מעדכן רק שדות שנשלחו ב-body (לא מאפס שדות שלא נשלחו)
2. לא ניתן לעדכן `phone_number`
3. לא ניתן לעדכן `status`, `current_status`, `status_history` ישירות
4. אם הסטטוס הנוכחי הוא `Extracting` → משנה ל-`Waiting Bot Interview`
5. אם הסטטוס הנוכחי הוא `In Classification` → משנה ל-`Ready For Recruit`

**פונקציה**: `update_document_fields_only()` ב-`app/services/storage.py`

### עדכון סטטוס (`PATCH /cv/{id}/status`)
**קובץ**: `app/main.py` - `update_cv_status()`

**לוגיקה**:
1. מקבל `status_id` (מספר 1-7)
2. ממיר ID לשם סטטוס דרך `get_status_by_id()`
3. מעדכן את `current_status` ומוסיף ל-`status_history`

## חיפוש מסמכים

**קובץ**: `app/services/storage.py` - `search_documents()`

**לוגיקה**:
- חיפוש טקסטואלי (case-insensitive) ב:
  - `extracted_text`
  - `file_metadata.filename`
  - `file_metadata.content_type`
  - `known_data.*` (כל השדות)
  - `current_status`
- מחזיר רק מסמכים שלא מחוקים (`is_deleted != True`)

## מחיקה ושחזור

### מחיקה (`DELETE /cv/{id}`)
**לוגיקה**:
- לא מוחק פיזית מהמסד
- מעדכן `is_deleted = True`
- המסמך לא יופיע ב-`GET /cv` (אלא אם `deleted=true`)

### שחזור (`POST /cv/{id}/restore`)
**לוגיקה**:
- מעדכן `is_deleted = False`
- המסמך חוזר להופיע ב-`GET /cv`

## נרמול נתונים

### המרת "unknown" ל-None
**פונקציה**: `normalize_unknown_values()` ב-`app/services/storage.py`

**לוגיקה**:
- כל ערך "unknown" (בכל וריאציה: "Unknown", "UNKNOWN") ב-`known_data` מומר ל-`None`
- מתבצע בכל קריאה למסד הנתונים (GET, SEARCH)
- מתבצע גם בעדכונים

**סיבה**: להבטיח עקביות בנתונים - "unknown" = אין מידע = `null`

## אינטגרציה עם שירותים חיצוניים

### Webhooks
כל ה-webhooks מוגדרים ב-`services_config.json`:
- **base_url**: URL בסיס משותף
- **paths**: paths ספציפיים לכל webhook

### קריאות Webhook

#### 1. Upload CV Webhook
**מתי**: אחרי העלאת CV מוצלחת
**URL**: `{base_url}/{upload_cv_path}`
**Payload**: `{"id": "document_id"}`
**תגובה**: אם HTTP 2xx → עדכון סטטוס ל-`Extracting`

#### 2. Bot Processor Webhook
**מתי**: עיבוד רשומות עם סטטוס "Waiting Bot Interview"
**URL**: `{base_url}/{bot_processor_path}`
**Payload**: `{"id": "...", "phone_number": "...", "latin_name": "..."}`
**תגובה**: בודק שדה `success` (boolean או string) → אם `true` → עדכון ל-`Bot Interview`

#### 3. Classification Webhook
**מתי**: עיבוד רשומות עם סטטוס "Waiting Classification"
**URL**: `{base_url}/{classification_processor_path}`
**Payload**: `{"id": "document_id"}`
**תגובה**: אם HTTP 2xx → עדכון ל-`In Classification`

## Scheduler Jobs

### Bot Processor Job
**סוג**: Cron (יומי)
**תדירות**: פעם ביום בשעה מוגדרת (ברירת מחדל: 10:00 UTC)
**קובץ קונפיגורציה**: `app/jobs/scheduler_config.json`
**פונקציה**: `scheduled_bot_processor()` ב-`app/jobs/scheduler.py`

### Classification Processor Job
**סוג**: Interval (תקופתי)
**תדירות**: כל X דקות (ברירת מחדל: 5 דקות)
**קובץ קונפיגורציה**: `app/jobs/scheduler_config.json`
**פונקציה**: `scheduled_classification_processor()` ב-`app/jobs/scheduler.py`

## טיפול בשגיאות

### שגיאות Webhook
- **Timeout**: מתועד כ-`webhook_error: Webhook timeout`
- **Request Error**: מתועד כ-`webhook_error: Webhook request error`
- **Unexpected Error**: מתועד כ-`webhook_error: Webhook unexpected error`
- כל שגיאה מתווספת ל-`status_history`

### שגיאות Processing
- **PDF Parse Error**: מתועד כ-`processing_error: {error_message}`
- **Empty Text**: מתועד כ-`processing_failed`
- **Success**: מתועד כ-`processing_success`

### שגיאות Validation
- **Invalid Status ID**: HTTP 400 עם רשימת סטטוסים תקפים
- **Missing Required Fields**: HTTP 400
- **Document Not Found**: HTTP 404

## ראו גם
- [תיעוד API](api.md)
- [תזרימי מידע](data-flow.md)
- [תיעוד מודולים](modules.md)
- [ארכיטקטורה](architecture.md)

