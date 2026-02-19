import re
import ftfy

def clean_markdown(text: str) -> str:
    """
    Applies deterministic cleaning rules to Markdown text derived from legal OCR.
    Removes headers, footers, excessive whitespace, and OCR artifacts.
    """
    # 1. Fix encoding issues
    text = ftfy.fix_text(text)
    
    # 2. Normalize line breaks
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    # 3. Remove common header/footer artifacts
    # Pattern: Page numbers (e.g., "Página 1 de 5", "1/5", "- 1 -")
    text = re.sub(r'^\s*(Página|Page)?\s*\d+\s*(de|of|/)\s*\d+\s*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
    text = re.sub(r'^\s*-\s*\d+\s*-\s*$', '', text, flags=re.MULTILINE)
    
    # Pattern: Common legal headers repeated on every page (simplified example)
    # text = re.sub(r'(?m)^.*?EXPEDIENTE.*?$', '', text) # CAREFUL: This might delete valid content if not specific enough
    
    # 4. Remove OCR noise
    # Remove lines that are just non-alphanumeric noise (e.g. "_ . , ;")
    text = re.sub(r'(?m)^\W+$', '', text)
    
    # 5. Collapse excessive vertical whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()
