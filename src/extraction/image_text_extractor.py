"""
Image Text Extractor module for OCR-based text extraction from images and scanned PDFs.
"""

import os
import tempfile
from pathlib import Path
from typing import Union, List, Dict, Optional, Any

import pytesseract
from PIL import Image
import fitz  # PyMuPDF
import numpy as np

from ..utils.logger import get_logger

class ImageTextExtractor:
    """
    Extracts text from images and scanned PDFs using OCR technology.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the image text extractor with OCR configuration.
        
        Args:
            config: Optional configuration dictionary with OCR settings
        """
        self.logger = get_logger(__name__)
        self.config = config or {}
        
        # Configure OCR settings
        self.language = self.config.get('language', 'eng')
        self.dpi = self.config.get('dpi', 300)
        self.tesseract_path = self.config.get('tesseract_path')
        self.page_segmentation_mode = self.config.get('psm', 1)
        self.oem = self.config.get('oem', 3)
        
        # Configure Tesseract path if provided
        if self.tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_path
            
    def extract_from_image(self, image_path: Union[str, Path]) -> str:
        """
        Extract text from an image file using OCR.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Extracted text content as a string
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")
            
        try:
            self.logger.info(f"Performing OCR on image: {image_path}")
            img = Image.open(image_path)
            
            # Perform OCR
            ocr_config = f'--psm {self.page_segmentation_mode} --oem {self.oem}'
            text = pytesseract.image_to_string(img, lang=self.language, config=ocr_config)
            
            return text
            
        except Exception as e:
            self.logger.error(f"OCR extraction error: {str(e)}")
            raise
            
    def extract_from_pdf(self, pdf_path: Union[str, Path], page_range: Optional[range] = None) -> str:
        """
        Extract text from a PDF by treating each page as an image and applying OCR.
        
        Args:
            pdf_path: Path to the PDF file
            page_range: Optional range of pages to process
            
        Returns:
            Extracted text content as a string
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
            
        text_content = []
        
        try:
            self.logger.info(f"Performing OCR on PDF: {pdf_path}")
            doc = fitz.open(str(pdf_path))
            
            # Process specified pages or all pages
            page_range = page_range or range(len(doc))
            
            for page_num in page_range:
                if page_num < len(doc):
                    self.logger.info(f"Processing page {page_num + 1}")
                    page_text = self._process_pdf_page(doc, page_num)
                    text_content.append(page_text)
                    
            return "\n\n".join(text_content)
            
        except Exception as e:
            self.logger.error(f"PDF OCR extraction error: {str(e)}")
            raise
            
    def _process_pdf_page(self, doc, page_num: int) -> str:
        """
        Process a single PDF page with OCR.
        
        Args:
            doc: PyMuPDF document
            page_num: Page number to process
            
        Returns:
            Extracted text from the page
        """
        page = doc[page_num]
        
        # Create a temporary directory for image files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Render page to image
            pix = page.get_pixmap(dpi=self.dpi)
            image_path = os.path.join(temp_dir, f"page_{page_num}.png")
            pix.save(image_path)
            
            # Perform OCR on the image
            return self.extract_from_image(image_path)
            
    def process_image(self, image: Union[Image.Image, np.ndarray]) -> str:
        """
        Extract text from a PIL Image or numpy array.
        
        Args:
            image: PIL Image or numpy array containing image data
            
        Returns:
            Extracted text content as a string
        """
        try:
            # Convert numpy array to PIL Image if necessary
            if isinstance(image, np.ndarray):
                image = Image.fromarray(image)
                
            # Perform OCR
            ocr_config = f'--psm {self.page_segmentation_mode} --oem {self.oem}'
            text = pytesseract.image_to_string(image, lang=self.language, config=ocr_config)
            
            return text
            
        except Exception as e:
            self.logger.error(f"OCR extraction error on image object: {str(e)}")
            raise
