"""
Search engine for Gomas Legal Engine.
Combines:
  - In-memory PageIndex JSON cache
  - SQLite FTS5 full-text search with BM25 ranking
  - Semantic context building from hierarchical tree
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from loguru import logger

import database
import llm_utils
import config


class SearchEngine:
    """
    Loads PageIndex JSON trees and answers natural-language queries.
    Uses FTS5 for document discovery, then builds context from tree summaries.
    """

    def __init__(self, indices_dir: str = ""):
        self.indices_dir = indices_dir or config.INDICES_DIR
        self._indices: Dict[str, Any] = {}
        self._refresh()

    # ─── Index management ─────────────────────────────────────────────────────

    def _refresh(self):
        """Scans indices dir and loads / updates cache for changed files."""
        if not os.path.exists(self.indices_dir):
            os.makedirs(self.indices_dir, exist_ok=True)
            return

        for fname in os.listdir(self.indices_dir):
            if fname.startswith("index_") and fname.endswith(".json"):
                doc_id = fname[len("index_"):-len(".json")]
                fpath  = os.path.join(self.indices_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        self._indices[doc_id] = json.load(f)
                except Exception as exc:
                    logger.error(f"Failed to load index {fname}: {exc}")

    def refresh_indices(self):
        """Public alias — also reloads from disk."""
        self._refresh()

    def list_documents(self) -> List[Dict[str, Any]]:
        self._refresh()
        return [
            {"id": doc_id, "filename": f"Document {doc_id}"}
            for doc_id in self._indices
        ]

    # ─── Context building from tree ───────────────────────────────────────────

    def _flatten_tree(self, node: Any, depth: int = 0) -> str:
        """Recursively converts a PageIndex tree node to readable text."""
        if not isinstance(node, dict):
            return ""
        indent = "  " * depth
        text   = ""

        title   = node.get("title") or node.get("header", "")
        summary = node.get("summary", "")

        if title:
            text += f"{indent}## {title}\n"
        if summary:
            text += f"{indent}{summary}\n"

        # Recurse into known children keys
        for key, val in node.items():
            if key in ("title", "header", "summary", "node_id", "line_num",
                       "id", "content", "prefix_summary"):
                continue
            if isinstance(val, dict):
                text += self._flatten_tree(val, depth + 1)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, dict):
                        text += self._flatten_tree(item, depth + 1)

        return text

    def _build_context_for_doc(self, doc_id: str) -> str:
        """Returns text context for a document.
        Prefers full OCR text from disk; falls back to PageIndex tree summaries."""
        # ── Try to read the full OCR text from the database ───────────────────
        try:
            row = database.get_document_by_id(int(doc_id))
            if row:
                ocr_path = row.get("ocr_path") or ""
                if ocr_path and os.path.exists(ocr_path):
                    with open(ocr_path, "r", encoding="utf-8") as f:
                        ocr_text = f.read().strip()
                    if ocr_text:
                        return ocr_text
        except Exception as exc:
            logger.warning(f"Could not read OCR file for doc {doc_id}: {exc}")

        # ── Fallback: PageIndex tree summaries ────────────────────────────────
        tree = self._indices.get(doc_id)
        if not tree:
            return ""
        if isinstance(tree, dict):
            structure = tree.get("structure", tree)
        else:
            structure = tree
        if isinstance(structure, list):
            return "\n".join(self._flatten_tree(node) for node in structure)
        return self._flatten_tree(structure)

    # ─── FTS-assisted query ───────────────────────────────────────────────────

    async def query(
        self, query: str, doc_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Answers a natural-language query.
        If doc_ids is None, first runs FTS5 to find the most relevant docs,
        then builds context from their trees.
        """
        self._refresh()

        # ── Determine which documents to use ──────────────────────────────────
        if doc_ids:
            target_ids = doc_ids
        else:
            # Try FTS5 for relevance-ranked discovery
            try:
                fts_results = database.fts_search(query, limit=5)
                target_ids  = [str(r["id"]) for r in fts_results]
                logger.info(f"FTS5 returned {len(target_ids)} docs for query: {query!r}")
            except Exception as exc:
                logger.warning(f"FTS5 search failed ({exc}); using all indexed docs.")
                target_ids = list(self._indices.keys())

        if not target_ids:
            target_ids = list(self._indices.keys())

        # ── Build context ──────────────────────────────────────────────────────
        context_parts: List[str] = []
        used_ids: List[str] = []

        for did in target_ids:
            if did not in self._indices:
                logger.warning(f"Doc ID {did!r} not in index cache.")
                continue
            ctx = self._build_context_for_doc(did)
            if ctx:
                context_parts.append(f"=== Documento {did} ===\n{ctx}")
                used_ids.append(did)

        if not context_parts:
            return {
                "answer": "No hay documentos indexados disponibles para responder.",
                "sources": [],
            }

        full_context = "\n\n".join(context_parts)

        # ── Semantic chunking (token-aware instead of char truncation) ─────────
        # Rough estimate: 1 token ≈ 4 chars; Claude Haiku context ≈ 200k tokens
        MAX_CONTEXT_CHARS = 180_000  # leaves room for prompt + answer
        if len(full_context) > MAX_CONTEXT_CHARS:
            # Keep whole section blocks, don't cut mid-sentence
            truncated = full_context[:MAX_CONTEXT_CHARS]
            last_break = max(
                truncated.rfind("\n\n"), truncated.rfind("\n===")
            )
            if last_break > MAX_CONTEXT_CHARS // 2:
                truncated = truncated[:last_break]
            full_context = truncated + "\n\n[CONTEXTO TRUNCADO]"
            logger.warning("Context truncated to fit model limits.")

        # ── LLM answer ────────────────────────────────────────────────────────
        prompt = (
            "Eres un asistente jurídico experto. Responde la pregunta del usuario "
            "basándote ÚNICAMENTE en los resúmenes de documentos legales proporcionados.\n"
            "Si la respuesta no está en los documentos, indícalo claramente.\n\n"
            f"DOCUMENTOS:\n{full_context}\n\n"
            f"PREGUNTA DEL USUARIO:\n{query}\n\n"
            "RESPUESTA:"
        )

        answer = await llm_utils.generate_completion(prompt, max_tokens=2048)

        return {
            "answer": answer or "No se pudo generar respuesta.",
            "sources": used_ids,
        }
