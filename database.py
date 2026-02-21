"""
Database layer for Gomas Legal Engine.
SQLite with FTS5 full-text search and a persistent job queue.
"""
import sqlite3
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

import config

DB_PATH = config.DB_PATH


# ─── Connection helper ────────────────────────────────────────────────────────

def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Enable WAL for better concurrency
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ─── Schema initialization ────────────────────────────────────────────────────

def init_db():
    """Creates all tables and FTS5 virtual table if they don't exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db_connection()
    cursor = conn.cursor()

    # ── Main documents table ──────────────────────────────────────────────────
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS documentos (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre_archivo    TEXT    NOT NULL,
        ruta_pdf          TEXT    NOT NULL,
        hash_sha256       TEXT    UNIQUE NOT NULL,
        estado            TEXT    DEFAULT 'recibido',
        tipo_documento    TEXT,
        confianza         REAL,
        requiere_revision INTEGER DEFAULT 0,
        paginas           INTEGER,
        fecha_recibido    DATETIME DEFAULT CURRENT_TIMESTAMP,
        fecha_indexado    DATETIME,
        error_mensaje     TEXT,
        ocr_path          TEXT,
        ocr_json_path     TEXT,
        etiquetas         TEXT,
        entidades         TEXT,
        resumen           TEXT,
        norm_path         TEXT
    )
    """)

    # ── Safe column migrations for older DBs ─────────────────────────────────
    _add_column_if_missing(cursor, "documentos", "etiquetas",  "TEXT")
    _add_column_if_missing(cursor, "documentos", "entidades",  "TEXT")
    _add_column_if_missing(cursor, "documentos", "resumen",    "TEXT")
    _add_column_if_missing(cursor, "documentos", "norm_path",  "TEXT")
    _add_column_if_missing(cursor, "documentos", "texto_ocr",  "TEXT")

    # ── FTS5 full-text search virtual table ───────────────────────────────────
    # Check if texto_ocr is already in the FTS schema; if not, migrate.
    fts_needs_migration = False
    try:
        cursor.execute("SELECT texto_ocr FROM documentos_fts LIMIT 1")
    except sqlite3.OperationalError:
        fts_needs_migration = True

    if fts_needs_migration:
        # Drop old triggers and FTS, then recreate with texto_ocr
        cursor.execute("DROP TRIGGER IF EXISTS documentos_ai")
        cursor.execute("DROP TRIGGER IF EXISTS documentos_ad")
        cursor.execute("DROP TRIGGER IF EXISTS documentos_au")
        cursor.execute("DROP TABLE IF EXISTS documentos_fts")

    # content= makes it a content table backed by `documentos`
    cursor.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS documentos_fts USING fts5(
        nombre_archivo,
        tipo_documento,
        etiquetas,
        resumen,
        entidades,
        texto_ocr,
        content='documentos',
        content_rowid='id',
        tokenize='unicode61 remove_diacritics 1'
    )
    """)

    # ── Triggers to keep FTS in sync ──────────────────────────────────────────
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS documentos_ai AFTER INSERT ON documentos BEGIN
        INSERT INTO documentos_fts(rowid, nombre_archivo, tipo_documento,
            etiquetas, resumen, entidades, texto_ocr)
        VALUES (new.id, new.nombre_archivo, COALESCE(new.tipo_documento,''),
            COALESCE(new.etiquetas,''), COALESCE(new.resumen,''),
            COALESCE(new.entidades,''), COALESCE(new.texto_ocr,''));
    END
    """)

    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS documentos_ad AFTER DELETE ON documentos BEGIN
        INSERT INTO documentos_fts(documentos_fts, rowid, nombre_archivo,
            tipo_documento, etiquetas, resumen, entidades, texto_ocr)
        VALUES ('delete', old.id, old.nombre_archivo,
            COALESCE(old.tipo_documento,''), COALESCE(old.etiquetas,''),
            COALESCE(old.resumen,''), COALESCE(old.entidades,''),
            COALESCE(old.texto_ocr,''));
    END
    """)

    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS documentos_au AFTER UPDATE ON documentos BEGIN
        INSERT INTO documentos_fts(documentos_fts, rowid, nombre_archivo,
            tipo_documento, etiquetas, resumen, entidades, texto_ocr)
        VALUES ('delete', old.id, old.nombre_archivo,
            COALESCE(old.tipo_documento,''), COALESCE(old.etiquetas,''),
            COALESCE(old.resumen,''), COALESCE(old.entidades,''),
            COALESCE(old.texto_ocr,''));
        INSERT INTO documentos_fts(rowid, nombre_archivo, tipo_documento,
            etiquetas, resumen, entidades, texto_ocr)
        VALUES (new.id, new.nombre_archivo, COALESCE(new.tipo_documento,''),
            COALESCE(new.etiquetas,''), COALESCE(new.resumen,''),
            COALESCE(new.entidades,''), COALESCE(new.texto_ocr,''));
    END
    """)

    # ── Persistent job queue ──────────────────────────────────────────────────
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS job_queue (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_id      INTEGER NOT NULL,
        intentos    INTEGER DEFAULT 0,
        estado      TEXT    DEFAULT 'pending',
        ultimo_error TEXT,
        created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_job_queue_estado
        ON job_queue(estado)
    """)

    conn.commit()
    conn.close()


def _add_column_if_missing(cursor, table: str, column: str, col_type: str):
    """Safely add a column to an existing table (idempotent)."""
    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
    except sqlite3.OperationalError:
        pass  # Column already exists


# ─── Document CRUD ────────────────────────────────────────────────────────────

def register_document(filename: str, filepath: str, file_hash: str) -> int:
    """Registers a new document. Returns its ID (existing or new)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO documentos (nombre_archivo, ruta_pdf, hash_sha256, estado, fecha_recibido) "
            "VALUES (?, ?, ?, 'recibido', ?)",
            (filename, filepath, file_hash, datetime.now()),
        )
        doc_id = cursor.lastrowid
        conn.commit()
        return doc_id
    except sqlite3.IntegrityError:
        cursor.execute("SELECT id FROM documentos WHERE hash_sha256 = ?", (file_hash,))
        row = cursor.fetchone()
        return row["id"] if row else -1
    finally:
        conn.close()


