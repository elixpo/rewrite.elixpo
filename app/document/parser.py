"""Document parsing — PDF and DOCX extraction to structured Document."""

import logging
import re
from pathlib import Path

from app.document.structure import Document, Section, Paragraph

logger = logging.getLogger(__name__)


def parse_pdf(path: str) -> Document:
    """Extract text from PDF preserving basic structure."""
    from PyPDF2 import PdfReader

    reader = PdfReader(path)
    pages_text = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages_text.append(text.strip())

    full_text = "\n\n".join(pages_text)
    return _text_to_document(full_text, title=Path(path).stem, source_path=path)


def parse_docx(path: str) -> Document:
    """Extract text from DOCX preserving headings and structure."""
    from docx import Document as DocxDocument

    doc = DocxDocument(path)
    sections = []
    current_heading = ""
    current_paragraphs = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        # Detect headings by style
        style_name = (para.style.name or "").lower()
        if "heading" in style_name:
            # Flush current section
            if current_paragraphs:
                sections.append(Section(
                    heading=current_heading,
                    paragraphs=[Paragraph(text=p) for p in current_paragraphs],
                ))
                current_paragraphs = []
            current_heading = text
        else:
            current_paragraphs.append(text)

    # Flush last section
    if current_paragraphs:
        sections.append(Section(
            heading=current_heading,
            paragraphs=[Paragraph(text=p) for p in current_paragraphs],
        ))

    if not sections:
        # Fallback: treat as single section
        full_text = "\n".join(p.text.strip() for p in doc.paragraphs if p.text.strip())
        return _text_to_document(full_text, title=Path(path).stem, source_path=path)

    return Document(title=Path(path).stem, sections=sections, source_path=path)


def parse_file(path: str) -> Document:
    """Auto-detect file type and parse. Supports .pdf, .docx, .txt."""
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        return parse_pdf(path)
    elif ext == ".docx":
        return parse_docx(path)
    elif ext in (".txt", ".md"):
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        return _text_to_document(text, title=Path(path).stem, source_path=path)
    else:
        raise ValueError(f"Unsupported file type: {ext}. Use .pdf, .docx, or .txt")


def _text_to_document(text: str, title: str = "", source_path: str = None) -> Document:
    """Convert raw text into a structured Document with section detection."""
    lines = text.split("\n")
    sections = []
    current_heading = ""
    current_lines = []

    # Simple heading detection: short lines (< 80 chars) that are all caps or
    # followed by blank lines, or lines starting with common section patterns
    heading_pattern = re.compile(
        r"^(?:\d+\.?\s+)?(?:abstract|introduction|background|methods?|results?|"
        r"discussion|conclusion|references|acknowledgments?|appendix)",
        re.IGNORECASE,
    )

    for line in lines:
        stripped = line.strip()

        is_heading = (
            stripped
            and len(stripped) < 80
            and (
                stripped.isupper()
                or heading_pattern.match(stripped)
                or (stripped.startswith("#") and len(stripped) < 100)
            )
        )

        if is_heading:
            # Flush current section
            paragraph_text = "\n".join(current_lines).strip()
            if paragraph_text:
                paragraphs = [
                    Paragraph(text=p.strip())
                    for p in paragraph_text.split("\n\n")
                    if p.strip()
                ]
                sections.append(Section(heading=current_heading, paragraphs=paragraphs))
                current_lines = []
            current_heading = stripped.lstrip("# ")
        else:
            current_lines.append(line)

    # Flush last
    paragraph_text = "\n".join(current_lines).strip()
    if paragraph_text:
        paragraphs = [
            Paragraph(text=p.strip())
            for p in paragraph_text.split("\n\n")
            if p.strip()
        ]
        sections.append(Section(heading=current_heading, paragraphs=paragraphs))

    if not sections:
        sections = [Section(heading="", paragraphs=[Paragraph(text=text.strip())])]

    return Document(title=title, sections=sections, source_path=source_path)
