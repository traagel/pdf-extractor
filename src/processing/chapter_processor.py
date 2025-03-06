"""
Processor for identifying and cleaning chapter titles from lines.
"""

import re
from typing import List, Dict, Tuple, Optional, Any
from .table_processor import TableProcessor
from ..nlp.text_validator import TextValidator
from ..utils.logger import get_logger

class ChapterProcessor:
    """Processes lines to identify and clean chapter titles."""
    
    def __init__(self, progress_callback=None):
        # Patterns for identifying spaced text
        self.spaced_patterns = [
            # Chapter pattern like "C h a p t e r 1"
            r'^C\s+h\s+a\s+p\s+t\s+e\s+r\s+\d+',
            
            # Title pattern like "R a c e s" or "C l a s s e s"
            r'^[A-Z](\s+[a-z])+$',
            
            # Multi-word title like "H i l l D w a r f"
            r'^([A-Z](\s+[a-z])+\s+)+[A-Z](\s+[a-z])+$'
        ]
        
        # Add patterns for line merging
        self.continuation_patterns = [
            r'^[a-z]',  # Starts with lowercase
            r'^(and|or|but|nor|for|yet|so|the|a|an|in|on|at|to|of|with|by|from)\b',  # Common continuations
            r'^\s*[,;]\s*',  # Starts with comma or semicolon
            r'^\s*[-•]\s*'   # Starts with bullet or dash
        ]
        
        # Add pattern for vertical text
        self.vertical_text_pattern = r'^[a-zA-Z]$'  # Single letter lines
        self.max_vertical_gap = 5  # Max lines to look ahead for vertical text
        self.table_processor = TableProcessor()
        self.text_validator = TextValidator()
        self.progress_callback = progress_callback
        self.logger = get_logger(__name__)
    
    def _process_subchapter(self, line: str) -> Optional[Dict]:
        """Process a potential subchapter title from spaced text."""
        if not self._has_spaced_text(line):
            return None
            
        cleaned = self._clean_spaced_text(line)
        
        # Skip lines that are too long after cleaning
        if len(cleaned) > 50:
            return None
            
        # Check if it looks like a title (all words start with caps or it's a single capitalized word)
        words = cleaned.split()
        if (len(words) == 1 and words[0][0].isupper()) or \
           (len(words) >= 2 and all(w[0].isupper() for w in words)):
            # Split camelCase/PascalCase into words
            title_words = []
            for word in words:
                # Split on capital letters but keep them
                split_words = re.findall('[A-Z][^A-Z]*', word)
                title_words.extend(split_words)
            
            return {
                'title': ' '.join(title_words),
                'original_line': line
            }
        
        return None
    
    def process(self, lines: List[str]) -> Dict:
        """Process lines to identify and clean chapter titles."""
        self.logger.debug(f"Starting chapter processing on {len(lines)} lines")
        
        chapters = []
        current_chapter = {
            'number': 0,
            'title': 'Front Matter',
            'original_line': None,
            'content': {
                'info': {},
                'main_content': [],
                'subchapters': [],
                'tables': []
            }
        }
        current_content = []
        current_subchapter = None
        
        chapter_count = 0
        for line in lines:
            cleaned_line = line
            
            # Check if line contains spaced text
            if self._has_spaced_text(cleaned_line):
                cleaned_line = self._clean_spaced_text(cleaned_line)
                # Check for chapter title
                if self._is_chapter_title(cleaned_line):
                    self.logger.debug(f"Found chapter title: {cleaned_line}")
                    # Save previous chapter if exists
                    if current_chapter:
                        if current_subchapter:
                            current_subchapter['lines'] = current_content
                            current_chapter['content']['subchapters'].append(current_subchapter)
                            current_subchapter = None
                        else:
                            current_chapter['content']['main_content'] = current_content
                            
                        current_chapter['content']['info']['line_count'] = len(current_content)
                        chapters.append(current_chapter)
                        chapter_count += 1
                        
                        # Update progress if callback provided
                        if self.progress_callback:
                            self.progress_callback(1)
                    
                    # Start new chapter
                    current_chapter = self._extract_chapter_info(cleaned_line)
                    current_content = []
                    continue
                
                # Check for subchapter title
                subchapter = self._process_subchapter(line)
                if subchapter:
                    # Save previous subchapter content if exists
                    if current_subchapter:
                        current_subchapter['lines'] = current_content
                        current_chapter['content']['subchapters'].append(current_subchapter)
                        current_content = []
                    
                    current_subchapter = subchapter
                    continue
            
            # Add line to current content
            current_content.append(cleaned_line)
        
        # Process content before adding to chapter
        if current_content:
            processed_content = self._process_content(current_content)
            if processed_content['type'] == 'table':
                current_chapter['content']['tables'].append(processed_content)
            else:
                current_chapter['content']['main_content'].extend(processed_content['lines'])
        
        # Add final content
        if current_chapter:
            if current_subchapter:
                current_subchapter['lines'] = current_content
                current_chapter['content']['subchapters'].append(current_subchapter)
            else:
                current_chapter['content']['main_content'] = current_content
                
            current_chapter['content']['info']['line_count'] = len(current_content)
            chapters.append(current_chapter)
        
        # Add validation results
        validation_results = []
        for chapter in chapters:
            validation = self.text_validator.validate_chapter(chapter)
            if any([validation['main_content'], 
                   validation['subchapters'], 
                   validation['tables']]):
                validation_results.append(validation)
        
        self.logger.debug(f"Chapter processing complete. Found {len(chapters)} chapters")
        
        return {
            'chapters': chapters,
            'validation': validation_results,
            'stats': {
                'total_chapters': len(chapters),
                'avg_chapter_length': sum(len(c['content']['main_content']) + 
                                       sum(len(s['lines']) for s in c['content']['subchapters'])
                                       for c in chapters) / len(chapters) if chapters else 0
            }
        }
    
    def _has_spaced_text(self, line: str) -> bool:
        """Check if line contains spaced text."""
        return any(re.search(pattern, line) for pattern in self.spaced_patterns)
    
    def _clean_spaced_text(self, line: str) -> str:
        """Clean text that has spaces between letters."""
        # Split into words
        words = line.split()
        cleaned_words = []
        current_word = []
        
        for word in words:
            # If word is a single letter
            if len(word) == 1 and word.isalpha():
                current_word.append(word)
            else:
                # If we have collected letters, join them
                if current_word:
                    cleaned_words.append(''.join(current_word))
                    current_word = []
                cleaned_words.append(word)
        
        if current_word:
            cleaned_words.append(''.join(current_word))
        
        return ' '.join(cleaned_words)
    
    def _is_chapter_title(self, line: str) -> bool:
        """Check if a line looks like a chapter title."""
        # Patterns for chapter titles
        chapter_patterns = [
            # Standard chapter pattern with number
            r'^Chapter\s+\d+\s*:?\s*\w',
            # Just a number (common for chapters)
            r'^\d+\s*$',
            # Common chapter titles in D&D
            r'^(Races|Classes|Equipment|Spells|Combat|Adventuring|Spellcasting)\s*$',
            # Check for "Step by Step Characters" with various spacings
            r'(?i)st\s*[e\s]*p\s*[b\s]*y\s*[s\s]*t\s*e\s*p\s*characters'
        ]
        
        # Check for TOC indicators - skip these
        toc_indicators = [
            r'\.\.\.\.\.*\d+$',  # Dots followed by page number
            r'\s\d+$',           # Space followed by page number at end
        ]
        
        # Check if line matches any TOC pattern
        for pattern in toc_indicators:
            if re.search(pattern, line):
                return False
        
        # Check if line matches any chapter pattern
        for pattern in chapter_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                return True
            
        return False
    
    def _extract_chapter_info(self, line: str) -> Dict[str, Any]:
        """Extract chapter number and title from a line."""
        # Clean the line
        line = line.strip()
        
        # Handle special case for "Step-by-Step Characters" with various spacings
        if re.search(r'(?i)st\s*[e\s]*p\s*[b\s]*y\s*[s\s]*t\s*e\s*p\s*characters', line):
            return {
                'number': 1,  # Typically the first chapter
                'title': 'Step-by-Step Characters',
                'original_line': line,
                'content': {
                    'info': {},
                    'main_content': [],
                    'subchapters': [],
                    'tables': []
                }
            }
        
        # Handle "Chapter 4: Personality and Background" with missing space
        match = re.match(r'^Chapter\s+(\d+)\s*:?\s*([Pp]ersonalityand\s*.*)$', line)
        if match:
            fixed_title = re.sub(r'([Pp]ersonalityand)', r'Personality and', match.group(2))
            return {
                'number': int(match.group(1)),
                'title': fixed_title.strip(),
                'original_line': line,
                'content': {
                    'info': {},
                    'main_content': [],
                    'subchapters': [],
                    'tables': []
                }
            }
        
        # Try to match "Chapter X: Title" pattern
        match = re.match(r'^Chapter\s+(\d+)\s*:?\s*(.+)$', line, re.IGNORECASE)
        if match:
            return {
                'number': int(match.group(1)),
                'title': match.group(2).strip(),
                'original_line': line,
                'content': {
                    'info': {},
                    'main_content': [],
                    'subchapters': [],
                    'tables': []
                }
            }
        
        # Try to match just a number
        match = re.match(r'^(\d+)\s*$', line)
        if match:
            return {
                'number': int(match.group(1)),
                'title': f"Chapter {match.group(1)}",  # Default title
                'original_line': line,
                'content': {
                    'info': {},
                    'main_content': [],
                    'subchapters': [],
                    'tables': []
                }
            }
        
        # For other cases, use the line as the title
        return {
            'number': 0,
            'title': line,
            'original_line': line,
            'content': {
                'info': {},
                'main_content': [],
                'subchapters': [],
                'tables': []
            }
        }
    
    def _print_structure(self, chapters: List[Dict]) -> None:
        """Print the chapter structure in a readable format."""
        print("\nDocument Structure:")
        print("==================")
        
        for chapter in chapters:
            # Print chapter header
            if chapter['number'] == 0:
                print(f"\n[Front Matter]")
            else:
                print(f"\n[Chapter {chapter['number']}: {chapter['title']}]")
            
            # Print subchapters
            if chapter['content']['subchapters']:
                print("  Subchapters:")
                for subchapter in chapter['content']['subchapters']:
                    print(f"    - {subchapter['title']}")
                    print(f"      ({len(subchapter['lines'])} lines)")
            
            # Print main content summary
            main_content_lines = len(chapter['content']['main_content'])
            if main_content_lines > 0:
                print(f"  Main content: {main_content_lines} lines")
            
            print(f"  Total lines: {chapter['content']['info'].get('line_count', 0)}")
    
    def _should_merge_with_previous(self, current: str, previous: str) -> bool:
        """Check if current line should be merged with previous line."""
        if not current or not previous:
            return False
            
        # Check if current line starts with a continuation pattern
        if any(re.match(pattern, current, re.IGNORECASE) for pattern in self.continuation_patterns):
            return True
            
        # Check if previous line ends with an incomplete phrase
        if previous.rstrip().endswith(('and', 'or', 'but', 'the', 'a', 'an', 'in', 'on', 'at', 'to', 'of', 'with')):
            return True
            
        # Check if previous line ends with a hanging word (no punctuation)
        if not re.search(r'[.!?:;,]\s*$', previous):
            # But make sure the current line isn't a new sentence
            if not current[0].isupper() or current.startswith(('and ', 'or ', 'but ')):
                return True
        
        return False
    
    def _merge_lines(self, lines: List[str], max_iterations: int = 10) -> List[str]:
        """
        Merge lines that appear to be part of the same sentence.
        Limits iterations to prevent infinite loops.
        """
        if not lines:
            return lines
            
        # Keep track of iterations
        iteration = 0
        current_lines = lines.copy()
        
        while iteration < max_iterations:
            if len(current_lines) <= 1:
                break
                
            # Try one pass of merging
            merged = []
            i = 0
            
            while i < len(current_lines):
                # If this is the last line, add it and break
                if i == len(current_lines) - 1:
                    merged.append(current_lines[i])
                    break
                    
                current = current_lines[i]
                next_line = current_lines[i + 1]
                
                # Check if lines should be merged
                if self._should_merge_with_previous(next_line.strip(), current.strip()):
                    # Merge the lines
                    if current.rstrip().endswith('-'):
                        merged_line = current.rstrip()[:-1] + next_line.lstrip()
                    else:
                        space = '' if next_line.lstrip().startswith((',', '.', ';', ':', '?', '!')) else ' '
                        merged_line = current.rstrip() + space + next_line.lstrip()
                    merged.append(merged_line)
                    i += 2  # Skip next line since we merged it
                else:
                    merged.append(current)
                    i += 1
            
            # If no merges occurred (length didn't change), we're done
            if len(merged) == len(current_lines):
                return current_lines
            
            current_lines = merged
            iteration += 1
        
        # If we hit max iterations, return what we have
        if iteration >= max_iterations:
            print(f"Warning: Hit maximum merge iterations ({max_iterations})")
            return lines
            
        return current_lines
    
    def _collect_vertical_text(self, lines: List[str], start_idx: int) -> Tuple[str, int]:
        """
        Collect vertically split text starting from given index.
        Returns the collected text and the number of lines consumed.
        """
        if start_idx >= len(lines):
            return '', 0
            
        collected = []
        i = start_idx
        lines_consumed = 0
        
        while i < len(lines) and lines_consumed < self.max_vertical_gap:
            line = lines[i].strip()
            
            # If line is a single letter
            if re.match(self.vertical_text_pattern, line):
                collected.append(line)
                lines_consumed += 1
                i += 1
            # If line has multiple single letters (like "a c")
            elif all(len(w) == 1 and w.isalpha() for w in line.split()):
                collected.extend(w for w in line.split())
                lines_consumed += 1
                i += 1
            # If we hit a non-matching line after collecting some letters
            elif collected:
                break
            else:
                return '', 0
        
        if not collected:
            return '', 0
            
        return ''.join(collected), lines_consumed 
    
    def _process_content(self, lines: List[str]) -> Dict:
        """Process content lines to identify tables or clean text."""
        # Check if content might be a table
        table = self.table_processor.detect_table(lines)
        if table:
            return table
        
        # If not a table, clean up the text lines
        cleaned_lines = []
        for line in lines:
            cleaned = self._clean_content_line(line)
            if cleaned:
                cleaned_lines.append(cleaned)
        
        return {
            'type': 'text',
            'lines': cleaned_lines
        }
    
    def _clean_content_line(self, line: str) -> str:
        """Clean a content line from spacing and formatting issues."""
        if not line or not line.strip():
            return ""
        
        # Apply basic cleaning
        line = line.strip()
        
        # Fix spaced out text (like "D u n g e o n s")
        if re.search(r'\b([A-Za-z](\s+[A-Za-z]){2,})\b', line):
            # Find all instances of spaced text
            spaced_segments = re.findall(r'\b([A-Za-z](\s+[A-Za-z]){2,})\b', line)
            for spaced_segment in spaced_segments:
                spaced_word = spaced_segment[0]  # Get the full match
                
                # Only clean if it's actually a spaced word (e.g., "D u n g e o n s")
                # and not something like "I am a" which could match the pattern
                if len(spaced_word) > 5:  # arbitrary threshold to avoid false positives
                    normalized = re.sub(r'\s+', '', spaced_word)
                    line = line.replace(spaced_word, normalized)
        
        # Fix common D&D terms
        line = re.sub(r'D\s*&\s*D', 'D&D', line)
        line = re.sub(r'Dungeons\s*&\s*Dragons', 'Dungeons & Dragons', line)
        
        # Fix weird internal spacing in words like "m ore" -> "more"
        line = re.sub(r'([a-z])\s([a-z])', r'\1\2', line)
        
        # Clean up any double spaces
        line = re.sub(r'\s{2,}', ' ', line)
        
        return line.strip() 