def update_document_status(doc_id: int, status: str, error_msg: Optional[str] = None):
    conn = get_db_connection()
    if error_msg:
        conn.execute(
            "UPDATE documentos SET estado = ?, error_mensaje = ? WHERE id = ?",
            (status, error_msg, doc_id),
        )
    else:
        conn.execute(
            "UPDATE documentos SET estado = ?, error_mensaje = NULL WHERE id = ?",
            (status, doc_id),
        )
    conn.commit()
    conn.close()


def update_document_classification(
    doc_id: int,
    tipo: str,
    confianza: float,
    etiquetas: list,
    requiere_revision: bool,
    entidades: Optional[dict] = None,
):
    conn = get_db_connection()
    conn.execute(
        "UPDATE documentos SET tipo_documento=?, confianza=?, etiquetas=?, "
        "requiere_revision=?, entidades=?, estado='clasificado' WHERE id=?",
        (
            tipo,
            confianza,
            json.dumps(etiquetas, ensure_ascii=False),
            1 if requiere_revision else 0,
            json.dumps(entidades or {}, ensure_ascii=False),
            doc_id,
        ),
    )
    conn.commit()
    conn.close()


def update_ocr_data(doc_id: int, ocr_path: str, ocr_json_path: str, pages: int,
                    texto_ocr: Optional[str] = None):
    conn = get_db_connection()
    conn.execute(
        "UPDATE documentos SET ocr_path=?, ocr_json_path=?, paginas=?, "
        "texto_ocr=?, estado='ocr_ok' WHERE id=?",
        (ocr_path, ocr_json_path, pages, texto_ocr or "", doc_id),
    )
    conn.commit()
    conn.close()


def populate_ocr_text_from_files():
    """Backfills texto_ocr for existing documents that have ocr_path but no texto_ocr."""
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT id, ocr_path FROM documentos "
        "WHERE ocr_path IS NOT NULL AND (texto_ocr IS NULL OR texto_ocr='')"
    ).fetchall()
    # Convert to plain dicts so connection can be closed before iteration
    rows = [dict(r) for r in rows]
    conn.close()
    updated = 0
    for row in rows:
        ocr_path = row["ocr_path"]
        if ocr_path and os.path.exists(ocr_path):
            try:
                with open(ocr_path, "r", encoding="utf-8") as f:
                    text = f.read().strip()
                if text:
                    conn2 = get_db_connection()
                    conn2.execute("UPDATE documentos SET texto_ocr=? WHERE id=?",
                                  (text, row["id"]))
                    conn2.commit()
                    conn2.close()
                    updated += 1
            except Exception:
                pass
    return updated


