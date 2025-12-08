# תזרימי מידע ותרחישים

## סקירה כללית

מסמך זה מתאר את תזרימי המידע במערכת, תרחישי עבודה מלאים, וטיפול בשגיאות.

## תרחיש 1: העלאת CV חדש

### תזרים מלא

```
1. Client → POST /upload-cv
   ├─ Form Data: file (PDF), name, phone, email, campaign, notes
   └─ FastAPI validates input

2. FastAPI → extract_text_from_pdf()
   ├─ If PDF exists: Extract text using pdfminer
   ├─ Returns: (text, error_message)
   └─ If error: error_message is set

3. FastAPI → insert_cv_document()
   ├─ Create document structure
   ├─ Set current_status = "Submitted"
   ├─ Add status_history entry: {"status": "Submitted", "timestamp": "..."}
   ├─ Set is_deleted = False
   └─ Insert to MongoDB → Returns document_id

4. FastAPI → add_status_to_history()
   ├─ Add processing status:
   │   ├─ If error: "processing_error: {error_message}"
   │   ├─ If success: "processing_success"
   │   └─ If failed: "processing_failed"
   └─ Update MongoDB

5. FastAPI → Background Task: call_webhook()
   ├─ Get webhook URL from config_loader
   ├─ POST to webhook with {"id": document_id}
   ├─ If HTTP 2xx:
   │   ├─ Add "webhook_status_200" to history
   │   └─ update_document_status() → "Extracting"
   └─ If error:
       └─ Add "webhook_error: ..." to history

6. FastAPI → Response to Client
   └─ {"id": "...", "status": "stored"}
```

### דיאגרמת מצבים
```
[Submitted] → [Extracting] (after webhook success)
```

### טיפול בשגיאות
- **PDF Parse Error**: מתועד ב-history, המסמך נשמר עם `extracted_text = ""`
- **Webhook Timeout**: מתועד ב-history, הסטטוס נשאר "Submitted"
- **Webhook Error**: מתועד ב-history, הסטטוס נשאר "Submitted"

---

## תרחיש 2: עיבוד בוט אוטומטי (Scheduled)

### תזרים מלא

```
1. Scheduler (Daily at configured time)
   └─ Triggers: scheduled_bot_processor()

2. scheduled_bot_processor() → process_waiting_for_bot_records()
   ├─ Get all documents with status "Waiting Bot Interview"
   └─ For each document:

3. For each document:
   ├─ call_bot_webhook()
   │   ├─ Get webhook URL from config_loader
   │   ├─ POST to webhook:
   │   │   {
   │   │     "id": record_id,
   │   │     "phone_number": "...",
   │   │     "latin_name": "..."
   │   │   }
   │   ├─ Parse response JSON
   │   ├─ Check response.success field:
   │   │   ├─ If string "true" → convert to boolean True
   │   │   ├─ If string "false" → convert to boolean False
   │   │   └─ If missing → use HTTP status code as fallback
   │   ├─ Add webhook_status to history
   │   └─ Return True/False
   │
   ├─ If success:
   │   ├─ Mark in results as "success"
   │   └─ update_document_status() → "Bot Interview"
   │
   └─ If failed:
       └─ Mark in results as "failed"

4. Return results summary
   └─ {
       "total": 5,
       "success": 3,
       "failed": 2,
       "details": [...]
     }
```

### דיאגרמת מצבים
```
[Waiting Bot Interview] → [Bot Interview] (after webhook success)
```

### טיפול בשגיאות
- **Webhook Timeout**: מתועד ב-history, המסמך נשאר ב-"Waiting Bot Interview"
- **Webhook Returns success=false**: המסמך נשאר ב-"Waiting Bot Interview"
- **Database Error**: מתועד ב-logs, המסמך לא מעודכן

---

## תרחיש 3: עיבוד Classification אוטומטי (Interval)

### תזרים מלא

```
1. Scheduler (Every X minutes)
   └─ Triggers: scheduled_classification_processor()

2. scheduled_classification_processor() → process_waiting_classification_records()
   ├─ Get all documents with status "Waiting Classification"
   └─ For each document:

3. For each document:
   ├─ call_classification_webhook()
   │   ├─ Get webhook URL from config_loader
   │   ├─ POST to webhook: {"id": record_id}
   │   ├─ Check HTTP status code:
   │   │   ├─ If 200-299: Success
   │   │   └─ Otherwise: Failed
   │   ├─ Add webhook_status to history
   │   └─ Return True/False
   │
   ├─ If success:
   │   ├─ Mark in results as "success"
   │   └─ update_document_status() → "In Classification"
   │
   └─ If failed:
       └─ Mark in results as "failed"

4. Return results summary
```

