import re
from collections import Counter
import ftfy


def _detect_recurring_lines(pages: list[str], threshold: float = 0.4) -> set[str]:
    """
    Detects lines that appear in more than `threshold` fraction of pages.
    These are recurring headers/footers and should be removed.
    Ignores empty lines and very short lines (< 4 chars).
    """
    total_pages = len(pages)
    if total_pages < 3:
        return set()

    # Count in how many pages each line appears
    line_page_count = Counter()
    for page_text in pages:
        # Use a set per page so one line counts once per page
        seen_in_page = set()
        for line in page_text.splitlines():
            stripped = line.strip()
            if len(stripped) >= 4:
                seen_in_page.add(stripped)
        for line in seen_in_page:
            line_page_count[line] += 1

    # Lines appearing in >= threshold of all pages are headers/footers
    min_pages = max(2, int(total_pages * threshold))
    recurring = {
        line for line, count in line_page_count.items()
        if count >= min_pages
    }
    return recurring


def _split_pages(text: str) -> list[str]:
    """Split OCR markdown into per-page chunks using '## Page N' markers."""
    parts = re.split(r'^##\s+Page\s+\d+', text, flags=re.MULTILINE)
    # First part is the file header (before Page 1), rest are page bodies
    return [p.strip() for p in parts if p.strip()]


def _remove_recurring_lines(text: str, recurring: set[str]) -> str:
    """Remove all recurring header/footer lines from the full text."""
    if not recurring:
        return text
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        if line.strip() not in recurring:
            cleaned.append(line)
    return "\n".join(cleaned)


def clean_markdown(text: str) -> str:
    """
    Applies deterministic cleaning to Markdown OCR text of legal documents.

    Steps:
    1. Fix encoding
    2. Auto-detect and remove recurring page headers/footers
    3. Remove standard OCR artifacts (page numbers, noise)
    4. Collapse excessive whitespace
    """
    # 1. Fix encoding issues
    text = ftfy.fix_text(text)

    # 2. Normalize line breaks
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # 3. Auto-detect recurring headers/footers across pages
    pages = _split_pages(text)
    if len(pages) >= 3:
        recurring = _detect_recurring_lines(pages, threshold=0.4)
        if recurring:
            text = _remove_recurring_lines(text, recurring)

    # 4. Remove standard page number patterns
    #    e.g. "Página 1 de 5", "1/5", "- 1 -", "Pág. 2 de 168"
    text = re.sub(
        r'^\s*P[aá]g(?:ina|\.)?\.?\s*\d+\s*(?:de|of|/)?\s*\d*\s*$',
        '', text, flags=re.MULTILINE | re.IGNORECASE
    )
    text = re.sub(r'^\s*-\s*\d+\s*-\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\s*/\s*\d+\s*$', '', text, flags=re.MULTILINE)

    # 5. Remove lines that are pure URLs (footers often contain source URLs)
    text = re.sub(r'^\s*https?://\S+\s*$', '', text, flags=re.MULTILINE)

    # 6. Remove OCR noise lines (only non-alphanumeric chars)
    text = re.sub(r'(?m)^\W+$', '', text)

    # 7. Collapse excessive vertical whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()
