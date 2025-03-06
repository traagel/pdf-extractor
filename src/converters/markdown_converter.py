"""
Converter for transforming extracted PDF content into Markdown format.
"""

import os
import yaml
import json
from pathlib import Path
from typing import Dict, Any, Union, List, Optional
import re
import argparse
from tqdm import tqdm

from ..utils.logger import get_logger
from ..nlp.text_cleaner import TextCleaner

logger = get_logger(__name__)

class MarkdownConverter:
    """Converts extracted PDF content into formatted Markdown."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Markdown converter.
        
        Args:
            config: Optional configuration options
        """
        self.config = config or {}
        self.toc_enabled = self.config.get('toc', True)
        self.include_validation = self.config.get('include_validation', False)
        self.table_style = self.config.get('table_style', 'github')
        self.keep_front_matter = self.config.get('keep_front_matter', False)
        self.aggressive_cleaning = self.config.get('aggressive_cleaning', False)
        self.text_cleaning = self.config.get('text_cleaning', 'light')
        self.text_cleaner = TextCleaner({
            'cleaning_level': self.text_cleaning
        }) if self.text_cleaning != 'none' else None
        
    def convert(self, data: Dict[str, Any]) -> str:
        """
        Convert extracted PDF data to Markdown.
        
        Args:
            data: Extracted data dictionary (from lines_chapters_validation output)
            
        Returns:
            Markdown formatted string
        """
        output = []
        
        # Add document title
        filename = data.get('filename', 'Untitled Document')
        title = self._clean_filename(filename)
        output.append(f"# {title}")
        output.append("")
        
        # Add metadata
        output.append(f"*Extracted on: {data.get('extraction_date', 'Unknown date')}*")
        output.append("")
        
        # Filter out chapters that shouldn't be included
        filtered_chapters = []
        if 'content' in data and 'chapters' in data['content']:
            filtered_chapters = []
            for ch in data['content']['chapters']:
                # Skip Front Matter if configured
                if not self.keep_front_matter and ch.get('title') == 'Front Matter' and ch.get('number') == 0:
                    continue
                    
                # Skip chapters that look like TOC entries (with page numbers or dots)
                title = ch.get('title', '')
                if self._looks_like_toc_entry(title) or self._is_appendix_heading(title):
                    continue
                    
                # Normalize chapter title
                if 'title' in ch:
                    ch['title'] = self._normalize_title(ch['title'])
                    
                filtered_chapters.append(ch)
                
            # Replace the chapters with filtered ones for processing
            original_chapters = data['content']['chapters']
            data['content']['chapters'] = filtered_chapters
        
        # Add table of contents if enabled
        if self.toc_enabled and 'content' in data and 'chapters' in data['content']:
            output.append("## Table of Contents")
            output.append("")
            
            for chapter in data['content']['chapters']:
                chapter_num = chapter.get('number', '')
                chapter_title = chapter.get('title', 'Untitled Chapter')
                
                # Create anchor link
                anchor = self._create_anchor(f"{chapter_num}-{chapter_title}")
                output.append(f"- [{chapter_num}. {chapter_title}](#{anchor})")
                
                # Add subchapters to TOC if present
                if 'content' in chapter and 'subchapters' in chapter['content']:
                    for subchapter in chapter['content']['subchapters']:
                        sub_title = subchapter.get('title', 'Untitled Section')
                        sub_anchor = self._create_anchor(f"{chapter_num}-{sub_title}")
                        output.append(f"  - [{sub_title}](#{sub_anchor})")
                        
            output.append("")
        
        # Apply text cleaning if configured
        if self.text_cleaner and self.text_cleaning != 'none':
            # Apply NLP-based cleaning to chapters
            if 'content' in data and 'chapters' in data['content']:
                cleaned_chapters = []
                for chapter in data['content']['chapters']:
                    cleaned_chapter = self.text_cleaner.clean_chapter(chapter)
                    cleaned_chapters.append(cleaned_chapter)
                
                # Use cleaned chapters for processing
                original_chapters = data['content']['chapters']
                data['content']['chapters'] = cleaned_chapters
        
        # Process chapters
        if 'content' in data and 'chapters' in data['content']:
            chapters = data['content']['chapters']
            
            # Show progress bar when processing many chapters
            if len(chapters) > 5:
                chapters_iter = tqdm(chapters, desc="Converting chapters")
            else:
                chapters_iter = chapters
                
            for chapter in chapters_iter:
                output.extend(self._format_chapter(chapter))
        
        # Restore original chapters if we filtered them
        if 'content' in data and 'original_chapters' in locals():
            data['content']['chapters'] = original_chapters
        
        # Apply aggressive cleaning to chapter content if configured
        if self.aggressive_cleaning and 'content' in data and 'chapters' in data['content']:
            for chapter in data['content']['chapters']:
                if 'content' in chapter:
                    # Clean main content
                    if 'main_content' in chapter['content']:
                        chapter['content']['main_content'] = [
                            self._clean_content_text(line) 
                            for line in chapter['content']['main_content']
                        ]
                        
                    # Clean subchapters
                    if 'subchapters' in chapter['content']:
                        for subchapter in chapter['content']['subchapters']:
                            if 'lines' in subchapter:
                                subchapter['lines'] = [
                                    self._clean_content_text(line) 
                                    for line in subchapter['lines']
                                ]
        
        return "\n".join(output)
    
    def _format_chapter(self, chapter: Dict[str, Any]) -> List[str]:
        """Format a chapter as Markdown."""
        output = []
        
        # Chapter title
        chapter_num = chapter.get('number', '')
        chapter_title = chapter.get('title', 'Untitled Chapter')
        
        if chapter_num:
            output.append(f"## {chapter_num}. {chapter_title}")
        else:
            output.append(f"## {chapter_title}")
            
        output.append("")
        
        # Chapter content
        if 'content' in chapter:
            # Main content
            if 'main_content' in chapter['content'] and chapter['content']['main_content']:
                # Join lines with proper paragraph breaks
                content = self._format_paragraphs(chapter['content']['main_content'])
                output.append(content)
                output.append("")
            
            # Tables
            if 'tables' in chapter['content'] and chapter['content']['tables']:
                for table in chapter['content']['tables']:
                    output.extend(self._format_table(table))
                    output.append("")
            
            # Subchapters
            if 'subchapters' in chapter['content'] and chapter['content']['subchapters']:
                for subchapter in chapter['content']['subchapters']:
                    output.extend(self._format_subchapter(subchapter, chapter_num))
        
        return output
    
    def _format_subchapter(self, subchapter: Dict[str, Any], chapter_num: str) -> List[str]:
        """Format a subchapter as Markdown."""
        output = []
        
        # Subchapter title
        sub_title = subchapter.get('title', 'Untitled Section')
        output.append(f"### {sub_title}")
        output.append("")
        
        # Subchapter content
        if 'lines' in subchapter and subchapter['lines']:
            content = self._format_paragraphs(subchapter['lines'])
            output.append(content)
            output.append("")
        
        return output
    
    def _format_paragraphs(self, lines: List[str]) -> str:
        """Format lines into proper paragraphs with clean text."""
        if not lines:
            return ""
        
        # First pass: clean up individual lines
        cleaned_lines = []
        for line in lines:
            # Clean spacing issues
            cleaned = self._clean_content_text(line)
            cleaned_lines.append(cleaned)
        
        # Second pass: join lines into paragraphs
        paragraphs = []
        current_para = []
        
        for line in cleaned_lines:
            # Skip empty lines
            if not line.strip():
                if current_para:
                    paragraphs.append(" ".join(current_para))
                    current_para = []
                continue
            
            # Add line to current paragraph
            current_para.append(line)
        
        # Add the last paragraph if there is one
        if current_para:
            paragraphs.append(" ".join(current_para))
        
        # Join paragraphs with double newlines
        return "\n\n".join(paragraphs)
    
    def _clean_content_text(self, text: str) -> str:
        """Clean content text by removing abnormal spacing and fixing common issues."""
        if not text or len(text) < 3:
            return text
        
        # Make a copy of the original text
        current_text = text.strip()
        
        # Fix only truly spaced-out words like "D u n g e o n s" -> "Dungeons"
        # This pattern specifically looks for single letters separated by spaces
        spaced_word_pattern = r'\b([A-Za-z])\s+([A-Za-z])\s+([A-Za-z])'
        
        # Keep searching for patterns of "X y Z" (3+ single letters with spaces)
        while re.search(spaced_word_pattern, current_text):
            match = re.search(spaced_word_pattern, current_text)
            if match:
                # Only grab the exact matched portion
                full_match = match.group(0)
                
                # Check if this is really a spaced word (vs. normal text)
                if len(full_match) >= 5 and all(len(c) == 1 for c in full_match.split() if c.isalpha()):
                    # This is a spaced word like "D u n g e o n s"
                    normalized = re.sub(r'\s+', '', full_match)
                    # Only replace the exact match
                    current_text = current_text.replace(full_match, normalized)
                else:
                    # Exit the loop if we can't find a good replacement
                    break
        
        # Fix common D&D terms
        current_text = re.sub(r'D\s*&\s*D', 'D&D', current_text)
        current_text = re.sub(r'Dungeons\s*&\s*Dragons', 'Dungeons & Dragons', current_text)
        
        # Fix internal gaps in words like "m ore" -> "more" - but be very careful
        # Only look for cases where we have a lowercase letter, space, lowercase letter
        # and the surrounding context suggests it's a single word
        word_fix_pattern = r'(\b[a-z]+)\s([a-z])'
        matches = list(re.finditer(word_fix_pattern, current_text))
        
        # Process matches in reverse to avoid index issues
        for match in reversed(matches):
            prefix = match.group(1)
            suffix = match.group(2)
            
            # Only combine if the prefix is short (to avoid false positives)
            if len(prefix) <= 2:
                full_word = prefix + suffix
                # Check if this is a common word
                if full_word.lower() in ['more', 'some', 'come', 'name', 'time', 'like', 'take']:
                    start, end = match.span()
                    current_text = current_text[:start] + prefix + suffix + current_text[end:]
        
        # Double-check: make sure we haven't created run-together words
        # Add spaces in obvious cases like "andcreate" -> "and create"
        common_words = ['and', 'the', 'you', 'your', 'with', 'that', 'this', 'from', 'they', 
                       'have', 'what', 'were', 'when', 'will', 'whom', 'their']
        
        for word in common_words:
            # Look for the word without a space after it
            pattern = fr'\b{word}([a-z])'
            current_text = re.sub(pattern, f"{word} \\1", current_text)
        
        # Fix multiple spaces
        current_text = re.sub(r'\s{2,}', ' ', current_text)
        
        return current_text.strip()
    
    def _format_table(self, table: Dict[str, Any]) -> List[str]:
        """Format a table as Markdown."""
        output = []
        
        # Skip tables without proper structure
        if 'table_type' not in table or 'columns' not in table or 'rows' not in table:
            return output
        
        # Add table caption
        table_type = table.get('table_type', 'Table')
        output.append(f"**{table_type.replace('_', ' ').title()}**")
        output.append("")
        
        # Get columns and rows
        columns = table['columns']
        rows = table['rows']
        
        if not columns or not rows:
            return output
        
        # Create header row
        header = "| " + " | ".join(columns) + " |"
        output.append(header)
        
        # Create separator row
        separator = "| " + " | ".join(["---"] * len(columns)) + " |"
        output.append(separator)
        
        # Create data rows
        for row in rows:
            # Ensure row has correct number of columns
            padded_row = row + [''] * (len(columns) - len(row))
            data_row = "| " + " | ".join(str(cell) for cell in padded_row[:len(columns)]) + " |"
            output.append(data_row)
        
        output.append("")
        return output
    
    def _clean_filename(self, filename: str) -> str:
        """Clean filename to create a title."""
        # Remove extension and replace underscores/hyphens with spaces
        title = os.path.splitext(filename)[0]
        title = title.replace('_', ' ').replace('-', ' ')
        
        # Capitalize words
        return title.title()
    
    def _create_anchor(self, text: str) -> str:
        """Create a GitHub-style anchor from text."""
        # Convert to lowercase
        anchor = text.lower()
        
        # Replace spaces with hyphens
        anchor = anchor.replace(' ', '-')
        
        # Remove non-alphanumeric characters
        anchor = re.sub(r'[^\w-]', '', anchor)
        
        return anchor
    
    def _looks_like_toc_entry(self, text: str) -> bool:
        """Check if text looks like a table of contents entry."""
        # Check for patterns that indicate TOC entries
        # - Lines with dots (........)
        # - Lines ending with page numbers
        # - Lines with spaced text followed by page number
        
        if '.' * 5 in text:  # Contains a series of dots
            return True
        
        # Check for line ending with page number pattern
        if re.search(r'\s\d+$', text):
            return True
        
        # Check for typical TOC format with chapter name and page number
        if re.search(r'.*\s+\d+$', text):
            return True
        
        return False
    
    def _is_appendix_heading(self, text: str) -> bool:
        """Check if text is an appendix or other non-chapter heading."""
        common_appendix_titles = [
            'index', 'appendix', 'glossary', 'references', 
            'bibliography', 'game dice', 'character sheet',
            'creature statistics', 'inspirational reading',
            'god', 'plane', 'multiverse', 'advantage', 'disadvantage'
        ]
        
        normalized = text.lower()
        return any(title in normalized for title in common_appendix_titles)
    
    def _normalize_title(self, title: str) -> str:
        """Normalize a spaced or oddly formatted title."""
        # First, remove any page numbers and dots
        title = re.sub(r'\.{2,}.*?\d+$', '', title)
        
        # Remove all dots and ellipses
        title = re.sub(r'\.{3,}', '', title)
        
        # Replace multiple spaces, hyphens with single space
        title = re.sub(r'[\s\-]+', ' ', title)
        
        # Special case for "Personality and Background"
        if 'personalityand' in title.lower():
            title = re.sub(r'[Pp]ersonalityand', 'Personality and', title)
        
        # Special case for "Step by Step Characters" with weird spacing
        if re.search(r'(?i)st\s*[e\s]*p\s*[b\s]*y\s*[s\s]*t\s*e\s*p\s*characters', title):
            return "Step-by-Step Characters"
        
        # Fix common capitalization issues in conjoined words
        for word_pair in [('Backgroundand', 'Background and'), 
                          ('Equipmentand', 'Equipment and'),
                          ('Spellsand', 'Spells and')]:
            title = title.replace(word_pair[0], word_pair[1])
        
        # Handle spaced text like "S t e p" -> "Step"
        # Look for patterns like "B a c k g r o u n d"
        spaced_text_pattern = r'([A-Za-z])(\s+[A-Za-z])+\b'
        
        while re.search(spaced_text_pattern, title):
            match = re.search(spaced_text_pattern, title)
            if match:
                spaced_word = match.group(0)
                normalized = re.sub(r'\s+', '', spaced_word)
                title = title.replace(spaced_word, normalized)
        
        # Clean up the text
        title = title.strip()
        
        # Fix casing - capitalize first letter of each word
        words = title.split()
        if words:
            title = ' '.join(word.capitalize() for word in words)
        
        # Special case for D&D
        title = title.replace('Dungeons & Dragons', 'Dungeons & Dragons')
        title = title.replace('D & D', 'D&D')
        title = title.replace('D&d', 'D&D')
        
        return title


