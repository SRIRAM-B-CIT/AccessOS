"""
Tests for AccessOS Document Reader and Multi-Format Extractor
=============================================================
Validates:
  - Text extraction across formats (.txt, .md, .html, .docx, .odt, .epub, images)
  - Sentence splitting with abbreviation awareness
  - Playback controller states (PLAYING, PAUSED, STOPPED)
  - Speed adjustments and navigation (next, previous, jump)
  - UI initialization and safe shutdown
"""
import io
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

from accessos.reader.extractor import DocumentExtractor
from accessos.reader.document_reader import DocumentReader, PlaybackState
from accessos.reader.reader_window import DocumentReaderWindow
from accessos.voice.tts_engine import TTSEngine
from accessos.voice.command_parser import CommandAction, parse_command


def test_sentence_splitting_abbreviations():
    text = "Hello Dr. Watson. Mrs. Hudson made tea at 4 p.m. Is Mr. Holmes home? Yes, he is."
    sentences = DocumentExtractor.split_sentences(text)
    assert len(sentences) == 4
    assert sentences[0] == "Hello Dr. Watson."
    assert "Mrs. Hudson" in sentences[1]
    assert sentences[2] == "Is Mr. Holmes home?"
    assert sentences[3] == "Yes, he is."


def test_extract_txt_and_markdown(tmp_path: Path):
    txt_file = tmp_path / "sample.txt"
    txt_file.write_text("Hello AccessOS plain text.", encoding="utf-8")
    assert DocumentExtractor.extract_text(txt_file) == "Hello AccessOS plain text."

    md_file = tmp_path / "sample.md"
    md_file.write_text("# Title\n\nThis is **bold** text with a [link](https://example.com).", encoding="utf-8")
    extracted_md = DocumentExtractor.extract_text(md_file)
    assert "Title" in extracted_md
    assert "bold" in extracted_md
    assert "link" in extracted_md
    assert "**" not in extracted_md
    assert "[" not in extracted_md


def test_extract_html(tmp_path: Path):
    html_file = tmp_path / "sample.html"
    html_file.write_text(
        "<html><head><style>body { color: red; }</style></head>"
        "<body><h1>Header</h1><script>alert(1);</script><p>Paragraph text.</p></body></html>",
        encoding="utf-8",
    )
    text = DocumentExtractor.extract_text(html_file)
    assert "Header" in text
    assert "Paragraph text." in text
    assert "alert(1)" not in text
    assert "color: red" not in text


def test_extract_docx(tmp_path: Path):
    docx_file = tmp_path / "test.docx"
    with zipfile.ZipFile(docx_file, "w") as zf:
        xml_content = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body>'
            '<w:p><w:r><w:t>First sentence in docx.</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>Second paragraph.</w:t></w:r></w:p>'
            '</w:body></w:document>'
        )
        zf.writestr("word/document.xml", xml_content)

    text = DocumentExtractor.extract_text(docx_file)
    assert "First sentence in docx." in text
    assert "Second paragraph." in text


def test_extract_odt(tmp_path: Path):
    odt_file = tmp_path / "test.odt"
    with zipfile.ZipFile(odt_file, "w") as zf:
        xml_content = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"'
            '                         xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
            '<office:body><office:text>'
            '<text:p>OpenDocument content here.</text:p>'
            '</office:text></office:body></office:document-content>'
        )
        zf.writestr("content.xml", xml_content)

    text = DocumentExtractor.extract_text(odt_file)
    assert "OpenDocument content here." in text


def test_extract_epub(tmp_path: Path):
    epub_file = tmp_path / "test.epub"
    with zipfile.ZipFile(epub_file, "w") as zf:
        xhtml_content = "<html><body><h1>EPUB Title</h1><p>Chapter text.</p></body></html>"
        zf.writestr("chapter1.xhtml", xhtml_content)

    text = DocumentExtractor.extract_text(epub_file)
    assert "EPUB Title" in text
    assert "Chapter text." in text


def test_image_notice(tmp_path: Path):
    img_file = tmp_path / "photo.png"
    img_file.write_bytes(b"\x89PNG\r\n\x1a\n")
    text = DocumentExtractor.extract_text(img_file)
    assert "Image document detected" in text


def test_document_reader_playback_controller():
    mock_tts = MagicMock(spec=TTSEngine)
    mock_tts.enabled = True

    sentence_events = []
    state_events = []

    reader = DocumentReader(
        tts=mock_tts,
        on_sentence_changed=lambda cur, tot, txt: sentence_events.append((cur, tot, txt)),
        on_state_changed=lambda st: state_events.append(st),
    )

    doc_text = "First sentence. Second sentence. Third sentence."
    reader.load_text(doc_text, title="Test Document")

    assert reader.total_sentences == 3
    assert reader.current_index == 0
    assert reader.progress == 0.0
    assert reader.state == PlaybackState.STOPPED

    # Navigation while stopped
    reader.next_sentence()
    assert reader.current_index == 1
    assert reader.progress > 0.0

    reader.previous_sentence()
    assert reader.current_index == 0

    reader.jump_to(2)
    assert reader.current_index == 2

    # Speed control
    assert reader.speed == 1.0
    reader.increase_speed()
    assert reader.speed == 1.25
    reader.decrease_speed()
    assert reader.speed == 1.0

    # Play and pause
    reader.play()
    assert reader.state == PlaybackState.PLAYING

    reader.pause()
    assert reader.state == PlaybackState.PAUSED

    reader.resume()
    assert reader.state == PlaybackState.PLAYING

    reader.stop()
    assert reader.state == PlaybackState.STOPPED
    assert reader.current_index == 0


def test_document_reader_window_lifecycle():
    mock_tts = MagicMock(spec=TTSEngine)
    win = DocumentReaderWindow(tts=mock_tts)

    win.load_text("Window test sentence one. Window test sentence two.", title="Window Test")
    assert win.reader.total_sentences == 2

    # Clean close
    win.reader.stop()
    win.destroy()


def test_voice_commands_include_reading():
    assert parse_command("read document") == CommandAction.READ_DOCUMENT
    assert parse_command("read aloud") == CommandAction.READ_DOCUMENT
    assert parse_command("pause reading") == CommandAction.PAUSE_READING
    assert parse_command("resume reading") == CommandAction.RESUME_READING
    assert parse_command("stop reading") == CommandAction.STOP_READING
    assert parse_command("read faster") == CommandAction.READING_FASTER
    assert parse_command("read slower") == CommandAction.READING_SLOWER
    assert parse_command("next sentence") == CommandAction.NEXT_SENTENCE
    assert parse_command("previous sentence") == CommandAction.PREVIOUS_SENTENCE
