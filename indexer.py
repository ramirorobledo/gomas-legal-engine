import sys
import os
import logging
import asyncio
import json
from dotenv import load_dotenv

# Add lib to path so we can import 'pageindex'
sys.path.append(os.path.join(os.path.dirname(__file__), "lib", "PageIndex"))

try:
    from pageindex.page_index_md import md_to_tree
    import pageindex.utils as pageindex_utils
except ImportError as e:
    logging.error(f"Failed to import PageIndex. Make sure it is cloned in lib/PageIndex. Error: {e}")
    sys.exit(1)

import config  # loads .env and exposes ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)

import llm_utils

# --- Monkeypatching PageIndex to use Anthropic ---

# Apply patch
logger.info("Patching PageIndex to use Anthropic...")
pageindex_utils.ChatGPT_API_async = llm_utils.PageIndex_LLM_Adapter
pageindex_utils.count_tokens = llm_utils.count_tokens
# We also need to patch synchronous if used, but md_to_tree uses async mostly.
# pageindex_utils.ChatGPT_API = ... (if needed)


async def generate_document_index(md_path: str, output_path: str):
    """
    Generates a hierarchical JSON index from a Markdown file.
    """
    if not os.path.exists(md_path):
        raise FileNotFoundError(f"Markdown file not found: {md_path}")
        
    logger.info(f"Indexing {md_path}...")
    
    # Run PageIndex logic
    # We use default settings suitable for legal docs
    try:
        toc_with_page_number = await md_to_tree(
            md_path=md_path,
            if_thinning=False, # Don't skip sections
            min_token_threshold=1000,
            if_add_node_summary="yes", # We want summaries
            summary_token_threshold=200,
            model="gpt-4", # Passed to satisfy tiktoken, intercepted by adapter
            if_add_doc_description="no",
            if_add_node_text="no",
            if_add_node_id="yes"
        )
        
        # Save to file
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(toc_with_page_number, f, indent=2, ensure_ascii=False)
            
        logger.info(f"Index saved to {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Indexing failed: {e}", exc_info=True)
        raise e

# Async wrapper for main.py (called with await from async pipeline)
async def create_index(md_path: str, doc_id: str, output_dir: str) -> str:
    xml_filename = f"index_{doc_id}.json"
    output_path = os.path.join(output_dir, xml_filename)

    await generate_document_index(md_path, output_path)
    return output_path
