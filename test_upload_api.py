from fastapi.testclient import TestClient
from api import app
import os
import shutil

client = TestClient(app)

INPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "input")
TEST_PDF = "test_upload.pdf"

def setup_test_file():
    # Create a dummy PDF file for testing
    with open(TEST_PDF, "wb") as f:
        f.write(b"%PDF-1.4 header dummy content")

def cleanup():
    if os.path.exists(TEST_PDF):
        os.remove(TEST_PDF)
    # Remove from input dir if it got there
    uploaded_path = os.path.join(INPUT_DIR, TEST_PDF)
    if os.path.exists(uploaded_path):
        os.remove(uploaded_path)

def test_upload_success():
    setup_test_file()
    try:
        with open(TEST_PDF, "rb") as f:
            response = client.post("/upload", files={"file": (TEST_PDF, f, "application/pdf")})
        
        # Verify API response
        print(f"Upload Response: {response.json()}")
        assert response.status_code == 200
        assert response.json()["filename"] == TEST_PDF
        
        # Verify file existence in input dir
        uploaded_path = os.path.join(INPUT_DIR, TEST_PDF)
        assert os.path.exists(uploaded_path)
        print("✅ File upload verification successful")
        
    finally:
        cleanup()

def test_upload_invalid_type():
    # Create a txt file
    with open("test.txt", "w") as f:
        f.write("Not a PDF")
    
    try:
        with open("test.txt", "rb") as f:
            response = client.post("/upload", files={"file": ("test.txt", f, "text/plain")})
        
        print(f"Invalid Type Response: {response.json()}")
        assert response.status_code == 400
        print("✅ Invalid file type rejection successful")
        
    finally:
        if os.path.exists("test.txt"):
            os.remove("test.txt")

if __name__ == "__main__":
    print("Testing Upload API...")
    test_upload_success()
    test_upload_invalid_type()
    print("All upload tests passed.")
