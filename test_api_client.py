from fastapi.testclient import TestClient
from api import app
import os
import json

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    print("Health check passed.")

def test_list_documents():
    response = client.get("/documents")
    assert response.status_code == 200
    docs = response.json()
    print(f"Documents found: {docs}")
    # We expect at least one doc from our previous integration test
    assert len(docs) > 0
    print("List documents passed.")

def test_query():
    # Helper to check if we have docs
    docs = client.get("/documents").json()
    if not docs:
        print("Skipping query test (no docs found).")
        return

    doc_id = docs[0]['id']
    query_payload = {
        "query": "De qué trata el documento?",
        "doc_ids": [doc_id]
    }
    
    # We might need to mock llm_utils if we don't want real API calls, 
    # but for integration we might want to see if it runs.
    # If ANTHROPIC_API_KEY is not set, it returns mock response anyway.
    
    print(f"Sending query for doc {doc_id}...")
    response = client.post("/query", json=query_payload)
    
    if response.status_code != 200:
        print(f"Query failed: {response.text}")
    
    assert response.status_code == 200
    data = response.json()
    print(f"Answer: {data['answer']}")
    assert "answer" in data
    assert "sources" in data
    print("Query test passed.")

if __name__ == "__main__":
    test_health()
    test_list_documents()
    test_query()
