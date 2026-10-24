"""
AccessOS Document Text Extractor
=================================
Extracts plain text and structured sentences from multiple file formats:
  - Plain Text (.txt)
  - Markdown (.md)
  - HTML (.html, .htm)
  - PDF (.pdf via pdftotext or pure fallback)
  - Word Document (.docx via zipfile XML)
  - OpenDocument (.odt via zipfile XML)
  - EPUB e-books (.epub via zipfile XHTML)
  - Image notices (.png, .jpg, .jpeg, etc.)

No heavy external Python packages required. Uses standard library and system pdftotext.
"""
from __future__ import annotations

import io
import logging
import re
import shutil
import subprocess
import zipfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Optional

log = logging.getLogger(__name__)

_ABBREVIATIONS = (
    "mr.", "mrs.", "ms.", "dr.", "prof.", "jr.", "sr.", "vs.",
    "e.g.", "i.e.", "etc.", "fig.", "inc.", "ltd.", "corp.", "u.s.", "u.k."
)


class _HTMLToTextParser(HTMLParser):
    """Simple, secure HTML-to-text converter ignoring scripts and styling."""

    def __init__(self) -> None:
        super().__init__()
        self.pieces: List[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in ("script", "style", "head"):
            self._skip = True
        elif tag.lower() in ("p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "br", "li", "tr"):
            self.pieces.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in ("script", "style", "head"):
            self._skip = False
        elif tag.lower() in ("p", "div", "h1", "h2", "h3", "h4", "h5", "h6"):
            self.pieces.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.pieces.append(data)

    def get_text(self) -> str:
        raw = "".join(self.pieces)
        return re.sub(r"\n{3,}", "\n\n", raw).strip()


class DocumentExtractor:
    """Multi-format text extraction engine for AccessOS Document Reader."""

    @classmethod
    def extract_text(cls, path: Path | str) -> str:
        """Extract clean text from a file path."""
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = file_path.suffix.lower()

        if ext in (".txt", ".log", ".csv", ".tsv"):
            return cls._extract_txt(file_path)
        elif ext == ".md":
            return cls._extract_markdown(file_path)
        elif ext in (".html", ".htm"):
            return cls._extract_html(file_path)
        elif ext == ".pdf":
            return cls._extract_pdf(file_path)
        elif ext == ".docx":
            return cls._extract_docx(file_path)
        elif ext == ".odt":
            return cls._extract_odt(file_path)
        elif ext == ".epub":
            return cls._extract_epub(file_path)
        elif ext in (".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff"):
            return (
                f"Image document detected: {file_path.name}. "
                "AccessOS Document Reader reads text documents. "
                "Optical Character Recognition (OCR) is recommended for image scans."
            )
        else:
            try:
                return cls._extract_txt(file_path)
            except Exception as exc:
                raise ValueError(f"Unsupported file format '{ext}' for file: {file_path.name}") from exc

    @staticmethod
    def _extract_txt(path: Path) -> str:
        for enc in ("utf-8", "latin-1", "cp1252"):
            try:
                return path.read_text(encoding=enc).strip()
            except UnicodeDecodeError:
                continue
        return path.read_text(encoding="utf-8", errors="replace").strip()

    @classmethod
    def _extract_markdown(cls, path: Path) -> str:
        raw = cls._extract_txt(path)
        text = re.sub(r"^#+\s*", "", raw, flags=re.MULTILINE)
        text = re.sub(r"[*_]{1,3}([^*_]+)[*_]{1,3}", r"\1", text)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"```[a-zA-Z]*\n[\s\S]*?```", "", text)
        text = re.sub(r"`([^`]+)`", r"\1", text)
        return text.strip()

    @staticmethod
    def _extract_html(path: Path) -> str:
        parser = _HTMLToTextParser()
        content = path.read_text(encoding="utf-8", errors="replace")
        parser.feed(content)
        return parser.get_text()

    @staticmethod
    def _extract_pdf(path: Path) -> str:
        pdftotext = shutil.which("pdftotext")
        if pdftotext:
            try:
                proc = subprocess.run(
                    [pdftotext, "-layout", str(path), "-"],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=True,
                )
                text = proc.stdout.strip()
                if text:
                    return text
            except Exception as exc:
                log.warning("pdftotext failed on %s: %s", path, exc)

        return f"Document: {path.name}. Text could not be extracted automatically from this PDF."

    @staticmethod
    def _extract_docx(path: Path) -> str:
        with zipfile.ZipFile(path) as zf:
            if "word/document.xml" not in zf.namelist():
                raise ValueError("Invalid DOCX format: missing word/document.xml")
            xml_data = zf.read("word/document.xml")

        tree = ET.fromstring(xml_data)
        paragraphs: List[str] = []
        for p in tree.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
            texts = [t.text for t in p.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t") if t.text]
            if texts:
                paragraphs.append("".join(texts))

        return "\n\n".join(paragraphs).strip()

    @staticmethod
    def _extract_odt(path: Path) -> str:
        with zipfile.ZipFile(path) as zf:
            if "content.xml" not in zf.namelist():
                raise ValueError("Invalid ODT format: missing content.xml")
            xml_data = zf.read("content.xml")

        tree = ET.fromstring(xml_data)
        paragraphs: List[str] = []
        for p in tree.iter("{urn:oasis:names:tc:opendocument:xmlns:text:1.0}p"):
            text = "".join(t for t in p.itertext() if t).strip()
            if text:
                paragraphs.append(text)

        return "\n\n".join(paragraphs).strip()

    @staticmethod
    def _extract_epub(path: Path) -> str:
        with zipfile.ZipFile(path) as zf:
            chapters: List[str] = []
            for name in sorted(zf.namelist()):
                if name.lower().endswith((".xhtml", ".html", ".htm")) and not name.lower().endswith("toc.xhtml"):
                    try:
                        raw = zf.read(name).decode("utf-8", errors="ignore")
                        p = _HTMLToTextParser()
                        p.feed(raw)
                        txt = p.get_text()
                        if txt:
                            chapters.append(txt)
                    except Exception as exc:
                        log.debug("Error reading EPUB chapter %s: %s", name, exc)

        return "\n\n".join(chapters).strip()

    @classmethod
    def split_sentences(cls, text: str) -> List[str]:
        """
        Split a document into readable sentences suitable for voice speech synthesis.
        Preserves common abbreviations and filters out blank entries.
        """
        if not text:
            return []

        cleaned = re.sub(r"[ \t]+", " ", text)
        paragraphs = [p.strip() for p in cleaned.split("\n") if p.strip()]

        sentences: List[str] = []
        for para in paragraphs:
            raw_sents = re.split(r"(?<=[.!?])\s+", para)
            buffer = ""
            for s in raw_sents:
                s = s.strip()
                if not s:
                    continue

                if buffer:
                    buffer += " " + s
                else:
                    buffer = s

                lower = buffer.lower()
                is_abbrev = any(lower.endswith(abbr) for abbr in _ABBREVIATIONS)
                if not is_abbrev or len(buffer) > 150:
                    sentences.append(buffer)
                    buffer = ""

            if buffer:
                sentences.append(buffer)

        return sentences
