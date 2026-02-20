import sys
import time
import logging
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import database
import utils
import ocr_service
import normalizer
import classifier
from dotenv import load_dotenv

# Setup Logging
log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(__file__), "logs", "gomas_engine.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("GomasEngine")

# Load Env
load_dotenv()

# Directories
BASE_DIR = os.path.dirname(__file__)
INPUT_DIR = os.path.join(BASE_DIR, "input")
PROCESSING_DIR = os.path.join(BASE_DIR, "processing")
OCR_OUTPUT_DIR = os.path.join(BASE_DIR, "ocr_output")
NORMALIZED_DIR = os.path.join(BASE_DIR, "normalized")
REVIEW_QUEUE_DIR = os.path.join(BASE_DIR, "review_queue")

class LegalDocumentHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        if not event.src_path.lower().endswith(".pdf"):
            logger.info(f"Ignoring non-PDF file: {event.src_path}")
            return
            
        logger.info(f"New PDF detected: {event.src_path}")
        self.process_document(event.src_path)

    def process_document(self, filepath):
        filename = os.path.basename(filepath)
        
        # 1. Stabilization
        if not utils.wait_for_file_stabilization(filepath):
            logger.warning(f"File {filename} not stable or disappeared. Skipping.")
            return

        # 2. Hashing & Deduplication
        file_hash = utils.calculate_file_hash(filepath)
        existing_doc = database.get_document_by_hash(file_hash)
        
        doc_id = -1
        current_state = ""
        
        if existing_doc:
            logger.info(f"Document {filename} already exists (ID: {existing_doc['id']}). Skipping OCR.")
            doc_id = existing_doc['id']
            # If it was previously errored or incomplete, we might want to resume?
            # For now, we assume if it exists in DB, OCR was at least attempted or completed.
            # We can move it to processed to clear the input folder if it's a re-drop.
        else:
            doc_id = database.register_document(filename, filepath, file_hash)
            logger.info(f"Registered new document ID: {doc_id}")

        # 3. Move to Processing (Staging)
        processing_path = os.path.join(PROCESSING_DIR, filename)
        utils.safe_move(filepath, processing_path)
        
        try:
            # 4. OCR
            if current_state in ['ocr_ok', 'normalizado', 'clasificado', 'indexado']:
                logger.info(f"Document {doc_id} already has valid OCR. Skipping.")
                if existing_doc:
                    md_path = existing_doc['ocr_path']
            else:
                logger.info(f"Starting OCR for doc ID: {doc_id}")
                md_path, json_path, pages = ocr_service.process_pdf_ocr(processing_path, OCR_OUTPUT_DIR, str(doc_id))
                database.update_ocr_data(doc_id, md_path, json_path, pages)
                logger.info(f"OCR completed for doc ID: {doc_id}")

            # 5. Normalization
            logger.info(f"Starting Normalization for doc ID: {doc_id}")
            
            if not md_path or not os.path.exists(md_path):
                 raise FileNotFoundError(f"OCR Markdown file not found: {md_path}")
                 
            with open(md_path, 'r', encoding='utf-8') as f:
                raw_text = f.read()
            
            try:
                clean_text = normalizer.clean_markdown(raw_text)
            except Exception as e:
                logger.error(f"Normalizer crashed: {e}")
                raise e
            
            norm_filename = f"norm_{os.path.basename(md_path)}"
            norm_path = os.path.join(NORMALIZED_DIR, norm_filename)
            
            with open(norm_path, 'w', encoding='utf-8') as f:
                f.write(clean_text)
                
            database.update_document_status(doc_id, "normalizado")
            
            # 6. Classification
            logger.info(f"Starting Classification for doc ID: {doc_id}")
            class_result = classifier.classify_document(clean_text)
            
            database.update_document_classification(
                doc_id, 
                class_result['tipo'], 
                class_result['confianza'], 
                class_result['etiquetas'], 
                class_result['requiere_revision']
            )
            
            logger.info(f"Classified doc {doc_id} as {class_result['tipo']} (Conf: {class_result['confianza']})")
            
            if class_result['requiere_revision']:
                logger.warning(f"Document {doc_id} requires manual review.")
                # Optionally copy to review queue folder?
                # shutil.copy(processing_path, os.path.join(REVIEW_QUEUE_DIR, filename))
            
            # 7. Indexing
            logger.info(f"Starting Indexing for doc ID: {doc_id}")
            
            # FORCE INDEXING for now (Phase 3 Review UI not ready)
            # if not class_result['requiere_revision']:
            if True: 
                import indexer
                indices_dir = os.path.join(BASE_DIR, "indices")
                os.makedirs(indices_dir, exist_ok=True)
                
                index_path = indexer.create_index(norm_path, str(doc_id), indices_dir)
                database.update_document_status(doc_id, "indexado")
                # We should save index path to DB too? Schema has `fecha_indexado`.
                # Let's add `fecha_indexado` update.
                conn = database.get_db_connection()
                conn.execute("UPDATE documentos SET fecha_indexado = datetime('now') WHERE id = ?", (doc_id,))
                conn.commit()
                conn.close()
                logger.info(f"Indexing completed. Saved to {index_path}")
            
            if class_result['requiere_revision']:
                 logger.warning(f"Document {doc_id} flagged for review (but indexed for testing).")
            
        except Exception as e:
            logger.error(f"Error processing {filename}: {e}", exc_info=True)
            database.update_document_status(doc_id, "error", str(e))

def main():
    print("DEBUG: Starting main...")
    # Init
    try:
        database.init_db()
        print("DEBUG: Database initialized.")
    except Exception as e:
        print(f"DEBUG: Database init failed: {e}")
        return
    
    # Ensure directories
    for d in [INPUT_DIR, PROCESSING_DIR, OCR_OUTPUT_DIR]:
        os.makedirs(d, exist_ok=True)
    print("DEBUG: Directories ensured.")

    logging.info(f"Gomas Legal Engine Watcher started.")
    print("DEBUG: Logger initialized.")
    
    event_handler = LegalDocumentHandler()
    
    # Process existing files in INPUT_DIR
    print("DEBUG: Scanning for existing files in input/...")
    for filename in os.listdir(INPUT_DIR):
        if filename.lower().endswith(".pdf"):
            filepath = os.path.join(INPUT_DIR, filename)
            print(f"DEBUG: Found existing file: {filename}")
            try:
                event_handler.process_document(filepath)
            except Exception as e:
                logger.error(f"Error processing existing file {filename}: {e}")

    observer = Observer()
    observer.schedule(event_handler, INPUT_DIR, recursive=False)
    try:
        observer.start()
        print("DEBUG: Observer started.")
    except Exception as e:
        print(f"DEBUG: Observer start failed: {e}")
        return
    
    try:
        while True:
            time.sleep(1)
            # print("DEBUG: Watcher alive...") # excessive noise, maybe just on start is enough. 
            # actually better to not spam. I'll rely on the start message.
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()
