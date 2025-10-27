from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import sqlite3
from datetime import datetime
import fitz  # PyMuPDF for PDF text extraction
import google.generativeai as genai
import os

app = FastAPI()

# Allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Database setup ---
conn = sqlite3.connect("summaries.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name TEXT,
    summary TEXT,
    created_at TEXT
)
""")
conn.commit()

# --- Configure Gemini API ---
genai.configure(api_key="AIzaSyDAgFofHdQEcVLSKYf7Rom0fbbeyWZOemc")  # Replace with your Gemini API key

@app.get("/")
def root():
    return {"message": "FastAPI with SQLite is running successfully!"}

# --- Upload and Summarize File ---
@app.post("/uploadfile/")
async def upload_file(file: UploadFile = File(...)):
    try:
        # Save uploaded file locally
        file_location = f"uploads/{file.filename}"
        os.makedirs("uploads", exist_ok=True)
        with open(file_location, "wb") as f:
            f.write(await file.read())

        # Extract text from PDF
        pdf_text = ""
        with fitz.open(file_location) as doc:
            for page in doc:
                pdf_text += page.get_text()

        if not pdf_text.strip():
            return JSONResponse({"status": "error", "message": "No text found in PDF"})

        # Call Gemini API to summarize
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(
            f"Summarize the following text briefly and clearly:\n\n{pdf_text[:15000]}"
        )
        ai_summary = response.text

        # Save summary in SQLite database
        cursor.execute(
            "INSERT INTO summaries (file_name, summary, created_at) VALUES (?, ?, ?)",
            (file.filename, ai_summary, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()

        return JSONResponse({
            "status": "ok",
            "message": "File analyzed successfully",
            "file_name": file.filename,
            "summary": ai_summary
        })

    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)})

# --- Get All Summaries ---
@app.get("/get_summaries/")
async def get_summaries():
    cursor.execute("SELECT file_name, summary, created_at FROM summaries ORDER BY id DESC")
    rows = cursor.fetchall()
    results = [
        {"file_name": r[0], "summary": r[1], "created_at": r[2]} for r in rows
    ]
    return {"status": "ok", "results": results}
