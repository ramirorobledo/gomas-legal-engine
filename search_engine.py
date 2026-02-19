import os
import json
import logging
import asyncio
from typing import List, Dict, Any
import llm_utils

logger = logging.getLogger(__name__)

class SearchEngine:
    def __init__(self, indices_dir: str):
        self.indices_dir = indices_dir
        self.indices = {} # Cache of loaded indices
        self.refresh_indices()

    def refresh_indices(self):
        """
        Scans the indices directory and loads all JSON index files.
        """
        if not os.path.exists(self.indices_dir):
            os.makedirs(self.indices_dir, exist_ok=True)
            return

        for filename in os.listdir(self.indices_dir):
            if filename.endswith(".json") and filename.startswith("index_"):
                # format: index_{doc_id}.json
                try:
                    doc_id = filename.replace("index_", "").replace(".json", "")
                    filepath = os.path.join(self.indices_dir, filename)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        self.indices[doc_id] = json.load(f)
                except Exception as e:
                    logger.error(f"Failed to load index {filename}: {e}")

    def list_documents(self) -> List[Dict[str, Any]]:
        """
        Returns a list of available documents.
        """
        self.refresh_indices()
        return [{"id": doc_id, "filename": f"Document {doc_id}"} for doc_id in self.indices.keys()]

    def _get_document_context(self, doc_id: str) -> str:
        """
        Extracts a textual representation of the document tree for the LLM.
        For now, we dump the tree structure with summaries.
        In the future, we can do semantic search over nodes.
        """
        if doc_id not in self.indices:
            return ""
        
        tree = self.indices[doc_id]
        
        # Helper to recursively build text
        def build_text(params, level=0):
            text = ""
            indent = "  " * level
            
            # PageIndex tree structure usually has a root dict or list
            # Checking structure based on PageIndex output
            # Usually: {"1": {...}, "2": {...}} or similar
            
            if isinstance(params, dict):
                # Check for node keys
                title = params.get("title", "Untitled")
                summary = params.get("summary", "")
                content = params.get("content", "") # If available (we set if_add_node_text="no")
                
                text += f"{indent}- {title}\n"
                if summary:
                    text += f"{indent}  Summary: {summary}\n"
                
                # Children
                for k, v in params.items():
                    if isinstance(v, (dict, list)) and k not in ["summary", "content", "title", "id"]:
                        text += build_text(v, level + 1)
            
            elif isinstance(params, list):
                for item in params:
                    text += build_text(item, level)
            
            return text

        return build_text(tree)

    def _flatten_tree_text(self, node, depth=0):
         # Recursively flatten the tree into a readable string
         text = ""
         indent = "  " * depth
         
         # Handle unexpected node types
         if not isinstance(node, dict):
             return ""

         # Extract title/header if present (PageIndex structure varies)
         # It often uses keys like "1", "1.1" etc for structure, but let's look for standard keys
         # If node has 'title' or 'header'
         title = node.get("title", node.get("header", ""))
         if title:
            text += f"{indent}{title}\n"
            
         summary = node.get("summary", "")
         if summary:
            text += f"{indent}Summary: {summary}\n"
            
         # Recurse values that are dicts (children)
         for key, value in node.items():
             if isinstance(value, dict):
                 text += self._flatten_tree_text(value, depth + 1)
             elif isinstance(value, list): # List of children
                 for item in value:
                    if isinstance(item, dict):
                        text += self._flatten_tree_text(item, depth + 1)
                        
         return text

    async def query(self, query: str, doc_ids: List[str] = None) -> Dict[str, Any]:
        """
        Answers a query based on the selected documents.
        """
        self.refresh_indices()
        
        if not doc_ids:
            # If no docs specified, use all (be careful with context window)
            doc_ids = list(self.indices.keys())
        
        context_parts = []
        for doc_id in doc_ids:
            if doc_id in self.indices:
                # context = self._get_document_context(doc_id)
                # Let's try a simpler dump for now
                context = json.dumps(self.indices[doc_id], indent=2, ensure_ascii=False)
                # Truncate if too huge? PageIndex summaries should be concise.
                context_parts.append(f"Document {doc_id}:\n{context}")
            else:
                logger.warning(f"Doc ID {doc_id} not found locally.")

        full_context = "\n\n".join(context_parts)
        
        # Limit context to avoid overflow (rough heuristic)
        # Using haiku, we have 200k context, so we are likely fine for a few docs.
        # But let's be safe.
        if len(full_context) > 100000:
             full_context = full_context[:100000] + "... [TRUNCATED]"

        prompt = f"""
        You are a legal assistant. Answer the user's question based ONLY on the provided document summaries.
        The documents are provided as hierarchical JSON trees containing summaries of sections.
        
        If the answer is not in the documents, say "I cannot answer based on the provided documents."
        
        DOCUMENTS:
        {full_context}
        
        USER QUESTION:
        {query}
        
        ANSWER:
        """
        
        answer = await llm_utils.generate_completion(prompt, model="claude-3-haiku-20240307")
        
        return {
            "answer": answer,
            "sources": doc_ids 
        }

# Global instance
# engine = SearchEngine(os.path.join(os.path.dirname(__file__), "indices"))
