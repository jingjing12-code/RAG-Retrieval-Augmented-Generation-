import re
from bs4 import BeautifulSoup
import fitz

def clean_html_text(raw_html: str) -> str:
    """Extract clean text from HTML."""
    if not raw_html:
        return ""
    try:
        soup = BeautifulSoup(raw_html, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)
    except Exception as e:
        print(f"HTML cleaning error: {e}")
        return raw_html

def extract_pdf_text(file_path: str) -> str:
    """Extract text from PDF file."""
    try:
        doc = fitz.open(file_path)

        print(f"Pages: {len(doc)}")

        text = ""

        for i, page in enumerate(doc):
            page_text = page.get_text()

            print("=" * 50)
            print(f"PAGE {i + 1}")
            print(f"Length: {len(page_text)}")
            print(page_text[:500])   # first 500 characters
            print("=" * 50)

            text += page_text

        return _clean_text(text)

    except Exception as e:
        print(f"PDF error: {e}")
        return ""

def _clean_text(text):
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        if re.match(r'^\s*\d+\s*$', line):
            continue
        if re.match(r'^(Chapter|Section|Page)\s+\d+', line, re.I):
            continue
        cleaned.append(line)
    return '\n'.join(cleaned)