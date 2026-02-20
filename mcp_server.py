"""
Gomas Legal Engine — MCP Server (dual mode)

Mode 1 (stdio) — Claude Desktop integration:
    python mcp_server.py

Mode 2 (HTTP) — REST MCP endpoints at localhost:8765:
    python mcp_server.py --http

HTTP endpoints:
    GET  /mcp/list                  — all indexed documents
    GET  /mcp/search?q=...          — FTS5 search with BM25 ranking
    GET  /mcp/doc/{id}              — full document metadata + entities
    GET  /mcp/doc/{id}/page/{n}     — page n text from the OCR markdown
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from loguru import logger

import config
import database
import search_engine as se

# ─── Search engine shared instance ───────────────────────────────────────────
_engine = se.SearchEngine(config.INDICES_DIR)


# ══════════════════════════════════════════════════════════════════════════════
# MODE 1 — stdio MCP (Claude Desktop)
# ══════════════════════════════════════════════════════════════════════════════

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Gomas Legal Engine")


@mcp.tool()
def list_documents() -> str:
    """Lists all available legal documents that have been indexed."""
    docs = database.list_documents_db()
    if not docs:
        return "No documents found."
    lines = ["Available Documents:"]
    for doc in docs:
        tipo = doc.get("tipo_documento") or "sin_clasificar"
        conf = doc.get("confianza") or 0.0
        lines.append(
            f"  ID: {doc['id']} | {doc['nombre_archivo']} | {tipo} ({conf*100:.0f}%) | {doc['estado']}"
        )
    return "\n".join(lines)


@mcp.tool()
async def query_legal_docs(query: str, doc_ids: Optional[List[str]] = None) -> str:
    """
    Answers a natural language query about the indexed legal documents.

    Args:
        query: The question to ask (e.g. "¿Quién es el quejoso?").
        doc_ids: Optional list of document IDs to restrict the search. If None, searches all.
    """
    try:
        result = await _engine.query(query, doc_ids)
        answer  = result.get("answer", "Sin respuesta.")
        sources = ", ".join(result.get("sources", []))
        return f"**Respuesta:**\n{answer}\n\n**Fuentes:** {sources}"
    except Exception as exc:
        logger.error(f"MCP query error: {exc}")
        return f"Error: {exc}"


@mcp.tool()
def search_documents(query: str, limit: int = 10) -> str:
    """
    Full-text BM25 search over all indexed documents.
    Returns ranked results with document type, confidence, and summary.

    Args:
        query: Search terms (e.g. "amparo quejoso García").
        limit: Maximum number of results (default 10, max 50).
    """
    results = database.fts_search(query, limit=min(limit, 50))
    if not results:
        return f"No results for: {query}"
    lines = [f"Search results for '{query}':"]
    for r in results:
        lines.append(
            f"  [{r['id']}] {r['nombre_archivo']} — {r.get('tipo_documento','?')} "
            f"({(r.get('confianza') or 0)*100:.0f}%) | {r.get('estado','?')}"
        )
    return "\n".join(lines)


@mcp.tool()
def get_document_entities(doc_id: str) -> str:
    """
    Returns the extracted entities (parties, dates, case numbers, laws) for a document.

    Args:
        doc_id: The numeric document ID.
    """
    try:
        row = database.get_document_by_id(int(doc_id))
    except (ValueError, TypeError):
        return f"Invalid doc_id: {doc_id}"
    if not row:
        return f"Document {doc_id} not found."
    try:
        entidades = json.loads(row.get("entidades") or "{}")
    except Exception:
        entidades = {}
    if not entidades:
        return f"No entities extracted for document {doc_id}."
    lines = [f"Entities for document {doc_id} ({row['nombre_archivo']}):"]
    for key, vals in entidades.items():
        if vals:
            lines.append(f"  {key}: {', '.join(str(v) for v in vals[:5])}")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# MODE 2 — HTTP REST MCP (port 8765)
# ══════════════════════════════════════════════════════════════════════════════

def _build_http_app():
    """Creates and returns a FastAPI app with /mcp/* endpoints."""
    import os
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware

    http_app = FastAPI(title="Gomas MCP HTTP Server", version="2.0.0")
    http_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @http_app.get("/mcp/list")
    def mcp_list():
        """All indexed documents."""
        docs = database.list_documents_db()
        result = []
        for doc in docs:
            try:
                entidades = json.loads(doc.get("entidades") or "{}")
            except Exception:
                entidades = {}
            result.append({
                "id":         str(doc["id"]),
                "filename":   doc["nombre_archivo"],
                "type":       doc.get("tipo_documento"),
                "confidence": doc.get("confianza"),
                "status":     doc.get("estado"),
                "entities":   entidades,
            })
        return result

    @http_app.get("/mcp/search")
    def mcp_search(q: str, limit: int = 10):
        """FTS5 BM25 search."""
        if not q or len(q.strip()) < 2:
            raise HTTPException(status_code=400, detail="Query too short.")
        results = database.fts_search(q.strip(), limit=min(limit, 50))
        return {"query": q, "results": results}

    @http_app.get("/mcp/doc/{doc_id}")
    def mcp_get_doc(doc_id: int):
        """Full document metadata."""
        row = database.get_document_by_id(doc_id)
        if not row:
            raise HTTPException(status_code=404, detail="Document not found.")
        try:
            row["entidades"] = json.loads(row.get("entidades") or "{}")
            row["etiquetas"] = json.loads(row.get("etiquetas") or "[]")
        except Exception:
            pass
        return row

    @http_app.get("/mcp/doc/{doc_id}/page/{page_num}")
    def mcp_get_page(doc_id: int, page_num: int):
        """Returns text of a specific page from the OCR markdown."""
        row = database.get_document_by_id(doc_id)
        if not row:
            raise HTTPException(status_code=404, detail="Document not found.")

        ocr_path = row.get("ocr_path") or ""
        if not ocr_path or not os.path.exists(ocr_path):
            raise HTTPException(status_code=404, detail="OCR file not found for this document.")

        with open(ocr_path, "r", encoding="utf-8") as f:
            content = f.read()

        # OCR files have "## Page N" delimiters
        import re
        pages = re.split(r"^##\s+Page\s+\d+", content, flags=re.MULTILINE)
        pages = [p.strip() for p in pages if p.strip()]

        if page_num < 1 or page_num > len(pages):
            raise HTTPException(
                status_code=404,
                detail=f"Page {page_num} not found. Document has {len(pages)} pages."
            )

        return {
            "doc_id":    doc_id,
            "page":      page_num,
            "total_pages": len(pages),
            "content":   pages[page_num - 1],
        }

    @http_app.get("/health")
    def health():
        return {"status": "ok", "port": config.MCP_HTTP_PORT}

    return http_app


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    database.init_db()

    parser = argparse.ArgumentParser(description="Gomas MCP Server")
    parser.add_argument("--http", action="store_true",
                        help="Run as HTTP server on port " + str(config.MCP_HTTP_PORT))
    args = parser.parse_args()

    if args.http:
        import uvicorn
        http_app = _build_http_app()
        logger.info(f"Starting MCP HTTP server on port {config.MCP_HTTP_PORT}…")
        uvicorn.run(http_app, host="0.0.0.0", port=config.MCP_HTTP_PORT, log_level="info")
    else:
        logger.info("Starting MCP stdio server (Claude Desktop mode)…")
        mcp.run(transport="stdio")
