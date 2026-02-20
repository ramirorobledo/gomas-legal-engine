import os
import shutil
import logging
import sqlite3
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import search_engine
import database

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GomasAPI")

# Initialize DB
try:
    database.init_db()
except Exception as e:
    logger.error(f"Failed to initialize database: {e}")

app = FastAPI(title="Gomas Legal Engine API", version="0.1.0")

# CORS Configuration
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    
)

# Initialize Engine
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDICES_DIR = os.path.join(BASE_DIR, "indices")
INPUT_DIR = os.path.join(BASE_DIR, "input")

# Ensure Input Dir
os.makedirs(INPUT_DIR, exist_ok=True)

engine = search_engine.SearchEngine(INDICES_DIR)

class QueryRequest(BaseModel):
    query: str
    doc_ids: Optional[List[str]] = None

class QueryResponse(BaseModel):
    answer: str
    sources: List[str]

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/documents")
def list_documents():
    """
    Returns list of available documents with status from DB.
    """
    # 1. Get indexed docs from Search Engine (cache)
    # indexed_docs = engine.list_documents() 
    # Actually, better to query DB directly for status of ALL docs including processing ones.
    
    try:
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nombre_archivo, estado, tipo_documento, confianza, fecha_recibido FROM documentos ORDER BY id DESC")
        rows = cursor.fetchall()
        conn.close()
        
        docs = []
        for row in rows:
            docs.append({
                "id": str(row['id']),
                "filename": row['nombre_archivo'],
                "status": row['estado'],
                "type": row['tipo_documento'],
                "confidence": row['confianza'],
                "processed_at": row['fecha_recibido']
            })
        return docs
    except Exception as e:
        logger.error(f"Failed to fetch docs from DB: {e}")
        raise HTTPException(status_code=500, detail="Database error")

@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Uploads a PDF file to the input directory to trigger processing.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")
    
    try:
        # Save to input directory
        file_location = os.path.join(INPUT_DIR, file.filename)
        
        # Check if exists to avoid overwrite issues or handle duplicates
        # For now, simple overwrite or rename logic could be added. 
        # Using basic overwrite.
        
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        logger.info(f"File uploaded: {file.filename}")
        
        return {"filename": file.filename, "message": "File uploaded successfully. Processing started."}
        
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.post("/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest):
    """
    Answers a query based on selected documents.
    """
    try:
        result = await engine.query(request.query, request.doc_ids)
        return QueryResponse(**result)
    except Exception as e:
        logger.error(f"Query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