def update_norm_path(doc_id: int, norm_path: str):
    conn = get_db_connection()
    conn.execute(
        "UPDATE documentos SET norm_path=?, estado='normalizado' WHERE id=?",
        (norm_path, doc_id),
    )
    conn.commit()
    conn.close()


def update_indexed(doc_id: int, resumen: Optional[str] = None):
    conn = get_db_connection()
    conn.execute(
        "UPDATE documentos SET estado='indexado', fecha_indexado=datetime('now'), "
        "resumen=? WHERE id=?",
        (resumen or "", doc_id),
    )
    conn.commit()
    conn.close()


def get_document_by_hash(file_hash: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM documentos WHERE hash_sha256 = ?", (file_hash,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_document_by_id(doc_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM documentos WHERE id = ?", (doc_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def list_documents_db() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT id, nombre_archivo, estado, tipo_documento, confianza, "
        "fecha_recibido, entidades FROM documentos ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_document(doc_id: int) -> bool:
    conn = get_db_connection()
    cursor = conn.execute("DELETE FROM documentos WHERE id = ?", (doc_id,))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


# ─── FTS5 Search ──────────────────────────────────────────────────────────────

def fts_search(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Full-text search using SQLite FTS5 with BM25 ranking.
    Returns documents sorted by relevance.
    """
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT d.id, d.nombre_archivo, d.tipo_documento, d.confianza,
                   d.estado, d.fecha_recibido, d.entidades, d.resumen,
                   bm25(documentos_fts) AS rank
            FROM documentos_fts
            JOIN documentos d ON d.id = documentos_fts.rowid
            WHERE documentos_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError as e:
        # FTS query syntax error — fall back to LIKE search
        rows = conn.execute(
            "SELECT id, nombre_archivo, tipo_documento, confianza, estado, "
            "fecha_recibido, entidades, resumen FROM documentos "
            "WHERE nombre_archivo LIKE ? OR tipo_documento LIKE ? LIMIT ?",
            (f"%{query}%", f"%{query}%", limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def rebuild_fts_index():
    """Rebuilds the FTS index from scratch (run after bulk imports)."""
    conn = get_db_connection()
    conn.execute("INSERT INTO documentos_fts(documentos_fts) VALUES ('rebuild')")
    conn.commit()
    conn.close()


# ─── Job Queue ────────────────────────────────────────────────────────────────

def enqueue_job(doc_id: int) -> int:
    conn = get_db_connection()
    cursor = conn.execute(
        "INSERT INTO job_queue (doc_id, estado) VALUES (?, 'pending')", (doc_id,)
    )
    job_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return job_id


def get_next_job() -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM job_queue WHERE estado = 'pending' ORDER BY id ASC LIMIT 1"
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE job_queue SET estado='processing', updated_at=datetime('now') WHERE id=?",
            (row["id"],),
        )
        conn.commit()
    conn.close()
    return dict(row) if row else None


def mark_job_done(job_id: int):
    conn = get_db_connection()
    conn.execute(
        "UPDATE job_queue SET estado='done', updated_at=datetime('now') WHERE id=?",
        (job_id,),
    )
    conn.commit()
    conn.close()


def mark_job_failed(job_id: int, error: str):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT intentos FROM job_queue WHERE id=?", (job_id,)
    ).fetchone()
    intentos = (row["intentos"] if row else 0) + 1
    new_estado = "failed" if intentos >= config.MAX_RETRIES else "pending"
    conn.execute(
        "UPDATE job_queue SET estado=?, intentos=?, ultimo_error=?, updated_at=datetime('now') WHERE id=?",
        (new_estado, intentos, error, job_id),
    )
    conn.commit()
    conn.close()
    return new_estado == "failed"   # True → moved to dead letter


def add_to_dead_letter(doc_id: int, reason: str):
    """Updates document status to 'error' and marks job as dead."""
    update_document_status(doc_id, "error", reason)
    conn = get_db_connection()
    conn.execute(
        "UPDATE job_queue SET estado='dead_letter', ultimo_error=?, updated_at=datetime('now') "
        "WHERE doc_id=? AND estado='failed'",
        (reason, doc_id),
    )
    conn.commit()
    conn.close()