def convert_to_markdown(input_file: Union[str, Path], output_file: Optional[Union[str, Path]] = None,
                       config: Optional[Dict[str, Any]] = None) -> str:
    """
    Convert extracted PDF data to Markdown.
    
    Args:
        input_file: Path to YAML or JSON file with extracted data
        output_file: Optional path to save Markdown output (if None, returns string)
        config: Optional configuration options
        
    Returns:
        Markdown string if output_file is None, otherwise empty string
    """
    input_path = Path(input_file)
    
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    
    # Determine file type from extension
    file_ext = input_path.suffix.lower()
    
    # Load data from file
    with open(input_path, 'r', encoding='utf-8') as f:
        if file_ext == '.yaml' or file_ext == '.yml':
            data = yaml.safe_load(f)
        elif file_ext == '.json':
            data = json.load(f)
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")
    
    # Create converter and convert data
    converter = MarkdownConverter(config)
    markdown = converter.convert(data)
    
    # Save to file if output_file is provided
    if output_file:
        output_path = Path(output_file)
        os.makedirs(output_path.parent, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown)
        
        logger.info(f"Markdown saved to {output_path}")
        return ""
    
    return markdown


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert extracted PDF data to Markdown")
    
    parser.add_argument(
        "input",
        help="Path to YAML or JSON file with extracted data"
    )
    
    parser.add_argument(
        "-o", "--output",
        help="Path to save Markdown output"
    )
    
    parser.add_argument(
        "--no-toc",
        action="store_true",
        help="Disable table of contents generation"
    )
    
    parser.add_argument(
        "--include-validation",
        action="store_true",
        help="Include validation results in output"
    )
    
    args = parser.parse_args()
    
    # Configure options
    config = {
        'toc': not args.no_toc,
        'include_validation': args.include_validation
    }
    
    # Convert file
    convert_to_markdown(args.input, args.output, config) 