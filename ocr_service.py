import os
import json
import logging
from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage
# Check Mistral SDK version for OCR support, or use direct HTTP request if SDK is not yet ready for OCR-specific endpoint
# For now, using a placeholder for Mistral OCR API call as per brief.
# Brief says: Endpoint : https://api.mistral.ai/v1/ocr, Model : mistral-ocr-2512

import requests
from dotenv import load_dotenv

load_dotenv()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
OCR_ENDPOINT = "https://api.mistral.ai/v1/ocr"

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

    # MBO: mocking actual API call for now if no key is present or for testing
    # In production, this would make a real request
    if not MISTRAL_API_KEY or MISTRAL_API_KEY.startswith("FAJA"):
        logger.warning("MISTRAL_API_KEY not found or invalid. Using mock OCR.")
        return _mock_ocr(filepath, md_output_path, json_output_path)

    try:
        with open(filepath, "rb") as f:
            file_content = f.read()

        headers = {
            "Authorization": f"Bearer {MISTRAL_API_KEY}"
        }
        
        files = {
            'file': (filename, file_content, 'application/pdf')
        }
        
        data = {
            'model': 'mistral-ocr-2512',
            'purpose': 'ocr'
        }
        
        logger.info(f"Sending {filename} to Mistral OCR (model: mistral-ocr-2512)...")
        
        response = requests.post(OCR_ENDPOINT, headers=headers, files=files, data=data)
        
        if response.status_code != 200:
            logger.error(f"Mistral OCR API Error: {response.status_code} - {response.text}")
            raise Exception(f"Mistral OCR API Error: {response.status_code} - {response.text}")
            
        result = response.json()
        
        # Process Mistral Response
        # Expected response structure based on documentation:
        # { "pages": [ { "index": 0, "markdown": "...", "images": [...] }, ... ] }
        
        full_markdown = ""
        pages_data = []
        
        if "pages" in result:
            for page in result["pages"]:
                page_md = page.get("markdown", "")
                page_idx = page.get("index", 0)
                
                # Add page delimiter for context
                full_markdown += f"## Page {page_idx + 1}\n\n{page_md}\n\n"
                
                pages_data.append({
                    "page": page_idx + 1,
                    "text": page_md,
                    # specific dimensions might not be in basic response, handled if present
                    "dimensions": {
                        "width": page.get("dimensions", {}).get("width", 0),
                        "height": page.get("dimensions", {}).get("height", 0)
                    }
                })
        else:
             logger.warning("Unexpected Mistral response format: 'pages' key missing.")
             # Fallback or dump raw usage?
             full_markdown = result.get("markdown", "") # unexpected fallback
        
        final_md = f"# OCR Result for {os.path.basename(filepath)}\n\n{full_markdown}"
        
        # Save Markdown
        with open(md_output_path, "w", encoding="utf-8") as f:
            f.write(final_md)
            
        # Save JSON
        ocr_json = {
            "pages": pages_data,
            "meta": {
                "model": "mistral-ocr-2512",
                "pages": len(pages_data),
                "usage": result.get("usage", {})
            }
        }
        
        with open(json_output_path, "w", encoding="utf-8") as f:
            json.dump(ocr_json, f, indent=2)
            
        logger.info(f"OCR successfully processed {len(pages_data)} pages.")
        return md_output_path, json_output_path, len(pages_data)

    except Exception as e:
        logger.error(f"OCR failed: {e}")
        # In production, we might want to re-raise. For dev continuity, fallback?
        # User requested replacing "tapa-huecos", implying reliance on real API.
        # But if no key, we returned early. If API fails, better to raise so we know it failed.
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
