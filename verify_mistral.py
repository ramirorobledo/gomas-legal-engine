import os
import sys
import logging
import shutil
from ocr_service import process_pdf_ocr

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("validation_script")

def test_mistral_integration():
    # Input file
    input_pdf = os.path.join("input", "Convenio Marco.pdf")
    if not os.path.exists(input_pdf):
        logger.error(f"Input file not found: {input_pdf}")
        return

    # Create a small test PDF (first page only) to save time/cost if possible, 
    # but process_pdf_ocr takes a filepath. 
    # Let's just use the full file if it's small, or maybe slice it first?
    # Convenio Marco.pdf is 6MB. Might be many pages. 
    # Let's slice it to 1 page for the test to avoid burning tokens on a huge doc if it fails.
    
    import fitz
    doc = fitz.open(input_pdf)
    subset_pdf_path = os.path.join("input", "test_subset_mistral.pdf")
    
    # Save only first 2 pages
    new_doc = fitz.open()
    new_doc.insert_pdf(doc, from_page=0, to_page=1)
    new_doc.save(subset_pdf_path)
    new_doc.close()
    
    logger.info(f"Created subset PDF for testing: {subset_pdf_path}")
    
    output_dir = "ocr_output_validation"
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir)
    
    logger.info("Starting OCR processing with Mistral...")
    try:
        md_path, json_path, pages = process_pdf_ocr(subset_pdf_path, output_dir, "test_doc_001")
        
        logger.info(f"Processing complete!")
        logger.info(f"Markdown Path: {md_path}")
        logger.info(f"JSON Path: {json_path}")
        logger.info(f"Pages Processed: {pages}")
        
        # Verify Content
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
            if len(content) < 100:
                logger.error("Markdown content seems too short!")
            else:
                logger.info("Markdown content looks substantial.")
                print("\n--- SAMPLE MARKDOWN ---\n")
                print(content[:500])
                print("\n-----------------------\n")
                
    except Exception as e:
        logger.error(f"Verification Failed: {e}")

if __name__ == "__main__":
    test_mistral_integration()
