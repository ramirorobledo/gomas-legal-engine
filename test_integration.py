import time
import os
import shutil
import sqlite3
import json
from reportlab.pdfgen import canvas

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(BASE_DIR, "input")
OCR_OUTPUT_DIR = os.path.join(BASE_DIR, "ocr_output")
DB_PATH = os.path.join(BASE_DIR, "db", "gomas_legal.db")

def create_test_pdf(filename):
    filepath = os.path.join(INPUT_DIR, filename)
    c = canvas.Canvas(filepath)
    c.drawString(100, 750, "This is a test legal document.")
    c.drawString(100, 700, "CONFIDENTIAL")
    c.save()
    return filepath

def verify_db(filename):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documentos WHERE nombre_archivo = ?", (filename,))
    row = cursor.fetchone()
    conn.close()
    return row

def main():
    print("Starting integration test...")
    test_filename = "test_document.pdf"
    
    # Clean up previous run
    if os.path.exists(os.path.join(INPUT_DIR, test_filename)):
        os.remove(os.path.join(INPUT_DIR, test_filename))
    
    # 1. Create PDF
    print(f"Creating {test_filename} in input folder...")
    create_test_pdf(test_filename)
    
    # 2. Wait for processing (give it 10 seconds max)
    print("Waiting for processing...")
    start_time = time.time()
    processed = False
    
    while time.time() - start_time < 20:
        # check if moved from input (it might be in processing or done)
        if not os.path.exists(os.path.join(INPUT_DIR, test_filename)):
            print("File moved from input folder.")
            processed = True
            break
        time.sleep(1)
        
    if not processed:
        print("ERROR: File was not picked up by watcher.")
        return

    # 3. Check for OCR output
    # The filename might have the doc_id appended, so we need to valid loosely or query DB first
    row = None
    for _ in range(5):
        row = verify_db(test_filename)
        if row and row[4] == 'ocr_ok': # index 4 is 'estado'
            print(f"DB Record found: ID={row[0]}, Status={row[4]}")
            break
        time.sleep(1)
        
    if not row:
        print("ERROR: DB record not found or status not updated.")
        return

    doc_id = row[0]
    expected_md = os.path.join(OCR_OUTPUT_DIR, f"test_document_{doc_id}.md")
    expected_json = os.path.join(OCR_OUTPUT_DIR, f"test_document_{doc_id}.json")
    
    if os.path.exists(expected_md) and os.path.exists(expected_json):
        print("SUCCESS: OCR output files generated.")
        with open(expected_md, 'r') as f:
            print(f"MD Content Preview: {f.read()[:50]}...")
    else:
        print(f"ERROR: OCR output files missing. Expected: {expected_md}")
        
if __name__ == "__main__":
    main()
