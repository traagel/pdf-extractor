"""
Text processing module for structuring PDF content.
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from ..nlp.text_structure import TextStructureAnalyzer

@dataclass
class Section:
    """Represents a section in the document."""
    title: str
    level: int
    content: str
    page: Optional[int] = None
    subsections: List['Section'] = None

    def __post_init__(self):
        if self.subsections is None:
            self.subsections = []

    def to_dict(self) -> Dict:
        """Convert section to dictionary format."""
        result = {
            'title': self.title,
            'content': self.content,
        }
        if self.page:
            result['page'] = self.page
        if self.subsections:
            result['subsections'] = [s.to_dict() for s in self.subsections]
        return result

class TextProcessor:
    """
    Processes and structures extracted text from PDFs.
    """
    
    def __init__(self):
        # Regular expressions for detecting structure
        self.chapter_pattern = re.compile(
            r'(?:C\s*h\s*a\s*p\s*t\s*e\s*r|CHAPTER)\s*(\d+)[:\s]+([^\n\.]+)|'  # Standard and spaced format
            r'(\d+)\.\s+([A-Za-z][^\n]*?(?:\s+[A-Za-z]){2,}[^\n]*)',  # Numbered format
            re.IGNORECASE
        )
        self.appendix_pattern = re.compile(
            r'(?:A\s*p\s*p\s*e\s*n\s*d\s*i\s*x|APPENDIX)\s+([A-Z])[:\s]+([^\n\.]+)',
            re.IGNORECASE
        )
        self.section_pattern = re.compile(
            r'^([A-Z][^\.]+?)(?:\.{3,}|\s)*(\d+)',
            re.MULTILINE
        )
        self.page_number_pattern = re.compile(r'\s*(\d+)\s*$')
        
        self.structure_analyzer = TextStructureAnalyzer()
        
    def process(self, text: str) -> Dict:
        """
        Process the text and return structured content.
        
        Args:
            text: Raw text from PDF
            
        Returns:
            Dictionary containing structured content
        """
        # Clean the text first
        text = self._clean_text(text)
        
        # Split into major parts (TOC, chapters, etc.)
        parts = self._split_major_parts(text)
        
        # Process each part
        structured_content = {
            'metadata': {
                'title': 'Player\'s Handbook',
                'type': 'Core Rulebook'
            },
            'table_of_contents': self._extract_toc(parts.get('contents', '')),
            'chapters': [],
            'appendices': []
        }
        
        # Process chapters
        if 'main_content' in parts:
            chapters = self._split_chapters(parts['main_content'])
            for chapter_text in chapters:
                chapter = self._process_chapter(chapter_text)
                if chapter:
                    structured_content['chapters'].append(chapter)
        
        # Process appendices
        if 'appendices' in parts:
            appendices = self._split_appendices(parts['appendices'])
            for appendix_text in appendices:
                appendix = self._process_appendix(appendix_text)
                if appendix:
                    structured_content['appendices'].append(appendix)
        
        return structured_content
    
    def _clean_text(self, text: str) -> str:
        """Clean up the text before processing."""
        # Handle newlines and spacing
        text = re.sub(r'\s*\n\s*', '\n', text)  # Clean up spaces around newlines
        
        # Fix common OCR/formatting issues
        text = text.replace('o f', 'of')
        text = text.replace('a n d', 'and')
        text = text.replace('t h e', 'the')
        
        # Clean spaced-out text (do this before normalizing newlines)
        text = self._clean_spaced_text(text)
        
        # Now normalize newlines
        text = re.sub(r'\n{3,}', '\n\n', text)  # Normalize paragraph breaks
        
        # Join hyphenated words at line breaks
        text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)
        
        # Handle dotted lines in contents (.......)
        text = re.sub(r'\.{3,}', ' • ', text)
        
        return text.strip()
    
    def _clean_spaced_text(self, text: str) -> str:
        """Clean text with spaced-out letters."""
        # First join any split words across lines
        text = re.sub(r'([A-Za-z])\s*\n\s*([A-Za-z])', r'\1 \2', text)
        
        # Function to clean a single spaced word
        def clean_spaced_word(match):
            word = match.group(0)
            # Remove spaces between single letters, preserving word boundaries
            parts = word.split()
            cleaned_parts = []
            current_word = []
            
            for part in parts:
                # Handle single letters that should be joined
                if len(part) == 1 and part.isalpha():
                    current_word.append(part)
                # Handle special cases like "D&D", "M onk"
                elif re.match(r'^[A-Z]\s+[a-z]+$', part):
                    cleaned_parts.append(part.replace(' ', ''))
                else:
                    if current_word:
                        cleaned_parts.append(''.join(current_word))
                        current_word = []
                    cleaned_parts.append(part)
            
            if current_word:
                cleaned_parts.append(''.join(current_word))
            
            return ' '.join(cleaned_parts)
        
        # Pattern for words with spaces between letters, including across lines
        spaced_pattern = r'(?:[A-Z]\s+[a-z]+)|(?:[A-Z]\s+){2,}[A-Z]|[A-Z](?:\s*\n\s*[A-Z])+[A-Z]'
        
        # Clean the text in multiple passes to catch all patterns
        prev_text = None
        while prev_text != text:
            prev_text = text
            text = re.sub(spaced_pattern, clean_spaced_word, text, flags=re.MULTILINE)
        
        return text
    
    def _split_major_parts(self, text: str) -> Dict[str, str]:
        """Split text into major document parts."""
        parts = {}
        
        # Find the start of the content
        content_matches = list(re.finditer(r'(?:^|\n\n)C\s*o\s*n\s*t\s*e\s*n\s*t\s*s\s*(?:\n|$)', text, re.IGNORECASE))
        if content_matches:
            content_start = content_matches[0].start()
            
            # Extract preface if it exists
            preface = text[:content_start].strip()
            if preface:
                parts['preface'] = preface
            
            # Continue with the rest
            remaining_text = text[content_start:]
            
            # Find the table of contents
            chapter_matches = list(re.finditer(
                r'(?:^|\n)(?:C\s*h\s*a\s*p\s*t\s*e\s*r|CHAPTER)\s*1\s*:', 
                remaining_text, 
                re.IGNORECASE | re.MULTILINE
            ))
            
            if chapter_matches:
                toc_end = chapter_matches[0].start()
                parts['contents'] = remaining_text[:toc_end].strip()
                remaining_text = remaining_text[toc_end:]
                
                # Find where the appendices start
                appendix_matches = list(re.finditer(
                    r'(?:^|\n)(?:A\s*p\s*p\s*e\s*n\s*d\s*i\s*x|APPENDIX)\s+[A-Z]', 
                    remaining_text, 
                    re.IGNORECASE | re.MULTILINE
                ))
                
                if appendix_matches:
                    main_content_end = appendix_matches[0].start()
                    parts['main_content'] = remaining_text[:main_content_end].strip()
                    parts['appendices'] = remaining_text[main_content_end:].strip()
                else:
                    parts['main_content'] = remaining_text.strip()
            else:
                # If we can't find Chapter 1, treat everything after Contents as main content
                parts['main_content'] = remaining_text.strip()
        
        return parts
    
    def _extract_toc(self, toc_text: str) -> List[Dict]:
        """Extract and structure table of contents."""
        toc_entries = []
        current_chapter = None
        
        # Split into lines and process each line
        lines = toc_text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Try to match as chapter (both formats)
            chapter_match = self.chapter_pattern.search(line)
            if chapter_match:
                groups = chapter_match.groups()
                if groups[0] is not None:  # Standard format
                    number, title = groups[0], groups[1]
                else:  # Spaced-out format
                    number, title = groups[2], self._clean_spaced_text(groups[3])
                    
                page = self._extract_page_number(line)
                current_chapter = {
                    'type': 'chapter',
                    'number': int(number),
                    'title': title.strip(),
                    'page': page,
                    'sections': []
                }
                toc_entries.append(current_chapter)
                continue
                
            # Try to match as appendix
            appendix_match = self.appendix_pattern.search(line)
            if appendix_match:
                letter, title = appendix_match.groups()
                page = self._extract_page_number(line)
                toc_entries.append({
                    'type': 'appendix',
                    'letter': letter,
                    'title': title.strip(),
                    'page': page
                })
                current_chapter = None
                continue
                
            # Try to match as section
            if current_chapter and '.' in line:
                title, page_str = line.rsplit('.', 1)
                try:
                    page = int(page_str.strip())
                    current_chapter['sections'].append({
                        'title': title.strip(),
                        'page': page
                    })
                except ValueError:
                    pass
        
        return toc_entries
    
    def _extract_page_number(self, text: str) -> Optional[int]:
        """Extract page number from text."""
        match = self.page_number_pattern.search(text)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass
        return None
    
    def _split_chapters(self, text: str) -> List[str]:
        """Split text into individual chapters."""
        # Pattern that handles both normal and spaced chapter headings
        chapter_pattern = r'(?:^|\n)(?:C\s*h\s*a\s*p\s*t\s*e\s*r|CHAPTER)\s*\d+'
        chapters = re.split(chapter_pattern, text, flags=re.IGNORECASE)
        return [c.strip() for c in chapters if c.strip()]
    
    def _split_appendices(self, text: str) -> List[str]:
        """Split text into individual appendices."""
        # Pattern that handles both normal and spaced appendix headings
        appendix_pattern = r'(?:^|\n)(?:A\s*p\s*p\s*e\s*n\s*d\s*i\s*x|APPENDIX)\s+[A-Z]'
        appendices = re.split(appendix_pattern, text, flags=re.IGNORECASE)
        return [a.strip() for a in appendices if a.strip()]
    
    def _process_content_list(self, text: str) -> List[Dict]:
        """Process text that contains a list of items with page numbers."""
        items = []
        
        # First, extract the main title without page numbers
        title_match = re.match(r'^(.*?)(?:\s*•\s*\d+|\s*$)', text.split('\n')[0])
        if title_match:
            main_title = self._clean_spaced_text(title_match.group(1).strip())
        
        # Split content into lines
        lines = text.split('\n')
        current_section = None
        current_content = []
        
        for line in lines[1:]:  # Skip the first line (title)
            line = line.strip()
            if not line:
                continue
            
            # Try to match section with page number
            section_match = re.match(r'^(.*?)(?:\s*•\s*(\d+))?$', line)
            if section_match:
                section_title, page = section_match.groups()
                section_title = self._clean_spaced_text(section_title.strip())
                
                # Skip if it's just a page number
                if section_title and not section_title.isdigit():
                    items.append({
                        'title': section_title,
                        'page': int(page) if page else None
                    })
        
        return items

    def _process_chapter(self, chapter_text: str) -> Optional[Dict]:
        """Process a single chapter."""
        # Extract chapter number and title
        chapter_match = self.chapter_pattern.match(chapter_text)
        if not chapter_match:
            return None
            
        # Handle both standard and spaced-out formats
        groups = chapter_match.groups()
        if groups[0] is not None:  # Standard format
            number, title = groups[0], groups[1]
        else:  # Spaced-out format
            number, title = groups[2], self._clean_spaced_text(groups[3])
            
        # Process content as a list if it looks like a contents listing
        if re.search(r'\.{3,}|\s+\d+\s*$', chapter_text, re.MULTILINE):
            sections = self._process_content_list(chapter_text)
        else:
            # Use NLP for regular content
            blocks = self.structure_analyzer.analyze_structure(chapter_text)
            sections = self._process_blocks_to_sections(blocks)
        
        return {
            'number': int(number),
            'title': title.strip(),
            'sections': sections
        }

    def _process_blocks_to_sections(self, blocks: List['TextBlock']) -> List[Dict]:
        """Convert text blocks into sections."""
        sections = []
        current_section = None
        current_content = []
        
        for block in blocks:
            if block.block_type == 'title' and block.level <= 3:
                # Save previous section if exists
                if current_section:
                    sections.append({
                        'title': current_section,
                        'content': '\n'.join(current_content).strip()
                    })
                current_section = block.text
                current_content = []
            else:
                current_content.append(block.text)
                
        # Add the last section
        if current_section:
            sections.append({
                'title': current_section,
                'content': '\n'.join(current_content).strip()
            })
            
        return sections
    
    def _process_appendix(self, appendix_text: str) -> Optional[Dict]:
        """Process a single appendix."""
        # Extract appendix letter and title
        appendix_match = self.appendix_pattern.match(appendix_text)
        if not appendix_match:
            return None
            
        letter, title = appendix_match.groups()
        
        # Use NLP to analyze structure, just like chapters
        blocks = self.structure_analyzer.analyze_structure(appendix_text)
        
        # Organize blocks into sections
        sections = []
        current_section = None
        current_content = []
        
        for block in blocks:
            if block.block_type == 'title' and block.level <= 3:
                # Save previous section if exists
                if current_section:
                    sections.append({
                        'title': current_section,
                        'content': '\n'.join(current_content).strip()
                    })
                current_section = block.text
                current_content = []
            else:
                current_content.append(block.text)
        
        # Add the last section
        if current_section:
            sections.append({
                'title': current_section,
                'content': '\n'.join(current_content).strip()
            })
        
        # If no sections were found, create one with all content
        if not sections:
            sections = [{
                'title': 'Main Content',
                'content': appendix_text
            }]
        
        return {
            'letter': letter,
            'title': title.strip(),
            'content': appendix_text,  # Add the full content as required by schema
            'sections': sections  # Keep detailed sections for better structure
        } 