"""
Gomas Legal Engine — FastAPI REST server
Improvements:
  - CORS origins from config (env var)
  - Optional API key auth (Authorization: Bearer <key>)
  - Rate limiting via slowapi (100 req/min per IP)
  - Structured logging with loguru
  - New endpoints: DELETE /documents/{id}, GET /documents/{id}/entities,
                   GET /search?q=..., GET /documents/{id}
  - SSE /events endpoint (replaces 5s polling)
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
from typing import List, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

import config
import database
import search_engine as se

# ─── Database init ────────────────────────────────────────────────────────────
try:
    database.init_db()
    logger.info("Database initialized.")
except Exception as exc:
    logger.error(f"Database init failed: {exc}")

# ─── Rate limiter ─────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

# ─── FastAPI app ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Gomas Legal Engine API",
    version="2.0.0",
    description="AI-powered Mexican legal document processing pipeline.",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ─── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Search engine singleton ──────────────────────────────────────────────────
engine = se.SearchEngine(config.INDICES_DIR)


# ─── Optional API key auth ────────────────────────────────────────────────────

def _check_api_key(request: Request):
    """If API_KEY is configured in .env, enforce Bearer token auth."""
    if not config.API_KEY:
        return  # auth disabled
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer ") or auth[7:] != config.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")


# ─── Pydantic models ──────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str
    doc_ids: Optional[List[str]] = None


class QueryResponse(BaseModel):
    answer: str
    sources: List[str]


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health_check():
    return {"status": "ok", "version": "2.0.0"}


# ─── Documents ────────────────────────────────────────────────────────────────

@app.get("/documents", dependencies=[Depends(_check_api_key)])
@limiter.limit("120/minute")
def list_documents(request: Request):
    """Lists all documents tracked in the database."""
    try:
        docs = database.list_documents_db()
        result = []
        for row in docs:
            try:
                entidades = json.loads(row.get("entidades") or "{}")
            except Exception:
                entidades = {}
            result.append({
                "id":           str(row["id"]),
                "filename":     row["nombre_archivo"],
                "status":       row["estado"],
                "type":         row["tipo_documento"],
                "confidence":   row["confianza"],
                "processed_at": row["fecha_recibido"],
                "entities":     entidades,
            })
        return result
    except Exception as exc:
        logger.error(f"list_documents failed: {exc}")
        raise HTTPException(status_code=500, detail="Database error.")


@app.get("/documents/{doc_id}", dependencies=[Depends(_check_api_key)])
@limiter.limit("60/minute")
def get_document(request: Request, doc_id: int):
    """Returns full metadata for a single document."""
    row = database.get_document_by_id(doc_id)
    if not row:
        raise HTTPException(status_code=404, detail="Document not found.")
    try:
        entidades = json.loads(row.get("entidades") or "{}")
        etiquetas = json.loads(row.get("etiquetas") or "[]")
    except Exception:
        entidades, etiquetas = {}, []
    return {**row, "entidades": entidades, "etiquetas": etiquetas}


@app.get("/documents/{doc_id}/entities", dependencies=[Depends(_check_api_key)])
@limiter.limit("60/minute")
def get_document_entities(request: Request, doc_id: int):
    """Returns only the extracted entities for a document."""
    row = database.get_document_by_id(doc_id)
    if not row:
        raise HTTPException(status_code=404, detail="Document not found.")
    try:
        entidades = json.loads(row.get("entidades") or "{}")
    except Exception:
        entidades = {}
    return {"doc_id": doc_id, "entities": entidades}


@app.delete("/documents/{doc_id}", dependencies=[Depends(_check_api_key)])
@limiter.limit("20/minute")
def delete_document(request: Request, doc_id: int):
    """Removes a document record from the database."""
    deleted = database.delete_document(doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"message": f"Document {doc_id} deleted."}


# ─── Search ───────────────────────────────────────────────────────────────────

@app.get("/search", dependencies=[Depends(_check_api_key)])
@limiter.limit("60/minute")
def search_documents(request: Request, q: str, limit: int = 10):
    """Full-text BM25 search over indexed documents."""
    if not q or len(q.strip()) < 2:
        raise HTTPException(status_code=400, detail="Query too short.")
    results = database.fts_search(q.strip(), limit=min(limit, 50))
    return {"query": q, "results": results}


# ─── Upload ───────────────────────────────────────────────────────────────────

@app.post("/upload", dependencies=[Depends(_check_api_key)])
@limiter.limit("30/minute")
async def upload_document(request: Request, file: UploadFile = File(...)):
    """Uploads a PDF to the input directory (triggers the pipeline watcher)."""
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")
    dest = os.path.join(config.INPUT_DIR, file.filename)
    try:
        with open(dest, "wb") as buf:
            shutil.copyfileobj(file.file, buf)
        logger.info(f"Uploaded: {file.filename}")
        return {"filename": file.filename, "message": "File uploaded — processing started."}
    except Exception as exc:
        logger.error(f"Upload failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}")


# ─── Query ────────────────────────────────────────────────────────────────────

@app.post("/query", response_model=QueryResponse, dependencies=[Depends(_check_api_key)])
@limiter.limit("30/minute")
async def query_documents(request: Request, body: QueryRequest):
    """Answers a natural-language query over indexed documents."""
    if not body.query or len(body.query.strip()) < 3:
        raise HTTPException(status_code=400, detail="Query too short.")
    try:
        result = await engine.query(body.query.strip(), body.doc_ids)
        return QueryResponse(**result)
    except Exception as exc:
        logger.error(f"Query failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ─── SSE — real-time document updates ────────────────────────────────────────

@app.get("/events")
async def document_events(request: Request):
    """
    Server-Sent Events stream.
    Frontend can replace 5-second polling with EventSource('/events').
    """
    async def generator():
        last_count = -1
        while True:
            if await request.is_disconnected():
                break
            try:
                docs = database.list_documents_db()
                count = len(docs)
                if count != last_count:
                    last_count = count
                    payload = json.dumps({
                        "count": count,
                        "documents": [
                            {
                                "id":       str(d["id"]),
                                "filename": d["nombre_archivo"],
                                "status":   d["estado"],
                                "type":     d["tipo_documento"],
                                "confidence": d["confianza"],
                            }
                            for d in docs
                        ],
                    })
                    yield f"data: {payload}\n\n"
            except Exception:
                pass
            await asyncio.sleep(2)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ─── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=False,
    )
