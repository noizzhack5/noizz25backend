# FastAPI CV POC

מערכת API לדוגמה עבור העלאת קורות חיים (PDF + מידע נוסף), חילוץ טקסט, והכנסה ל-MongoDB Atlas.

## דרישות מוקדמות
- Python 3.10+
- חשבון וקישור ל-MongoDB Atlas

## התקנה והפעלה לוקאלית

1. יצירת סביבה וירטואלית:
    ```bash
    python -m venv venv
    ```
2. הפעלת הסביבה:
    - Windows:
      ```bash
      venv\Scripts\activate
      ```
    - Mac/Linux:
      ```bash
      source venv/bin/activate
      ```
3. התקנת תלויות:
    ```bash
    pip install -r requirements.txt
    ```

4. הגדרת משתנה סביבה:
    יש להגדיר את משתנה הסביבה `MONGO_URI`:
    ```bash
    set MONGO_URI="mongodb+srv://<user>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority"
    ```

5. הרצת השרת:
    ```bash
    uvicorn app.main:app --reload
    ```

## קבצים עיקריים במערכת
- `app/main.py`: הגדרת ה-FastAPI וכל הנתיבים.
- `app/models.py`: מבנה הסכמות (Pydantic models).
- `app/database.py`: חיבור למסד הנתונים.
- `app/services/pdf_parser.py`: חילוץ טקסט מקובץ PDF.
- `app/services/storage.py`: טיפול בשמירה ושליפה מהמאגרים.

## APIs

### 1. POST /upload-cv

- **קלט (form-data):**
  - `file`: קובץ PDF (אופציונאלי)
  - `name`: טקסט (אופציונאלי)
  - `phone`: טקסט (אופציונאלי)
  - `notes`: טקסט (אופציונאלי)

- **כלל חובה:** יש לשלוח לפחות PDF או מידע נוסף.
- **תשובה מוצלחת:**
    ```json
    {
      "id": "<inserted_id>",
      "status": "stored"
    }
    ```
- **400 - כשל חוקים:**
    ```json
    {
      "detail": "Must provide either PDF file or metadata"
    }
    ```

#### דוגמת CURL:
```bash
curl -X POST "http://127.0.0.1:8000/upload-cv" -F "file=@cv.pdf" -F "name=ישראל ישראלי" -F "phone=0501231234" -F "notes=הערה כלשהי"
```

### 2. GET /cv
מחזיר את כל המסמכים.

```bash
curl -X GET "http://127.0.0.1:8000/cv"
```

### 3. GET /cv/{id}
מחזיר מסמך לפי מזהה.

```bash
curl -X GET "http://127.0.0.1:8000/cv/{id}"
```

### 4. DELETE /cv/{id}
מוחק מסמך לפי מזהה.
- תשובה:
    ```json
    { "status": "deleted" }
    ```

```bash
curl -X DELETE "http://127.0.0.1:8000/cv/{id}"
```

---

## דוגמת JSON ב-DB
```json
{
  "file_metadata": {
    "filename": "cv.pdf",
    "size_bytes": 173129,
    "content_type": "application/pdf",
    "uploaded_at": "2025-12-07T16:32:48.123Z"
  },
  "extracted_text": "...",
  "known_data": {
    "name": "ישראל ישראלי",
    "phone": "0501231234",
    "notes": "מועמד חזק"
  },
  "processing": {
    "parse_success": true,
    "error_message": null
  }
}
```

## Swagger
ניתן לבדוק ולנסות את הממשק ב- [Swagger UI](http://127.0.0.1:8000/docs)

