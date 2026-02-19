import sqlite3
import os
from datetime import datetime
from typing import Optional, Dict, Any
import json

DB_PATH = os.path.join(os.path.dirname(__file__), "db", "gomas_legal.db")

def init_db():
    """Initializes the SQLite database with the required schema."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS documentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre_archivo TEXT NOT NULL,
        ruta_pdf TEXT NOT NULL,
        hash_sha256 TEXT UNIQUE NOT NULL,
        estado TEXT DEFAULT 'recibido',
        tipo_documento TEXT,
        confianza REAL,
        requiere_revision INTEGER DEFAULT 0,
        paginas INTEGER,
        fecha_recibido DATETIME DEFAULT CURRENT_TIMESTAMP,
        fecha_indexado DATETIME,
        error_mensaje TEXT,
        ocr_path TEXT,
        ocr_json_path TEXT,
        etiquetas TEXT
    )
    ''')
    
    # Migration for existing DBs during dev
    try:
        cursor.execute("ALTER TABLE documentos ADD COLUMN etiquetas TEXT")
    except sqlite3.OperationalError:
        pass
    
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def register_document(filename: str, filepath: str, file_hash: str) -> int:
    """Registers a new document or returns ID of existing one."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "INSERT INTO documentos (nombre_archivo, ruta_pdf, hash_sha256, estado, fecha_recibido) VALUES (?, ?, ?, ?, ?)",
            (filename, filepath, file_hash, 'recibido', datetime.now())
        )
        doc_id = cursor.lastrowid
        conn.commit()
        return doc_id
    except sqlite3.IntegrityError:
        # Document already exists (duplicate hash)
        cursor.execute("SELECT id FROM documentos WHERE hash_sha256 = ?", (file_hash,))
        result = cursor.fetchone()
        conn.close()
        return result['id'] if result else -1
    finally:
        conn.close()

def update_document_status(doc_id: int, status: str, error_msg: Optional[str] = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if error_msg:
        cursor.execute(
            "UPDATE documentos SET estado = ?, error_mensaje = ? WHERE id = ?",
            (status, error_msg, doc_id)
        )
    else:
        cursor.execute(
            "UPDATE documentos SET estado = ?, error_mensaje = NULL WHERE id = ?",
            (status, doc_id)
        )
    conn.commit()
    conn.close()

def update_document_classification(doc_id: int, tipo: str, confianza: float, etiquetas: list, requiere_revision: bool):
    conn = get_db_connection()
    cursor = conn.cursor()
    tags_str = json.dumps(etiquetas)
    cursor.execute(
        "UPDATE documentos SET tipo_documento = ?, confianza = ?, etiquetas = ?, requiere_revision = ?, estado = 'clasificado' WHERE id = ?",
        (tipo, confianza, tags_str, 1 if requiere_revision else 0, doc_id)
    )
    conn.commit()
    conn.close()

def update_ocr_data(doc_id: int, ocr_path: str, ocr_json_path: str, pages: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE documentos SET ocr_path = ?, ocr_json_path = ?, paginas = ?, estado = 'ocr_ok' WHERE id = ?",
        (ocr_path, ocr_json_path, pages, doc_id)
    )
    conn.commit()
    conn.close()

def get_document_by_hash(file_hash: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documentos WHERE hash_sha256 = ?", (file_hash,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None
