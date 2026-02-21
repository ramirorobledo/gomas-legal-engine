import os
import json
import logging
import base64
from mistralai import Mistral
from dotenv import load_dotenv

load_dotenv()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

logger = logging.getLogger(__name__)

def process_pdf_ocr(filepath: str, output_dir: str, doc_id: str) -> tuple[str, str, int]:
    """
    Sends PDF to Mistral OCR, saves Markdown and JSON results.
    Returns (markdown_path, json_path, number_of_pages)
    """
    filename = os.path.basename(filepath)
    base_name = os.path.splitext(filename)[0]

    md_output_path = os.path.join(output_dir, f"{base_name}_{doc_id}.md")
    json_output_path = os.path.join(output_dir, f"{base_name}_{doc_id}.json")

    if not MISTRAL_API_KEY:
        logger.warning("MISTRAL_API_KEY not found. Using local PyMuPDF OCR.")
        return _mock_ocr(filepath, md_output_path, json_output_path)

    try:
        with open(filepath, "rb") as f:
            file_content = f.read()

        pdf_base64 = base64.standard_b64encode(file_content).decode("utf-8")

        logger.info(f"Sending {filename} to Mistral OCR...")

        client = Mistral(api_key=MISTRAL_API_KEY)
        result = client.ocr.process(
            model="mistral-ocr-latest",
            document={
                "type": "document_url",
                "document_url": f"data:application/pdf;base64,{pdf_base64}"
            }
        )

        full_markdown = ""
        pages_data = []

        for page in result.pages:
            page_md = page.markdown or ""
            page_idx = page.index

            full_markdown += f"## Page {page_idx + 1}\n\n{page_md}\n\n"

            pages_data.append({
                "page": page_idx + 1,
                "text": page_md,
                "dimensions": {
                    "width": getattr(page, "width", 0),
                    "height": getattr(page, "height", 0)
                }
            })

        final_md = f"# OCR Result for {filename}\n\n{full_markdown}"

        with open(md_output_path, "w", encoding="utf-8") as f:
            f.write(final_md)

        ocr_json = {
            "pages": pages_data,
            "meta": {
                "model": "mistral-ocr-latest",
                "pages": len(pages_data)
            }
        }

        with open(json_output_path, "w", encoding="utf-8") as f:
            json.dump(ocr_json, f, indent=2)

        logger.info(f"OCR successfully processed {len(pages_data)} pages.")
        return md_output_path, json_output_path, len(pages_data)

    except Exception as e:
        logger.error(f"OCR failed: {e}")
        raise e

import fitz  # PyMuPDF

def _mock_ocr(filepath: str, md_path: str, json_path: str) -> tuple[str, str, int]:
    """
    Mock OCR that actually extracts text from digital PDFs using PyMuPDF.
    This allows testing classification rules with generated PDFs.
    """
    logger.info(f"Performing LOCAL OCR (PyMuPDF) on {filepath}")
    
    doc = fitz.open(filepath)
    text = ""
    pages_data = []
    
    for i, page in enumerate(doc):
        page_text = page.get_text()
        text += f"## Page {i+1}\n\n{page_text}\n\n"
        
        pages_data.append({
            "page": i+1,
            "text": page_text,
            "dimensions": {"width": page.rect.width, "height": page.rect.height}
        })
        
    full_md = f"# OCR Result for {os.path.basename(filepath)}\n\n{text}"
    
    mock_json = {
        "pages": pages_data,
        "meta": {
            "model": "local-pymupdf-mock",
            "pages": len(doc)
        }
    }
    
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(full_md)
        
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(mock_json, f, indent=2)
        
    return md_path, json_path, len(doc)
