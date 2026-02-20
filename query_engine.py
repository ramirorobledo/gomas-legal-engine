"""
Advanced query engine for Gomas Legal Engine.
Uses Reasoning-based RAG with PageIndex tree structure:
  1. Tree Search  — LLM selects relevant nodes from the TOC
  2. Content Extraction — reads specific line ranges from Markdown
  3. Answer Generation  — LLM answers using extracted context
"""
from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional

from loguru import logger

import llm_utils
import config


class QueryEngine:
    """Performs tree-based reasoning retrieval over indexed legal documents."""

    def __init__(self, indices_dir: str, normalized_dir: str):
        self.indices_dir    = indices_dir
        self.normalized_dir = normalized_dir

    # ─── Index loading ────────────────────────────────────────────────────────

    def load_index(self, doc_id: str) -> Optional[Dict]:
        """Loads the JSON index for a given document ID."""
        path = os.path.join(self.indices_dir, f"index_{doc_id}.json")
        if not os.path.exists(path):
            logger.error(f"Index not found: {path}")
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.error(f"Failed to load index {path}: {exc}")
            return None

    def _get_md_path(self, index_data: Dict) -> str:
        doc_name = index_data.get("doc_name", "")
        if not doc_name:
            return ""
        return os.path.join(self.normalized_dir, f"{doc_name}.md")

    # ─── Main query ───────────────────────────────────────────────────────────

    async def query_document(self, doc_id: str, query: str) -> Dict[str, str]:
        """
        Three-step reasoning RAG for a single document.
        Returns dict with keys: thinking, relevant_nodes, answer (or error).
        """
        index_data = self.load_index(doc_id)
        if not index_data:
            return {"error": "Documento no encontrado o no indexado."}

        # Step 1 — tree search
        thinking_result = await self._tree_search(index_data, query)
        node_ids        = thinking_result.get("node_list", [])
        thinking        = thinking_result.get("thinking", "")

        if not node_ids:
            return {
                "thinking": thinking,
                "answer": "No encontré secciones relevantes para responder tu pregunta.",
            }

        # Step 2 — content extraction
        md_path = self._get_md_path(index_data)
        if not md_path or not os.path.exists(md_path):
            return {
                "thinking": thinking,
                "error": f"Archivo Markdown no encontrado: {md_path}",
            }

        context_text = self._extract_text_for_nodes(node_ids, index_data, md_path)

        # Step 3 — answer generation
        prompt = (
            "Responde la siguiente pregunta basándote ÚNICAMENTE en el contexto provisto.\n\n"
            f"PREGUNTA:\n{query}\n\n"
            f"CONTEXTO:\n{context_text}\n\n"
            "RESPUESTA (en español):"
        )
        answer = await llm_utils.generate_completion(prompt, max_tokens=1500)

        return {
            "thinking": thinking,
            "relevant_nodes": node_ids,
            "answer": answer or "No se pudo generar respuesta.",
        }

    # ─── Step 1: tree search ─────────────────────────────────────────────────

    async def _tree_search(self, index_data: Dict, query: str) -> Dict:
        tree_summary = self._prune_tree_for_search(index_data.get("structure", []))

        prompt = (
            "Tienes una pregunta y la tabla de contenido (árbol) de un documento legal.\n"
            "Cada nodo tiene: node_id, title, summary.\n"
            "Identifica los nodos que probablemente contengan la respuesta.\n\n"
            f"Pregunta: {query}\n\n"
            f"Árbol del documento:\n{json.dumps(tree_summary, indent=2, ensure_ascii=False)}\n\n"
            "Responde ÚNICAMENTE en JSON válido:\n"
            '{\n  "thinking": "<razonamiento>",\n  "node_list": ["0001", "0002"]\n}'
        )

        raw = await llm_utils.generate_completion(prompt, max_tokens=800)

        # Strip markdown code fences if present
        clean = re.sub(r"```(?:json)?", "", raw or "").strip()
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            logger.error(f"Tree search JSON parse failed: {raw!r}")
            return {"thinking": "Error al parsear respuesta LLM.", "node_list": []}

    def _prune_tree_for_search(self, nodes: List[Dict]) -> List[Dict]:
        """Strips full text from tree nodes to save tokens during search."""
        result = []
        for node in nodes:
            summary = node.get("summary") or node.get("prefix_summary", "")
            pruned: Dict = {
                "node_id": node.get("node_id"),
                "title":   node.get("title"),
                "summary": summary,
            }
            children = node.get("nodes", [])
            if children:
                pruned["nodes"] = self._prune_tree_for_search(children)
            result.append(pruned)
        return result

    # ─── Step 2: content extraction ──────────────────────────────────────────

    def _extract_text_for_nodes(
        self, node_ids: List[str], index_data: Dict, md_path: str
    ) -> str:
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as exc:
            logger.error(f"Failed to read {md_path}: {exc}")
            return ""

        # Flatten tree → node_id: line_num mapping
        node_map: Dict[str, int] = {}

        def traverse(nodes: List[Dict]):
            for node in nodes:
                nid = node.get("node_id")
                ln  = node.get("line_num")
                if nid and ln is not None:
                    node_map[nid] = ln
                traverse(node.get("nodes", []))

        traverse(index_data.get("structure", []))

        # Sort all start lines to compute section boundaries
        all_starts = sorted(node_map.values())

        chunks: List[str] = []
        for nid in node_ids:
            if nid not in node_map:
                continue

            start_ln = node_map[nid]
            start_idx = max(start_ln - 1, 0)  # 1-based → 0-based

            # Next section boundary
            end_idx = len(lines)
            for s in all_starts:
                if s > start_ln:
                    end_idx = s - 1
                    break

            # Cap at 500 lines per chunk to avoid context overflow
            if end_idx - start_idx > 500:
                end_idx = start_idx + 500

            chunk = "".join(lines[start_idx:end_idx])
            chunks.append(f"--- Nodo {nid} ---\n{chunk}")

        return "\n\n".join(chunks)