### דיאגרמת מצבים
```
[Waiting Classification] → [In Classification] (after webhook success)
```

---

## תרחיש 4: עדכון מסמך

### תזרים מלא

```
1. Client → PATCH /cv/{id}
   ├─ Request Body: {latin_name: "...", email: "..."}
   └─ FastAPI validates input

2. FastAPI → get_document_by_id()
   ├─ Check if document exists
   └─ Return document (or 404)

3. FastAPI → update_document_fields_only()
   ├─ Remove phone_number from update_data
   ├─ Convert "unknown" values to None
   ├─ Update only fields that were sent
   ├─ Merge with existing known_data
   └─ Update MongoDB

4. FastAPI → Check current_status:
   ├─ If "Extracting":
   │   └─ update_document_status() → "Waiting Bot Interview"
   │
   └─ If "In Classification":
       └─ update_document_status() → "Ready For Recruit"

5. FastAPI → Response to Client
   └─ {"status": "updated", "id": "..."}
```

### דיאגרמת מצבים
```
[Extracting] → [Waiting Bot Interview] (after update)
[In Classification] → [Ready For Recruit] (after update)
```

---

## תרחיש 5: עדכון סטטוס ידני

### תזרים מלא

```
1. Client → PATCH /cv/{id}/status
   ├─ Request Body: {"status_id": 3}
   └─ FastAPI validates status_id (1-7)

2. FastAPI → get_document_by_id()
   └─ Check if document exists

3. FastAPI → get_status_by_id(status_id)
   ├─ Lookup in STATUS_ID_MAP
   └─ Return status name (or None)

4. FastAPI → update_document_status()
   ├─ Update current_status
   ├─ Add to status_history with timestamp
   └─ Update MongoDB

5. FastAPI → Response to Client
   └─ {
       "status": "updated",
       "id": "...",
       "status_id": 3,
       "current_status": "Waiting Bot Interview"
     }
```

---

## תרחיש 6: חיפוש מסמכים

### תזרים מלא

```
1. Client → GET /cv/search?query=John
   └─ FastAPI validates query (min_length=1)

2. FastAPI → search_documents()
   ├─ Build MongoDB query:
   │   ├─ is_deleted != True
   │   └─ $or: [
   │       extracted_text contains "John",
   │       file_metadata.filename contains "John",
   │       known_data.* contains "John",
   │       current_status contains "John"
   │     ]
   │
   ├─ Execute query
   ├─ For each result:
   │   ├─ Normalize "unknown" → None
   │   ├─ Ensure job_type, match_score, class_explain exist
   │   └─ Convert _id to id
   │
   └─ Return list of documents

3. FastAPI → Response to Client
   └─ Array of documents
```

---

## תרחיש 7: מחיקה ושחזור

### מחיקה

```
1. Client → DELETE /cv/{id}

2. FastAPI → delete_document_by_id()
   ├─ Update MongoDB: is_deleted = True
   └─ Return success/failure

3. FastAPI → Response to Client
   └─ {"status": "deleted"}
```

### שחזור

```
1. Client → POST /cv/{id}/restore

2. FastAPI → restore_document_by_id()
   ├─ Update MongoDB: is_deleted = False
   └─ Return success/failure

3. FastAPI → Response to Client
   └─ {"status": "restored", "id": "..."}
```

---

## מחזור חיי מסמך - תזרים מלא

```
[1. Submitted]
   ↓ (webhook success)
[2. Extracting]
   ↓ (user updates document)
[3. Waiting Bot Interview]
   ↓ (scheduler/bot webhook success)
[4. Bot Interview]
   ↓ (manual status update)
[5. Waiting Classification]
   ↓ (scheduler/classification webhook success)
[6. In Classification]
   ↓ (user updates document)
[7. Ready For Recruit]
```

---

## טיפול בשגיאות - תזרים

### שגיאת Webhook

```
Webhook Call
   ↓
Error Occurs (Timeout/Request Error/Unexpected)
   ↓
Catch Exception
   ↓
Create error message
   ↓
add_status_to_history("webhook_error: {message}")
   ↓
Log error
   ↓
Return False (or continue with next record)
```

