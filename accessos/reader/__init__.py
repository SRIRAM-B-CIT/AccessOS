"""
AccessOS Document Reader Package
=================================
Provides accessible document parsing and speech synthesis playback.
"""
from .document_reader import DocumentReader, PlaybackState
from .extractor import DocumentExtractor
from .reader_window import DocumentReaderWindow

__all__ = [
    "DocumentExtractor",
    "DocumentReader",
    "PlaybackState",
    "DocumentReaderWindow",
]
