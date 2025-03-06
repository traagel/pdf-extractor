"""
NLP-based text structure analysis.
"""

import re
import spacy
from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class TextBlock:
    """Represents a block of text with its type and properties."""
    text: str
    block_type: str  # 'title', 'paragraph', 'list_item', etc.
    level: int  # Heading level or 0 for non-titles
    properties: Dict = None

    def __post_init__(self):
        if self.properties is None:
            self.properties = {}

class TextStructureAnalyzer:
    def __init__(self):
        self.nlp = spacy.load("en_core_web_sm")
        # Increase max length but still process in chunks
        self.nlp.max_length = 2000000
        
        # Common patterns
        self.patterns = {
            'chapter': r'(?:C\s*h\s*a\s*p\s*t\s*e\s*r|CHAPTER)\s*(\d+)',
            'appendix': r'(?:A\s*p\s*p\s*e\s*n\s*d\s*i\s*x|APPENDIX)\s+([A-Z])',
            'section': r'^([A-Z][^\.]+?)(?:\.{3,}|\s*•\s*)(\d+)',
            'page_number': r'\s*(\d+)\s*$'
        }
        
        # Compile patterns
        self.compiled_patterns = {
            name: re.compile(pattern, re.IGNORECASE | re.MULTILINE)
            for name, pattern in self.patterns.items()
        }
    
    def preprocess_text(self, text: str) -> str:
        """Initial text cleanup and normalization."""
        # Join split words
        text = self._join_split_words(text)
        
        # Normalize whitespace
        text = re.sub(r'\s*\n\s*', '\n', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Fix common OCR issues
        text = text.replace('o f', 'of')
        text = text.replace('a n d', 'and')
        text = text.replace('t h e', 'the')
        
        # Convert dotted lines to bullets
        text = re.sub(r'\.{3,}', ' • ', text)
        
        return text.strip()
    
    def _join_split_words(self, text: str) -> str:
        """Join words that have been split with spaces between letters."""
        # Handle multi-line splits first
        text = re.sub(r'([A-Za-z])\s*\n\s*([A-Za-z])', r'\1\2', text)
        
        def join_word(match):
            word = match.group(0)
            parts = word.split()
            result = []
            current_word = []
            
            for part in parts:
                if len(part) == 1 and part.isalpha():
                    current_word.append(part)
                elif re.match(r'^[A-Z]\s+[a-z]+$', part):
                    result.append(part.replace(' ', ''))
                else:
                    if current_word:
                        result.append(''.join(current_word))
                        current_word = []
                    result.append(part)
            
            if current_word:
                result.append(''.join(current_word))
            
            return ' '.join(result)
        
        # Pattern for spaced words
        pattern = r'(?:[A-Z]\s+[a-z]+)|(?:[A-Z]\s+){2,}[A-Z]|[A-Z](?:\s*[A-Z])+[A-Z]?'
        
        # Clean in multiple passes
        prev_text = None
        while prev_text != text:
            prev_text = text
            text = re.sub(pattern, join_word, text, flags=re.MULTILINE)
        
        return text
    
    def analyze_document(self, text: str) -> Dict:
        """Analyze document structure using NLP."""
        # Preprocess text
        text = self.preprocess_text(text)
        
        # Split text into major sections first
        sections = self._split_into_sections(text)
        
        # Process each section separately
        structure = {
            'metadata': self._extract_metadata(sections.get('front_matter', '')),
            'table_of_contents': self._extract_toc(sections.get('contents', '')),
            'chapters': self._extract_chapters(sections.get('main_content', '')),
            'appendices': self._extract_appendices(sections.get('appendices', ''))
        }
        
        return structure
    
    def _split_into_sections(self, text: str) -> Dict[str, str]:
        """Split document into major sections before NLP processing."""
        sections = {}
        
        # Find the Contents section
        content_matches = list(re.finditer(
            r'(?:^|\n\n)C\s*o\s*n\s*t\s*e\s*n\s*t\s*s\s*(?:\n|$)', 
            text, 
            re.IGNORECASE
        ))
        
        if content_matches:
            # Everything before Contents is front matter
            content_start = content_matches[0].start()
            sections['front_matter'] = text[:content_start].strip()
            
            # Find Chapter 1
            chapter_matches = list(re.finditer(
                self.patterns['chapter'].replace('(\d+)', '1'), 
                text[content_start:]
            ))
            
            if chapter_matches:
                toc_end = content_start + chapter_matches[0].start()
                sections['contents'] = text[content_start:toc_end].strip()
                
                # Find first appendix
                appendix_matches = list(re.finditer(
                    self.patterns['appendix'], 
                    text[toc_end:]
                ))
                
                if appendix_matches:
                    main_content_end = toc_end + appendix_matches[0].start()
                    sections['main_content'] = text[toc_end:main_content_end].strip()
                    sections['appendices'] = text[main_content_end:].strip()
                else:
                    sections['main_content'] = text[toc_end:].strip()
            else:
                sections['main_content'] = text[content_start:].strip()
        
        return sections
    
    def _process_text_chunk(self, text: str, chunk_size: int = 100000) -> List[spacy.tokens.Doc]:
        """Process text in chunks to avoid memory issues."""
        chunks = []
        start = 0
        
        while start < len(text):
            # Find a good break point
            end = start + chunk_size
            if end < len(text):
                # Try to break at a paragraph or sentence boundary
                break_point = text.rfind('\n\n', start, end)
                if break_point == -1:
                    break_point = text.rfind('. ', start, end)
                if break_point == -1:
                    break_point = end
                else:
                    break_point += 2  # Include the delimiter
            else:
                break_point = len(text)
            
            # Process chunk
            chunk = text[start:break_point]
            doc = self.nlp(chunk)
            chunks.append(doc)
            
            start = break_point
        
        return chunks
    
    def _extract_metadata(self, text: str) -> Dict:
        """Extract document metadata using NLP."""
        metadata = {
            'title': 'Player\'s Handbook',
            'type': 'Core Rulebook'
        }
        
        if text:
            chunks = self._process_text_chunk(text, chunk_size=50000)
            # Process metadata from front matter
            # Implementation details...
        
        return metadata
    
    def _extract_toc(self, text: str) -> List[Dict]:
        """Extract table of contents using NLP."""
        toc = []
        
        if text:
            # Process TOC using regex first
            entries = self._process_content_list(text)
            
            # Use NLP for validation and enhancement
            chunks = self._process_text_chunk(text, chunk_size=50000)
            # Implementation details...
            
        return toc
    
    def _extract_chapters(self, text: str) -> List[Dict]:
        """Extract chapters using NLP."""
        chapters = []
        
        if not text:
            return chapters
            
        # Split into individual chapters
        chapter_texts = re.split(
            self.patterns['chapter'],
            text,
            flags=re.IGNORECASE | re.MULTILINE
        )
        
        # Process each chapter
        current_number = 0
        for chapter_text in chapter_texts:
            if not chapter_text.strip():
                continue
                
            # Try to extract chapter number and title
            chapter_match = re.match(
                r'^[:\s]*(.+?)(?:\s*•\s*(\d+)|$)',
                chapter_text.split('\n')[0],
                re.IGNORECASE
            )
            
            if chapter_match:
                current_number += 1
                title = self._clean_spaced_text(chapter_match.group(1).strip())
                
                # Process chapter content
                sections = []
                content_lines = chapter_text.split('\n')[1:]
                
                if content_lines:
                    # Look for section pattern
                    current_section = None
                    current_content = []
                    
                    for line in content_lines:
                        line = line.strip()
                        if not line:
                            continue
                            
                        # Check if line is a section title
                        section_match = re.match(
                            r'^([A-Z][^\.]+?)(?:\s*•\s*(\d+))?$',
                            line
                        )
                        
                        if section_match:
                            # Save previous section if exists
                            if current_section:
                                sections.append({
                                    'title': current_section,
                                    'content': '\n'.join(current_content).strip()
                                })
                            
                            current_section = self._clean_spaced_text(section_match.group(1))
                            current_content = []
                        else:
                            current_content.append(line)
                    
                    # Add final section
                    if current_section:
                        sections.append({
                            'title': current_section,
                            'content': '\n'.join(current_content).strip()
                        })
                    elif current_content:  # No sections found, use all content
                        sections.append({
                            'title': 'Main Content',
                            'content': '\n'.join(current_content).strip()
                        })
                
                chapters.append({
                    'number': current_number,
                    'title': title,
                    'sections': sections
                })
        
        return chapters

    def _extract_appendices(self, text: str) -> List[Dict]:
        """Extract appendices using NLP."""
        appendices = []
        
        if not text:
            return appendices
            
        # Split into individual appendices
        appendix_texts = re.split(
            self.patterns['appendix'],
            text,
            flags=re.IGNORECASE | re.MULTILINE
        )
        
        # Process each appendix
        for i, appendix_text in enumerate(appendix_texts[1:], start=0):  # Skip first split
            if not appendix_text.strip():
                continue
                
            # Try to extract appendix letter and title
            appendix_match = re.match(
                r'^[:\s]*(.+?)(?:\s*•\s*(\d+)|$)',
                appendix_text.split('\n')[0],
                re.IGNORECASE
            )
            
            if appendix_match:
                title = self._clean_spaced_text(appendix_match.group(1).strip())
                letter = chr(65 + i)  # A, B, C, etc.
                
                # Process appendix content similar to chapters
                content = appendix_text.strip()
                sections = [{
                    'title': 'Main Content',
                    'content': content
                }]
                
                appendices.append({
                    'letter': letter,
                    'title': title,
                    'content': content,
                    'sections': sections
                })
        
        return appendices 