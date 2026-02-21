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
def get_system_info() -> str:
    """
    Returns accurate technical information about the Gomas Legal Engine pipeline.

    Call this tool FIRST whenever the user asks how the system works, what technology
    it uses, how documents are stored, or how queries are processed.

    IMPORTANT: This system does NOT use ChromaDB, Docling, Pinecone, embeddings,
    or any vector database. It uses SQLite FTS5 + Mistral OCR + plain markdown files.
    """
    import os

    docs = database.list_documents_db()
    doc_count = len(docs)
    indexed_count = sum(1 for d in docs if d.get("estado") == "indexado")

    # Check indices dir
    indices_dir = config.INDICES_DIR
    index_files = []
    if os.path.exists(indices_dir):
        index_files = [f for f in os.listdir(indices_dir) if f.endswith(".json")]

    return f"""=== GOMAS LEGAL ENGINE — Arquitectura del sistema ===

PIPELINE DE PROCESAMIENTO (en orden):
  1. PDF de entrada  →  carpeta input/ (vigilada por watchdog main.py)
  2. OCR             →  Mistral API (modelo: mistral-ocr-latest)
                        Convierte PDF a texto Markdown estructurado
                        Preserva encabezados, tablas, formato
  3. Normalización   →  normalizer.py
                        - Detecta y elimina encabezados/pies de página recurrentes
                          (líneas que aparecen en >40% de las páginas)
                        - Elimina ruido OCR, números de página, URLs
                        - Colapsa espacios en blanco excesivos
  4. Clasificación   →  LLM (Claude/Mistral) clasifica tipo de documento
                        (amparo_indirecto, código, ley, sentencia, etc.)
  5. PageIndex       →  vectifyai/PageIndex
                        Genera árbol jerárquico JSON de secciones/artículos
                        Guardado en: {indices_dir}/index_{{id}}.json
  6. SQLite FTS5     →  database.py
                        Base de datos: {config.DB_PATH}
                        Tabla: documentos (metadata + ruta OCR)
                        FTS5: búsqueda full-text con ranking BM25
                        El texto OCR completo se almacena en disco como .md

CÓMO SE RESPONDEN LAS CONSULTAS (query_legal_docs):
  1. FTS5 BM25 encuentra los documentos más relevantes para la query
  2. Se lee el archivo .md del disco (texto OCR completo, SIN truncar)
  3. Para docs pequeños (<180K chars): se envía el texto completo al LLM
  4. Para docs grandes: extracción inteligente de secciones relevantes
     - Si la query menciona artículos específicos ("art. 316") → texto exacto de esos artículos
     - Si no → scoring por keywords en cada sección del documento
  5. Claude genera respuesta basada ÚNICAMENTE en el texto extraído

TECNOLOGÍAS (LO QUE SÍ USAMOS):
  - OCR:       Mistral API (mistral-ocr-latest) → markdown
  - Búsqueda:  SQLite FTS5 con BM25 ranking (sin vectores, sin embeddings)
  - Índice:    PageIndex JSON (árbol jerárquico de secciones)
  - LLM RAG:   Claude/Mistral para síntesis de respuestas
  - API REST:  FastAPI + uvicorn (puerto 8000)
  - Frontend:  Next.js (puerto 3000)

TECNOLOGÍAS QUE NO USAMOS:
  - ChromaDB ✗ | Pinecone ✗ | Weaviate ✗ | FAISS ✗ (sin vectores)
  - Docling ✗ | LangChain ✗ | LlamaIndex ✗
  - Embeddings ✗ | Similarity search ✗

ESTADO ACTUAL:
  - Documentos en base de datos: {doc_count}
  - Documentos indexados: {indexed_count}
  - Archivos PageIndex en disco: {len(index_files)}
  - Directorio de índices: {indices_dir}
  - Base de datos SQLite: {config.DB_PATH}
"""


@mcp.tool()
def list_documents() -> str:
    """
    Lists all available legal documents that have been indexed in this system.

    Returns document ID, filename, document type (amparo_indirecto, código, ley, etc.),
    classification confidence, and processing status.

    Use this to discover available documents before querying them.
    """
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

    HOW IT WORKS (do not invent other mechanisms):
    1. SQLite FTS5 (BM25 ranking) finds the most relevant documents
    2. The full OCR markdown text is read from disk (.md files, NOT from a vector DB)
    3. For large documents, smart extraction finds the specific articles mentioned in the query
    4. Claude generates an answer based ONLY on the extracted text

    This system uses Mistral OCR + SQLite FTS5 + markdown files.
    It does NOT use ChromaDB, Pinecone, embeddings, or any vector database.

    Args:
        query: The question to ask (e.g. "¿Quién es el quejoso?", "¿Qué dice el artículo 316?").
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
    Full-text BM25 search over all indexed documents using SQLite FTS5.
    Returns ranked results with document type, confidence, and summary.

    Use this to find which documents are relevant to a topic before querying them.
    This performs keyword matching with BM25 ranking — NOT semantic/vector search.

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
    Entities are extracted during the indexing pipeline and stored in SQLite.

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


@mcp.tool()
def get_article_text(doc_id: str, article_number: str) -> str:
    """
    Returns the LITERAL text of a specific article directly from the OCR markdown file on disk.
    No LLM synthesis, no interpretation — exact verbatim text as extracted by Mistral OCR.

    Use this when you need the precise legal text of a specific article number.
    Prefer this over query_legal_docs when the user asks for the exact text of a specific article.

    Args:
        doc_id: The numeric document ID (use list_documents or search_documents to find it).
        article_number: The article number to retrieve (e.g. "316", "1o", "490", "1").
    """
    import re, os

    try:
        row = database.get_document_by_id(int(doc_id))
    except (ValueError, TypeError):
        return f"Invalid doc_id: {doc_id}"
    if not row:
        return f"Document {doc_id} not found."

    ocr_path = row.get("ocr_path") or ""
    if not ocr_path or not os.path.exists(ocr_path):
        return f"No OCR file found for document {doc_id}."

    with open(ocr_path, "r", encoding="utf-8") as f:
        ocr_text = f.read()

    # Find the article using the same splitter as search_engine
    pattern = re.compile(
        r'^(#{1,2}\s+Art[ií]culo\s+[\d\w°o\.]+[^\n]*)',
        re.MULTILINE | re.IGNORECASE
    )
    positions = [(m.start(), m.group(1)) for m in pattern.finditer(ocr_text)]
    if not positions:
        return f"No articles found in document {doc_id}."

    num_clean = re.sub(r'[°o\.\s]', '', article_number).lower()
    for i, (start, heading) in enumerate(positions):
        h_num = re.search(r'(\d+)', heading)
        if h_num and re.sub(r'[°o\.\s]', '', h_num.group(1)).lower() == num_clean:
            end = positions[i + 1][0] if i + 1 < len(positions) else len(ocr_text)
            text = ocr_text[start:end].strip()
            return f"[TEXTO LITERAL — {row['nombre_archivo']}]\n\n{text}"

    m_first = re.search(r'(\d+)', positions[0][1])
    m_last  = re.search(r'(\d+)', positions[-1][1])
    first_num = m_first.group(1) if m_first else '?'
    last_num  = m_last.group(1)  if m_last  else '?'
    return (f"Artículo {article_number} no encontrado en documento {doc_id} "
            f"({row['nombre_archivo']}). El documento tiene {len(positions)} artículos "
            f"(del {first_num} al {last_num}).")


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
