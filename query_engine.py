
import json
import logging
import os
from typing import Dict, List, Optional
import llm_utils

logger = logging.getLogger(__name__)

class QueryEngine:
import json
import logging
import os
import re
from typing import Dict, List, Optional
import llm_utils

logger = logging.getLogger(__name__)

class QueryEngine:
    def __init__(self, indices_dir: str, normalized_dir: str):
        self.indices_dir = indices_dir
        self.normalized_dir = normalized_dir

    def load_index(self, doc_id: str) -> Optional[Dict]:
        """Loads the JSON index for a specific document ID."""
        filename = f"index_{doc_id}.json"
        path = os.path.join(self.indices_dir, filename)
        
        if not os.path.exists(path):
            logger.error(f"Index not found at {path}")
            return None
            
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load index: {e}")
            return None

    def _get_md_path(self, index_data: Dict) -> str:
        """Constructs the path to the normalized markdown file."""
        doc_name = index_data.get('doc_name')
        if not doc_name:
            return ""
        return os.path.join(self.normalized_dir, f"{doc_name}.md")

    async def query_document(self, doc_id: str, query: str) -> Dict[str, str]:
        """
        Answers a query using Reasoning-based RAG:
        1. Tree Search: LLM selects relevant nodes from the index TOC.
        2. Content Extraction: System reads specific lines from the Markdown file.
        3. Answer Generation: LLM answers using the specific context.
        """
        index_data = self.load_index(doc_id)
        if not index_data:
            return {"error": "Documento no encontrado o no indexado."}

        # Step 1: Tree Search
        # We perform a "Thinking" step where the LLM selects nodes.
        thinking_result = await self._tree_search(index_data, query)
        node_ids = thinking_result.get('node_list', [])
        thinking_process = thinking_result.get('thinking', '')

        if not node_ids:
            return {
                "thinking": thinking_process,
                "answer": "No encontré secciones relevantes en el índice del documento para responder a tu pregunta."
            }

        # Step 2: Content Extraction
        md_path = self._get_md_path(index_data)
        if not md_path or not os.path.exists(md_path):
             return {
                "thinking": thinking_process,
                "error": f"Archivo fuente Markdown no encontrado: {md_path}"
            }
            
        context_text = self._extract_text_for_nodes(node_ids, index_data, md_path)
        
        # Step 3: Answer Generation
        prompt = f"""
        Answer the question based ONLY on the provided context.
        
        QUESTION:
        {query}
        
        CONTEXT:
        {context_text}
        
        ANSWER (in Spanish):
        """
        
        answer = await llm_utils.generate_completion(prompt, max_tokens=1000)
        
        return {
            "thinking": thinking_process,
            "relevant_nodes": node_ids,
            "answer": answer
        }

    async def _tree_search(self, index_data: Dict, query: str) -> Dict:
        """
        Asks LLM to select relevant nodes from the tree structure.
        """
        # Create a lightweight version of the tree (titles & summaries only)
        tree_summary = self._prune_tree_for_search(index_data['structure'])
        
        prompt = f"""
        You are given a question and a Table of Contents (tree structure) of a document.
        Each node contains a node_id, title, and summary.
        Your task is to identify the nodes that are likely to contain the answer.

        Question: {query}

        Document Tree:
        {json.dumps(tree_summary, indent=2, ensure_ascii=False)}

        Reply in valid JSON format:
        {{
            "thinking": "<Reasoning about which nodes are relevant>",
            "node_list": ["node_id_1", "node_id_2"]
        }}
        Current nodes are 4-digit strings (e.g. "0001").
        """
        
        response_text = await llm_utils.generate_completion(prompt, max_tokens=1000)
        
        # Parse JSON from response
        try:
            # Clean potential markdown code blocks
            clean_json = response_text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_json)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse Tree Search JSON: {response_text}")
            return {"thinking": "Error parsing LLM response", "node_list": []}

    def _prune_tree_for_search(self, nodes: List[Dict]) -> List[Dict]:
        """
        Recursively creates a summary tree without the full text, to save tokens.
        """
        summary_nodes = []
        for node in nodes:
            new_node = {
                "title": node.get("title"),
                "node_id": node.get("node_id"),
                "summary": node.get("summary") or node.get("prefix_summary", ""),
            }
            if "nodes" in node and node["nodes"]:
                new_node["nodes"] = self._prune_tree_for_search(node["nodes"])
            summary_nodes.append(new_node)
        return summary_nodes

    def _extract_text_for_nodes(self, node_ids: List[str], index_data: Dict, md_path: str) -> str:
        """
        Reads the Markdown file and extracts lines corresponding to the selected nodes.
        Uses a flattened map of the tree to find line numbers.
        """
        # 1. Read all lines
        try:
            with open(md_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            logger.error(f"Failed to read MD file {md_path}: {e}")
            return ""

        # 2. Flatten tree to map node_id -> info
        node_map = {}
        
        def traverse(nodes: List[Dict]):
            for i, node in enumerate(nodes):
                nid = node.get("node_id")
                if nid:
                    node_map[nid] = {
                        "line_num": node.get("line_num"),
                        # We might need next node's line to know where this one ends
                        # But the PageIndex structure implies hierarchical.
                        # Simplification: We extract from line_num up to a reasonable length 
                        # OR we rely on the flattened list order to find the next start.
                    }
                if "nodes" in node:
                    traverse(node["nodes"])
        
        traverse(index_data['structure'])
        
        # To determine end lines, we need a sorted list of all starting lines
        all_starts = sorted([info['line_num'] for info in node_map.values() if info['line_num'] is not None])
        
        extracted_chunks = []
        
        for nid in node_ids:
            if nid not in node_map:
                continue
            
            start_line_idx = node_map[nid]['line_num'] - 1 # 1-based to 0-based
            
            # Find the next start line to define the end of this chunk
            # This is a heuristic. Ideally PageIndex gives end_index or we infer it from next sibling/child.
            # Using the next available line number in the document is a safe bet for "until the next section".
            
            next_start = None
            for s in all_starts:
                if s > node_map[nid]['line_num']:
                    next_start = s
                    break
            
            if next_start:
                end_line_idx = next_start - 1
            else:
                end_line_idx = len(lines) # Read until end
            
            # Limit chunk size just in case (e.g. 500 lines) to avoid context overflow if structure is sparse
            if end_line_idx - start_line_idx > 500:
                end_line_idx = start_line_idx + 500
                
            chunk_text = "".join(lines[start_line_idx:end_line_idx])
            extracted_chunks.append(f"--- Node {nid} ---\n{chunk_text}")
            
        return "\n\n".join(extracted_chunks)

# Singleton or factory if needed
