import time
import os
import shutil
import sqlite3
import json
from reportlab.pdfgen import canvas

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(BASE_DIR, "input")
OCR_OUTPUT_DIR = os.path.join(BASE_DIR, "ocr_output")
NORMALIZED_DIR = os.path.join(BASE_DIR, "normalized")
DB_PATH = os.path.join(BASE_DIR, "db", "gomas_legal.db")

def create_classified_test_pdf(filename, doc_type="amparo"):
    filepath = os.path.join(INPUT_DIR, filename)
    c = canvas.Canvas(filepath)
    if doc_type == "amparo":
        c.drawString(100, 750, "AMPARO DIRECTO EN REVISIÓN")
        c.drawString(100, 700, "TRIBUNAL COLEGIADO DE CIRCUITO")
        c.drawString(100, 650, "QUEJOSO: Juan Pérez")
    elif doc_type == "sentencia":
        c.drawString(100, 750, "SENTENCIA DEFINITIVA")
        c.drawString(100, 700, "CAUSA PENAL 123/2024")
    else:
        c.drawString(100, 750, "Documento genérico sin clasificación clara")
        
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

def wait_for_state(filename, target_state, timeout=20):
    start_time = time.time()
    while time.time() - start_time < timeout:
        row = verify_db(filename)
        if row:
            print(f"Current state: {row['estado']}")
            if row['estado'] == target_state:
                return row
        time.sleep(1)
    return None

def main():
    print("Starting Phase 2 Integration Test...")
    
    # Test 1: Amparo Directo
    filename = "test_amparo.pdf"
    if os.path.exists(os.path.join(INPUT_DIR, filename)):
        os.remove(os.path.join(INPUT_DIR, filename))
        
    print(f"Creating {filename} (Expect: Amparo Directo)...")
    create_classified_test_pdf(filename, "amparo")
    
    row = wait_for_state(filename, "indexado", timeout=60) # Increased timeout for indexing
    
    if row:
        print(f"SUCCESS: Document processed to 'indexado'")
        print(f"Type: {row['tipo_documento']}")
        print(f"Confidence: {row['confianza']}")
        print(f"Tags: {row['etiquetas']}")
        
        if row['tipo_documento'] == 'amparo_directo':
            print("✅ Classification Correct: Amparo Directo")
        else:
            print(f"❌ Classification Failed: Expected amparo_directo, got {row['tipo_documento']}")
            
        # Check normalized file existence
        # We need doc_id to find the file
        # md_path usually is basename_id.md
        # norm file is norm_basename_id.md
        norm_files = os.listdir(NORMALIZED_DIR)
        found_norm = False
        for f in norm_files:
            if str(row['id']) in f:
                found_norm = True
                print(f"✅ Normalized file found: {f}")
                break
        if not found_norm:
            print("❌ Normalized file NOT found")
            
        # Check index file existence
        indices_dir = os.path.join(BASE_DIR, "indices")
        index_files = os.listdir(indices_dir) if os.path.exists(indices_dir) else []
        found_index = False
        for f in index_files:
            if str(row['id']) in f and f.endswith(".json"):
                found_index = True
                print(f"✅ Index file found: {f}")
                break
        if not found_index:
             print("❌ Index file NOT found")
            
    else:
        print("❌ Timeout waiting for classification.")

if __name__ == "__main__":
    main()