### שגיאת Validation

```
Client Request
   ↓
FastAPI Validation
   ↓
If Invalid:
   ↓
Return HTTP 400/404/500
   ↓
Error detail in response body
```

### שגיאת Database

```
Database Operation
   ↓
If Error:
   ↓
Log error with exc_info
   ↓
Return False/None
   ↓
API returns appropriate HTTP status
```

---

## תרחישי קצה

### תרחיש 1: PDF ריק
- **קלט**: PDF קובץ ריק או פגום
- **תהליך**: `extract_text_from_pdf()` מחזיר `("", "file is empty")`
- **תוצאה**: המסמך נשמר עם `extracted_text = ""`, סטטוס `processing_failed` ב-history

### תרחיש 2: Webhook לא זמין
- **קלט**: Webhook מחזיר timeout או error
- **תהליך**: השגיאה מתועדת ב-history, הסטטוס לא משתנה
- **תוצאה**: המסמך נשאר בסטטוס הקודם, ניתן לנסות שוב

### תרחיש 3: Webhook מחזיר success=false
- **קלט**: Webhook מחזיר `{"success": false}` או `{"success": "false"}`
- **תהליך**: המערכת מזהה את הערך ומחזירה `False`
- **תוצאה**: המסמך לא מעודכן, נשאר ב-"Waiting Bot Interview"

### תרחיש 4: עדכון מסמך לא קיים
- **קלט**: `PATCH /cv/{invalid_id}`
- **תהליך**: `get_document_by_id()` מחזיר `None`
- **תוצאה**: HTTP 404 "Document not found"

### תרחיש 5: עדכון סטטוס לא תקין
- **קלט**: `PATCH /cv/{id}/status` עם `status_id: 99`
- **תהליך**: `get_status_by_id()` מחזיר `None`
- **תוצאה**: HTTP 400 עם רשימת סטטוסים תקפים

### תרחיש 6: עדכון ללא שינויים
- **קלט**: `PATCH /cv/{id}` עם body ריק או רק `phone_number`
- **תהליך**: `update_dict` ריק אחרי הסרת `phone_number`
- **תוצאה**: HTTP 200 עם `{"status": "no_changes"}`

---

## תזרים נתונים - מבנה מסמך

### יצירת מסמך חדש
```json
{
  "_id": ObjectId("..."),
  "file_metadata": {...},
  "extracted_text": "...",
  "known_data": {
    "name": "...",
    "phone_number": "...",
    "email": "...",
    "campaign": "...",
    "notes": "...",
    "job_type": null,
    "match_score": null,
    "class_explain": null
  },
  "is_deleted": false,
  "current_status": "Submitted",
  "status_history": [
    {"status": "Submitted", "timestamp": "2025-12-08T10:00:00Z"}
  ]
}
```

### לאחר עיבוד
```json
{
  "current_status": "Extracting",
  "status_history": [
    {"status": "Submitted", "timestamp": "..."},
    {"status": "processing_success", "timestamp": "..."},
    {"status": "webhook_status_200", "timestamp": "..."},
    {"status": "Extracting", "timestamp": "..."}
  ]
}
```

---

## אינטגרציה עם שירותים חיצוניים

### Webhook - Upload CV
```
Request:
POST {base_url}/{upload_cv_path}
Body: {"id": "document_id"}

Response (Success):
HTTP 200 OK
Body: {"message": "Workflow was started"}

System Action:
- Add "webhook_status_200" to history
- Update status to "Extracting"
```

### Webhook - Bot Processor
```
Request:
POST {base_url}/{bot_processor_path}
Body: {
  "id": "document_id",
  "phone_number": "...",
  "latin_name": "..."
}

Response (Success):
HTTP 200 OK
Body: {"success": true}  // or {"success": "true"}

System Action:
- Add "webhook_status_200" to history
- Check success field (boolean or string)
- If true: Update status to "Bot Interview"
```

### Webhook - Classification
```
Request:
POST {base_url}/{classification_processor_path}
Body: {"id": "document_id"}

Response (Success):
HTTP 200 OK

System Action:
- Add "webhook_status_200" to history
- If HTTP 2xx: Update status to "In Classification"
```

---

## ראו גם
- [לוגיקה עסקית](logic.md)
- [תיעוד API](api.md)
- [תיעוד מודולים](modules.md)
- [ארכיטקטורה](architecture.md)

