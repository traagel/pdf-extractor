"""
PDF Extractor module for extracting text content from PDF files.
"""

import os
import logging
from pathlib import Path
from typing import Union, List, Dict, Optional, Any
import re

# PDF processing libraries
import fitz  # PyMuPDF
import pypdf
from PIL import Image

from .image_text_extractor import ImageTextExtractor
from ..utils.logger import get_logger

class PDFExtractor:
    """
    Extracts text content from PDF files using various methods.
    Handles both digital PDFs and scanned documents.
    """
    
    def __init__(self, pdf_path=None, config: Optional[Dict[str, Any]] = None, progress_callback=None):
        """
        Initialize the PDF extractor with configuration options.
        
        Args:
            pdf_path: Optional path to PDF file
            config: Optional configuration dictionary with extraction settings
            progress_callback: Optional callback function for progress updates
        """
        self.logger = get_logger(__name__)
        self.config = config or {}
        self.pdf_path = Path(pdf_path) if pdf_path else None
        self.progress_callback = progress_callback
        
        # Configure extraction settings
        self.min_text_length = self.config.get('min_text_length', 100)
        self.use_ocr_fallback = self.config.get('use_ocr_fallback', True)
        self.page_range = self.config.get('page_range', None)
        
        # Initialize image text extractor for OCR if needed
        self.image_extractor = None
        if self.use_ocr_fallback:
            self.image_extractor = ImageTextExtractor(self.config.get('ocr_config', {}))
            
        # Configure extraction methods
        self.extraction_methods = [
            self._extract_with_pymupdf,
            self._extract_with_pypdf,
            self._extract_with_ocr
        ]
        
    def extract(self, pdf_path: Union[str, Path]) -> str:
        """
        Extract text from a PDF file.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Extracted text content as a string
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
            
        self.logger.info(f"Extracting text from {pdf_path}")
        
        try:
            for method in self.extraction_methods:
                try:
                    text = method(pdf_path)
                    if text:
                        # Clean and normalize the extracted text
                        text = self._clean_extracted_text(text)
                        return text
                except Exception as e:
                    continue
                
            # If all methods fail, try OCR if enabled
            if self.use_ocr_fallback and self.image_extractor:
                self.logger.info("Regular extraction failed, falling back to OCR")
                return self._extract_with_ocr(pdf_path)
                
            # Return whatever text we have if OCR is not enabled
            self.logger.warning("Text extraction may be incomplete")
            return ""
            
        except Exception as e:
            self.logger.error(f"Error extracting text: {str(e)}")
            raise
            
    def _clean_extracted_text(self, text: str) -> str:
        """Clean and normalize extracted text."""
        # Convert literal '\n' to actual newlines
        text = text.replace('\\n', '\n')
        
        # Normalize different types of whitespace
        text = re.sub(r'\r\n|\r', '\n', text)
        
        # Remove excessive newlines but preserve paragraph structure
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Remove excessive spaces
        text = re.sub(r' {2,}', ' ', text)
        
        # Fix common OCR/extraction artifacts
        text = text.replace('•', '\n•')  # Add newline before bullet points
        text = re.sub(r'([.!?])\s*([A-Z])', r'\1\n\2', text)  # Add newlines after sentences
        
        # Clean up empty lines
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(line for line in lines if line)
        
        return text
            
    def _extract_with_pymupdf(self, pdf_path: Path) -> str:
        """Extract text using PyMuPDF (fitz)."""
        text_content = []
        
        try:
            doc = fitz.open(str(pdf_path))
            page_range = self.page_range or range(len(doc))
            
            for page_num in page_range:
                if page_num < len(doc):
                    page = doc[page_num]
                    text_content.append(page.get_text())
                    
                    # Update progress if callback is provided
                    if self.progress_callback:
                        self.progress_callback(1)
                    
            return "\n\n".join(text_content)
            
        except Exception as e:
            self.logger.warning(f"PyMuPDF extraction error: {str(e)}")
            return ""
            
    def _extract_with_pypdf(self, pdf_path: Path) -> str:
        """Extract text using PyPDF."""
        text_content = []
        
        try:
            with open(pdf_path, 'rb') as file:
                reader = pypdf.PdfReader(file)
                page_range = self.page_range or range(len(reader.pages))
                
                for page_num in page_range:
                    if page_num < len(reader.pages):
                        page = reader.pages[page_num]
                        text_content.append(page.extract_text() or "")
                        
            return "\n\n".join(text_content)
            
        except Exception as e:
            self.logger.warning(f"PyPDF extraction error: {str(e)}")
            return ""
            
    def _extract_with_ocr(self, pdf_path: Path) -> str:
        """Extract text using OCR for scanned documents."""
        if not self.image_extractor:
            raise RuntimeError("OCR extraction requested but image extractor not initialized")
            
        return self.image_extractor.extract_from_pdf(pdf_path, page_range=self.page_range)
        
    def _is_extraction_sufficient(self, text: str) -> bool:
        """
        Check if the extracted text is sufficient and not likely a failed extraction.
        
        Args:
            text: Extracted text to check
            
        Returns:
            Boolean indicating if extraction appears successful
        """
        # Check text length
        if len(text.strip()) < self.min_text_length:
            return False
            
        # Check for common indicators of failed extraction
        low_content_markers = [
            "This PDF does not contain text",
            "No text content available"
        ]
        
        return not any(marker in text for marker in low_content_markers)
        
    def is_scanned_pdf(self, pdf_path: Union[str, Path]) -> bool:
        """
        Determine if a PDF is likely a scanned document with limited text.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Boolean indicating if the PDF appears to be scanned
        """
        text = self._extract_with_pymupdf(Path(pdf_path))
        
        # Very little text likely means it's a scanned document
        text_length = len(text.strip())
        return text_length < self.min_text_length
