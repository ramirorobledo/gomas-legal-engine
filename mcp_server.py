import os
import sys
import logging
from typing import List, Optional
from mcp.server.fastmcp import FastMCP
import search_engine

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GomasMCP")

# Initialize Engine
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDICES_DIR = os.path.join(BASE_DIR, "indices")
engine = search_engine.SearchEngine(INDICES_DIR)

# Initialize FastMCP Server
mcp = FastMCP("Gomas Legal Engine")

@mcp.tool()
def list_documents() -> str:
    """
    Lists all available legal documents that have been indexed.
    Returns a formatted string list of ID: Filename.
    """
    docs = engine.list_documents()
    if not docs:
        return "No documents found."
    
    result = "Available Documents:\n"
    for doc in docs:
        result += f"- ID: {doc['id']} | Filename: {doc['filename']}\n"
    return result

@mcp.tool()
async def query_legal_docs(query: str, doc_ids: Optional[List[str]] = None) -> str:
    """
    Answers a natural language query about the legal documents.
    Args:
        query: The question to ask (e.g. "What is the summary of the case?").
        doc_ids: Optional list of document IDs to restrict the search to. If None, searches all.
    """
    try:
        logger.info(f"Querying: {query} (Docs: {doc_ids})")
        result = await engine.query(query, doc_ids)
        
        response = f"**Answer:**\n{result['answer']}\n\n**Sources:**\n{', '.join(result['sources'])}"
        return response
    except Exception as e:
        logger.error(f"Error querying docs: {e}")
        return f"Error: {str(e)}"

if __name__ == "__main__":
    # fastmcp run is usually handled by the CLI, but we can also run programmatically
    # mcp.run()
    # For stdio transport (default for Claude Desktop):
    mcp.run(transport="stdio")
