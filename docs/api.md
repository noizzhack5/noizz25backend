# תיעוד REST API

## בסיס URL
```
http://localhost:8000
```

## Swagger UI
ניתן לגשת לתיעוד אינטראקטיבי ב:
```
http://localhost:8000/docs
```

## Endpoints

### 1. העלאת CV
**`POST /upload-cv`**

מעלה מסמך CV חדש למערכת.

**Content-Type**: `multipart/form-data`

**Parameters**:
- `file` (Optional[UploadFile]): קובץ PDF
- `name` (Optional[str]): שם המועמד
- `phone` (Optional[str]): מספר טלפון
- `email` (Optional[str]): כתובת אימייל
- `campaign` (Optional[str]): קמפיין
- `notes` (Optional[str]): הערות

**Validation**:
- חייב לשלוח לפחות PDF או אחד מהשדות האחרים

**Response** (200 OK):
```json
{
  "id": "69368322b70117f5f55dcc03",
  "status": "stored"
}
```

**Error Responses**:
- `400 Bad Request`: "Must provide either PDF file or metadata"

**תהליך**:
1. אם קיים PDF - מחלץ טקסט
2. שומר במסד הנתונים עם סטטוס `Submitted`
3. מוסיף סטטוס processing ל-history
4. קורא ל-webhook ב-background
5. אם webhook מצליח - מעדכן סטטוס ל-`Extracting`

**דוגמה**:
```bash
curl -X POST "http://localhost:8000/upload-cv" \
  -F "file=@cv.pdf" \
  -F "name=John Doe" \
  -F "phone=0501234567" \
  -F "email=john@example.com" \
  -F "campaign=Summer2024"
```

---

### 2. קבלת כל המסמכים
**`GET /cv`**

מחזיר את כל המסמכים במערכת.

**Query Parameters**:
- `deleted` (Optional[bool]):
  - `None` או `false`: רק מסמכים שלא מחוקים (ברירת מחדל)
  - `true`: רק מסמכים מחוקים

**Response** (200 OK):
```json
[
  {
    "id": "69368322b70117f5f55dcc03",
    "file_metadata": {
      "filename": "cv.pdf",
      "size_bytes": 2357,
      "content_type": "application/pdf",
      "uploaded_at": "2025-12-08T08:32:10.995564Z"
    },
    "extracted_text": "Name: John Doe...",
    "known_data": {
      "name": "JOHN",
      "phone_number": "0501234567",
      "email": "john@example.com",
      "campaign": "Summer2024",
      "notes": null,
      "job_type": null,
      "match_score": null,
      "class_explain": null,
      "latin_name": "John Doe",
      "hebrew_name": null,
      "age": null,
      "nationality": null,
      "can_travel_europe": null,
      "can_visit_israel": null,
      "lives_in_europe": null,
      "native_israeli": null,
      "english_level": null,
      "remembers_job_application": null,
      "skills_summary": null
    },
    "is_deleted": false,
    "current_status": "Extracting",
    "status_history": [
      {
        "status": "Submitted",
        "timestamp": "2025-12-08T08:32:11.047892Z"
      },
      {
        "status": "processing_success",
        "timestamp": "2025-12-08T08:32:12.877525Z"
      },
      {
        "status": "webhook_status_200",
        "timestamp": "2025-12-08T08:32:14.588425Z"
      },
      {
        "status": "Extracting",
        "timestamp": "2025-12-08T08:32:14.707736Z"
      }
    ]
  }
]
```

**דוגמה**:
```bash
curl -X GET "http://localhost:8000/cv"
curl -X GET "http://localhost:8000/cv?deleted=true"
```

---

### 3. קבלת מסמך לפי ID
**`GET /cv/{id}`**

מחזיר מסמך ספציפי לפי מזהה.

**Path Parameters**:
- `id` (str): מזהה המסמך

**Response** (200 OK):
```json
{
  "id": "69368322b70117f5f55dcc03",
  "file_metadata": {...},
  "extracted_text": "...",
  "known_data": {...},
  "current_status": "Extracting",
  "status_history": [...],
  "is_deleted": false
}
```

**Error Responses**:
- `404 Not Found`: "Document not found"

**הערה**: מחזיר גם מסמכים מחוקים (לא בודק `is_deleted`)

**דוגמה**:
```bash
curl -X GET "http://localhost:8000/cv/69368322b70117f5f55dcc03"
```

---

### 4. עדכון מסמך
**`PATCH /cv/{id}`**

מעדכן שדות של מסמך קיים.

