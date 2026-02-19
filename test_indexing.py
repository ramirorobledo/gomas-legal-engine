import time
import os
import shutil
import sqlite3
import json
from reportlab.pdfgen import canvas

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(BASE_DIR, "input")
INDICES_DIR = os.path.join(BASE_DIR, "indices")
DB_PATH = os.path.join(BASE_DIR, "db", "gomas_legal.db")

def create_indexable_pdf(filename):
    filepath = os.path.join(INPUT_DIR, filename)
    c = canvas.Canvas(filepath)
    c.drawString(100, 750, "AMPARO DIRECTO EN REVISIÓN")
    c.drawString(100, 700, "TRIBUNAL COLEGIADO DE CIRCUITO")
    c.drawString(100, 650, "QUEJOSO: Maria Lopez")
    c.drawString(100, 600, "CONSIDERANDO PRIMERO. Competencia.")
    c.drawString(100, 550, "CONSIDERANDO SEGUNDO. Oportunidad.")
    c.save()
    return filepath

def verify_db(filename):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documentos WHERE nombre_archivo = ?", (filename,))
    row = cursor.fetchone()
    conn.close()
    return row

def wait_for_state(filename, target_state, timeout=30):
    start_time = time.time()
    while time.time() - start_time < timeout:
        row = verify_db(filename)
        if row:
            print(f"Current state: {row['estado']}")
            if row['estado'] == target_state:
                return row
            if row['estado'] == 'error':
                 print(f"ERROR: {row['error_mensaje']}")
                 return None
        time.sleep(1)
    return None

def main():
    print("Starting Phase 3 Integration Test (Indexing)...")
    
    filename = "test_indexing.pdf"
    if os.path.exists(os.path.join(INPUT_DIR, filename)):
        os.remove(os.path.join(INPUT_DIR, filename))
        
    print(f"Creating {filename}...")
    create_indexable_pdf(filename)
    
    row = wait_for_state(filename, "indexado")
    
    if row:
        print(f"SUCCESS: Document processed to 'indexado'")
        
        # Check index file
        doc_id = row['id']
        expected_index = os.path.join(INDICES_DIR, f"index_{doc_id}.json")
        
        if os.path.exists(expected_index):
            print(f"✅ Index file found: {expected_index}")
            with open(expected_index, 'r') as f:
                content = json.load(f)
                print("Index content snippet:", str(content)[:200])
        else:
            print(f"❌ Index file NOT found at {expected_index}")
            
    else:
        print("❌ Timeout or Error waiting for indexing.")

if __name__ == "__main__":
    main()
