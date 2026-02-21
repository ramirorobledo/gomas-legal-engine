"""
Gomas Legal Engine — Pipeline Watcher
Monitors the input directory for new PDFs and processes them through:
  1. File stabilization + magic bytes validation
  2. SHA-256 deduplication
  3. OCR  (Mistral API or PyMuPDF fallback)
  4. Normalization
  5. Classification + entity extraction
  6. PageIndex indexing
  7. FTS5 index update
"""
from __future__ import annotations

import asyncio
import os
import shutil
import sys
import time

from loguru import logger
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

import config
import database
import utils

# ─── Loguru setup ─────────────────────────────────────────────────────────────
logger.remove()  # Remove default handler
logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
)
logger.add(
    os.path.join(config.LOG_DIR, "gomas_engine.log"),
    rotation="10 MB",
    retention="30 days",
    level="DEBUG",
    encoding="utf-8",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} | {message}",
)


# ─── Magic bytes validation ───────────────────────────────────────────────────

def is_valid_pdf(filepath: str) -> bool:
    """Verifies the file starts with the PDF magic bytes %PDF."""
    try:
        with open(filepath, "rb") as f:
            header = f.read(4)
        return header == b"%PDF"
    except OSError:
        return False


# ─── Pipeline ─────────────────────────────────────────────────────────────────

async def _run_pipeline(filepath: str):
    """
    Full async pipeline for one PDF.
    Raises on unrecoverable error so the caller can handle dead-letter logic.
    """
    import ocr_service
    import normalizer
    import classifier
    import indexer

    filename = os.path.basename(filepath)

    # 1. Stabilization
    if not utils.wait_for_file_stabilization(filepath):
        raise RuntimeError(f"File {filename} did not stabilize.")

    # 2. Magic bytes
    if not is_valid_pdf(filepath):
        raise ValueError(f"File {filename} is not a valid PDF (bad magic bytes).")

    # 3. Deduplication
    file_hash   = utils.calculate_file_hash(filepath)
    existing    = database.get_document_by_hash(file_hash)

    if existing and existing.get("estado") == "indexado":
        logger.info(f"Duplicate (already indexed): {filename} — skipping.")
        return

    if existing:
        doc_id = existing["id"]
        logger.info(f"Re-processing incomplete document ID {doc_id}: {filename}")
    else:
        doc_id = database.register_document(filename, filepath, file_hash)
        logger.info(f"Registered new document ID {doc_id}: {filename}")

    job_id = database.enqueue_job(doc_id)

    # 4. Move to processing staging
    proc_path = os.path.join(config.PROCESSING_DIR, filename)
    utils.safe_move(filepath, proc_path)

    # 5. OCR
    logger.info(f"[{doc_id}] Starting OCR…")
    md_path, json_path, pages = ocr_service.process_pdf_ocr(
        proc_path, config.OCR_OUTPUT_DIR, str(doc_id)
    )
    database.update_ocr_data(doc_id, md_path, json_path, pages)
    logger.info(f"[{doc_id}] OCR done — {pages} pages.")

    # 6. Normalization
    logger.info(f"[{doc_id}] Normalizing…")
    if not md_path or not os.path.exists(md_path):
        raise FileNotFoundError(f"OCR Markdown missing: {md_path}")

    with open(md_path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    clean_text = normalizer.clean_markdown(raw_text)

    norm_filename = f"norm_{os.path.basename(md_path)}"
    norm_path     = os.path.join(config.NORMALIZED_DIR, norm_filename)
    with open(norm_path, "w", encoding="utf-8") as f:
        f.write(clean_text)

    database.update_norm_path(doc_id, norm_path)

    # 7. Classification + entity extraction
    logger.info(f"[{doc_id}] Classifying…")
    result = classifier.classify_document(clean_text)
    database.update_document_classification(
        doc_id,
        result["tipo"],
        result["confianza"],
        result["etiquetas"],
        result["requiere_revision"],
        result.get("entidades", {}),
    )
    logger.info(
        f"[{doc_id}] Classified as '{result['tipo']}' "
        f"(conf={result['confianza']:.2f}, review={result['requiere_revision']})"
    )

    if result["requiere_revision"] and not config.FORCE_INDEXING:
        logger.warning(f"[{doc_id}] Sent to review queue (low confidence).")
        shutil.copy(proc_path, os.path.join(config.REVIEW_QUEUE_DIR, filename))
        database.mark_job_done(job_id)
        return

    # 8. Indexing
    logger.info(f"[{doc_id}] Indexing with PageIndex…")
    os.makedirs(config.INDICES_DIR, exist_ok=True)
    index_path = await indexer.create_index(norm_path, str(doc_id), config.INDICES_DIR)
    database.update_indexed(doc_id)
    logger.success(f"[{doc_id}] Indexed → {index_path}")

    database.mark_job_done(job_id)


def process_document_sync(filepath: str):
    """
    Synchronous wrapper around the async pipeline with retry + dead-letter queue.
    """
    filename = os.path.basename(filepath)

    for attempt in range(config.MAX_RETRIES):
        try:
            asyncio.run(_run_pipeline(filepath))
            return  # success
        except Exception as exc:
            wait = 2 ** attempt
            logger.warning(
                f"Pipeline error for {filename} (attempt {attempt + 1}/{config.MAX_RETRIES}): {exc}"
            )
            if attempt < config.MAX_RETRIES - 1:
                time.sleep(wait)
            else:
                # All retries exhausted → dead letter
                logger.error(f"Moving {filename} to dead-letter queue after {config.MAX_RETRIES} failures.")
                dead_path = os.path.join(config.DEAD_LETTER_DIR, filename)
                try:
                    if os.path.exists(filepath):
                        shutil.move(filepath, dead_path)
                    elif os.path.exists(os.path.join(config.PROCESSING_DIR, filename)):
                        shutil.move(os.path.join(config.PROCESSING_DIR, filename), dead_path)
                except Exception as move_exc:
                    logger.error(f"Failed to move to dead letter: {move_exc}")

                # Try to find doc_id and record error
                try:
                    file_hash = utils.calculate_file_hash(
                        dead_path if os.path.exists(dead_path) else filepath
                    )
                    doc = database.get_document_by_hash(file_hash)
                    if doc:
                        database.add_to_dead_letter(doc["id"], str(exc))
                except Exception:
                    pass


# ─── Watchdog Handler ─────────────────────────────────────────────────────────

class LegalDocumentHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        if not event.src_path.lower().endswith(".pdf"):
            return
        logger.info(f"New PDF detected: {event.src_path}")
        process_document_sync(event.src_path)


# ─── Entrypoint ───────────────────────────────────────────────────────────────

def main():
    logger.info("Gomas Legal Engine starting…")

    database.init_db()
    logger.info("Database initialized.")

    # Process any PDFs already sitting in input/
    existing = [
        f for f in os.listdir(config.INPUT_DIR) if f.lower().endswith(".pdf")
    ]
    if existing:
        logger.info(f"Processing {len(existing)} pre-existing file(s) in input/…")
        for fname in existing:
            fpath = os.path.join(config.INPUT_DIR, fname)
            try:
                process_document_sync(fpath)
            except Exception as exc:
                logger.error(f"Error processing existing file {fname}: {exc}")

    handler  = LegalDocumentHandler()
    observer = Observer()
    observer.schedule(handler, config.INPUT_DIR, recursive=False)
    observer.start()
    logger.info(f"Watching {config.INPUT_DIR} for new PDFs…")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping watcher…")
        observer.stop()
    observer.join()
    logger.info("Watcher stopped.")


if __name__ == "__main__":
    main()