**Path Parameters**:
- `id` (str): מזהה המסמך

**Request Body** (JSON):
```json
{
  "latin_name": "John Doe",
  "hebrew_name": "יוחנן דו",
  "email": "newemail@example.com",
  "campaign": "Winter2024",
  "age": "30",
  "nationality": "Israeli",
  "can_travel_europe": "yes",
  "can_visit_israel": "yes",
  "lives_in_europe": "no",
  "native_israeli": "yes",
  "english_level": "Advanced",
  "remembers_job_application": "yes",
  "skills_summary": "Experienced professional...",
  "job_type": "Software Engineer",
  "match_score": "85",
  "class_explain": "High match candidate"
}
```

**הגבלות**:
- לא ניתן לעדכן `phone_number`
- מעדכן רק שדות שנשלחו (לא מאפס שדות שלא נשלחו)
- לא ניתן לעדכן `status`, `current_status`, `status_history` ישירות

**לוגיקה מותנית**:
- אם `current_status == "Extracting"` → משנה ל-`"Ready For Bot Interview"`
- אם `current_status == "In Classification"` → משנה ל-`"Ready For Recruit"`

**Response** (200 OK):
```json
{
  "status": "updated",
  "id": "69368322b70117f5f55dcc03"
}
```

**Error Responses**:
- `404 Not Found`: "Document not found"
- `200 OK` עם `"status": "no_changes"`: אין שדות לעדכון

**דוגמה**:
```bash
curl -X PATCH "http://localhost:8000/cv/69368322b70117f5f55dcc03" \
  -H "Content-Type: application/json" \
  -d '{"latin_name": "John Doe", "email": "new@example.com"}'
```

---

### 5. עדכון סטטוס
**`PATCH /cv/{id}/status`**

מעדכן את הסטטוס של מסמך לפי ID של סטטוס.

**Path Parameters**:
- `id` (str): מזהה המסמך

**Request Body** (JSON):
```json
{
  "status_id": 3
}
```

**סטטוסים זמינים**:
- `1`: Submitted
- `2`: Extracting
- `3`: Ready For Bot Interview
- `4`: Bot Interview
- `5`: Ready For Classification
- `6`: In Classification
- `7`: Ready For Recruit

**Validation**:
- `status_id` חייב להיות בין 1 ל-7

**Response** (200 OK):
```json
{
  "status": "updated",
  "id": "69368322b70117f5f55dcc03",
  "status_id": 3,
  "current_status": "Ready For Bot Interview"
}
```

**Error Responses**:
- `404 Not Found`: "Document not found"
- `400 Bad Request`: "Invalid status_id: X. Available statuses: ..."
- `500 Internal Server Error`: "Failed to update document status"

**תהליך**:
1. ממיר `status_id` לשם סטטוס
2. מעדכן `current_status`
3. מוסיף פריט חדש ל-`status_history` עם timestamp

**דוגמה**:
```bash
curl -X PATCH "http://localhost:8000/cv/69368322b70117f5f55dcc03/status" \
  -H "Content-Type: application/json" \
  -d '{"status_id": 4}'
```

---

### 6. חיפוש מסמכים
**`GET /cv/search`**

מחפש מסמכים לפי טקסט.

**Query Parameters**:
- `query` (str, required, min_length=1): מונח חיפוש

**Response** (200 OK):
```json
[
  {
    "id": "...",
    "file_metadata": {...},
    "extracted_text": "...",
    "known_data": {...},
    "current_status": "...",
    "status_history": [...]
  }
]
```

**חיפוש מתבצע ב**:
- `extracted_text`
- `file_metadata.filename`
- `file_metadata.content_type`
- `known_data.*` (כל השדות)
- `current_status`

**הערה**: חיפוש case-insensitive, מחזיר רק מסמכים שלא מחוקים

**דוגמה**:
```bash
curl -X GET "http://localhost:8000/cv/search?query=John"
```

---

### 7. מחיקת מסמך
**`DELETE /cv/{id}`**

מוחק מסמך (soft delete).

**Path Parameters**:
- `id` (str): מזהה המסמך

**Response** (200 OK):
```json
{
  "status": "deleted"
}
```

**Error Responses**:
- `404 Not Found`: "Document not found"

**תהליך**:
- מעדכן `is_deleted = True`
- המסמך לא יופיע ב-`GET /cv` (אלא אם `deleted=true`)
- המסמך עדיין קיים במסד הנתונים

**דוגמה**:
```bash
curl -X DELETE "http://localhost:8000/cv/69368322b70117f5f55dcc03"
```

