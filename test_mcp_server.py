import asyncio
import os
import sys
from mcp.server.fastmcp import FastMCP

# Add current dir to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def test_mcp_logic():
    print("Testing MCP Server Logic...")
    
    # Import the server instance
    try:
        from mcp_server import list_documents, query_legal_docs
        print("✅ Imported mcp_server successfully.")
    except ImportError as e:
        print(f"❌ Failed to import mcp_server: {e}")
        return

    # Test list_documents
    print("\n--- Testing list_documents ---")
    try:
        docs = list_documents()
        print(f"Result:\n{docs}")
        if "Available Documents" in docs or "No documents found" in docs:
            print("✅ list_documents passed.")
        else:
            print("❌ list_documents returned unexpected format.")
    except Exception as e:
        print(f"❌ list_documents failed: {e}")

    # Test query_legal_docs
    print("\n--- Testing query_legal_docs ---")
    try:
        # queries need to be awaited if async
        response = await query_legal_docs("Resumen del documento", doc_ids=None)
        print(f"Result:\n{response}")
        if "**Answer:**" in response:
            print("✅ query_legal_docs passed.")
        else:
            print("❌ query_legal_docs returned unexpected format.")
    except Exception as e:
        print(f"❌ query_legal_docs failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_mcp_logic())
