"""
PDF Text Extractor - Extraction Module

This module provides classes and functions for extracting text content from
PDF files using various methods including direct text extraction and OCR.
"""

from .pdf_extractor import PDFExtractor
from .image_text_extractor import ImageTextExtractor

__all__ = ['PDFExtractor', 'ImageTextExtractor']