---

### 8. שחזור מסמך
**`POST /cv/{id}/restore`**

משחזר מסמך שנמחק.

**Path Parameters**:
- `id` (str): מזהה המסמך

**Response** (200 OK):
```json
{
  "status": "restored",
  "id": "69368322b70117f5f55dcc03"
}
```

**Error Responses**:
- `404 Not Found`: "Document not found"

**תהליך**:
- מעדכן `is_deleted = False`
- המסמך חוזר להופיע ב-`GET /cv`

**דוגמה**:
```bash
curl -X POST "http://localhost:8000/cv/69368322b70117f5f55dcc03/restore"
```

---

### 9. הפעלה ידנית - Bot Processor
**`POST /process-waiting-for-bot`**

מפעיל ידנית את עיבוד רשומות עם סטטוס "Ready For Bot Interview".

**Response** (200 OK):
```json
{
  "status": "completed",
  "results": {
    "total": 5,
    "success": 3,
    "failed": 2,
    "skipped": 0,
    "details": [
      {"id": "...", "status": "success"},
      {"id": "...", "status": "failed"}
    ]
  }
}
```

**Error Responses**:
- `500 Internal Server Error`: "Error processing records: ..."

**תהליך**:
- מוצא כל המסמכים עם סטטוס "Ready For Bot Interview"
- קורא ל-webhook לכל מסמך
- מעדכן סטטוס למסמכים שהצליחו

**דוגמה**:
```bash
curl -X POST "http://localhost:8000/process-waiting-for-bot"
```

---

### 10. הפעלה ידנית - Classification Processor
**`POST /process-waiting-classification`**

מפעיל ידנית את עיבוד רשומות עם סטטוס "Ready For Classification".

**Response** (200 OK):
```json
{
  "status": "completed",
  "message": "Classification processor executed successfully",
  "results": {
    "total": 3,
    "success": 2,
    "failed": 1,
    "details": [
      {"id": "...", "status": "success"},
      {"id": "...", "status": "failed"}
    ]
  }
}
```

**Error Responses**:
- `500 Internal Server Error`: "Error executing classification processor: ..."

**תהליך**:
- מוצא כל המסמכים עם סטטוס "Ready For Classification"
- קורא ל-webhook לכל מסמך
- מעדכן סטטוס למסמכים שהצליחו

**דוגמה**:
```bash
curl -X POST "http://localhost:8000/process-waiting-classification"
```

---

## מבני נתונים

### CVDocumentInDB
```typescript
{
  id: string;
  file_metadata?: {
    filename: string;
    size_bytes: number;
    content_type: string;
    uploaded_at: string; // ISO datetime
  };
  extracted_text: string;
  known_data: {
    name?: string;
    phone_number?: string;
    email?: string;
    campaign?: string;
    notes?: string;
    job_type?: string | null;
    match_score?: string | null;
    class_explain?: string | null;
    latin_name?: string;
    hebrew_name?: string;
    age?: string | null;
    nationality?: string | null;
    can_travel_europe?: string | null;
    can_visit_israel?: string | null;
    lives_in_europe?: string | null;
    native_israeli?: string | null;
    english_level?: string | null;
    remembers_job_application?: string | null;
    skills_summary?: string | null;
  };
  current_status: string;
  status_history: Array<{
    status: string;
    timestamp: string; // ISO datetime
  }>;
  is_deleted: boolean;
}
```

### CVUpdateRequest
כל השדות אופציונליים (למעט `phone_number` שלא ניתן לעדכן):
- `latin_name`, `hebrew_name`, `email`, `campaign`
- `age`, `nationality`, `can_travel_europe`, `can_visit_israel`
- `lives_in_europe`, `native_israeli`, `english_level`
- `remembers_job_application`, `skills_summary`
- `job_type`, `match_score`, `class_explain`

### StatusUpdateRequest
```json
{
  "status_id": 1  // מספר בין 1 ל-7
}
```

## שגיאות נפוצות

### 400 Bad Request
- "Must provide either PDF file or metadata"
- "Invalid status_id: X. Available statuses: ..."

### 404 Not Found
- "Document not found"

### 500 Internal Server Error
- "Error processing records: ..."
- "Error executing classification processor: ..."
- "Failed to update document status"

## ראו גם
- [לוגיקה עסקית](logic.md)
- [תזרימי מידע](data-flow.md)
- [תיעוד מודולים](modules.md)
- [ארכיטקטורה](architecture.md)

