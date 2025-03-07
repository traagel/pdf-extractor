"""
NLP-based validator for markdown content to detect typos and errors.
"""

import re
import markdown
from typing import Dict, List, Tuple, Optional, Set
from bs4 import BeautifulSoup
from dataclasses import dataclass

from .word_correction import WordCorrector
from ..utils.logger import get_logger

@dataclass
class MarkdownError:
    """Represents an error found in markdown content."""
    line_num: int
    column: int
    text: str
    suggestion: str
    confidence: float
    context: str

class MarkdownValidator:
    """
    Validates markdown content to detect typos and errors using NLP techniques.
    
    This validator can be used as a final quality check on processed markdown
    content before it's published or used.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize the markdown validator with configuration options."""
        self.config = config or {}
        self.logger = get_logger(__name__)
        
        # Initialize word corrector
        self.word_corrector = WordCorrector(self.config.get('word_correction', {}))
        
        # Configure validation parameters
        self.min_confidence = self.config.get('min_confidence', 0.85)
        self.ignore_code_blocks = self.config.get('ignore_code_blocks', True)
        self.max_errors_per_section = self.config.get('max_errors_per_section', 10)
        
    def validate_markdown(self, content: str) -> List[MarkdownError]:
        """
        Validate markdown content to detect typos and errors.
        
        Args:
            content: Markdown content to validate
            
        Returns:
            List of MarkdownError objects
        """
        self.logger.debug("Validating markdown content...")
        
        # Split content into lines for better error reporting
        lines = content.split('\n')
        
        # Extract sections to process (skip code blocks if configured)
        sections = self._extract_sections(lines)
        
        # Validate each section
        errors = []
        for section in sections:
            section_errors = self._validate_section(section, lines)
            
            # Limit number of errors per section to avoid overwhelming output
            errors.extend(section_errors[:self.max_errors_per_section])
            
            # Add an indication if errors were truncated
            if len(section_errors) > self.max_errors_per_section:
                self.logger.debug(f"Truncated {len(section_errors) - self.max_errors_per_section} errors in section")
        
        self.logger.debug(f"Found {len(errors)} errors in markdown content")
        return errors
        
    def _extract_sections(self, lines: List[str]) -> List[Dict]:
        """
        Extract sections from markdown content.
        
        Args:
            lines: List of lines from markdown content
            
        Returns:
            List of section dictionaries with start_line, end_line, and text
        """
        sections = []
        current_section = {"start_line": 0, "text": [], "type": "text"}
        in_code_block = False
        
        for i, line in enumerate(lines):
            # Check for code block markers
            if line.strip().startswith("```"):
                if in_code_block:
                    # End of code block
                    in_code_block = False
                    
                    # Only finish the code section if we're not ignoring code blocks
                    if not self.ignore_code_blocks:
                        current_section["end_line"] = i
                        current_section["text"].append(line)
                        sections.append(current_section)
                        
                    # Start a new text section
                    current_section = {"start_line": i + 1, "text": [], "type": "text"}
                else:
                    # Start of code block
                    # Finish the current text section
                    current_section["end_line"] = i
                    sections.append(current_section)
                    
                    # Start a new code section
                    in_code_block = True
                    current_section = {"start_line": i, "text": [line], "type": "code"}
            else:
                # Regular line, add to current section
                current_section["text"].append(line)
        
        # Add the final section
        if current_section["text"]:
            current_section["end_line"] = len(lines)
            sections.append(current_section)
        
        # Filter out code blocks if configured
        if self.ignore_code_blocks:
            sections = [s for s in sections if s["type"] == "text"]
            
        return sections
    
    def _validate_section(self, section: Dict, all_lines: List[str]) -> List[MarkdownError]:
        """
        Validate a section of markdown content.
        
        Args:
            section: Section dictionary with start_line, end_line, and text
            all_lines: All lines of the markdown content
            
        Returns:
            List of MarkdownError objects
        """
        errors = []
        
        # Skip code blocks
        if section["type"] == "code" and self.ignore_code_blocks:
            return errors
            
        # Join lines in this section
        text = "\n".join(section["text"])
        
        # Use our word corrector to find potential issues
        words = re.findall(r'\b(\w+)\b', text)
        
        # Track position in the text for error reporting
        pos = 0
        line_offset = section["start_line"]
        
        for word in words:
            # Skip short words
            if len(word) < self.word_corrector.min_word_length:
                pos = text.find(word, pos) + len(word)
                continue
                
            # Check if the word is correct
            corrected, confidence = self.word_corrector.correct_word(word)
            
            # If a correction is suggested with sufficient confidence
            if corrected != word and confidence >= self.min_confidence:
                # Find the position of this word
                word_pos = text.find(word, pos)
                
                # Calculate line and column
                line_index, column = self._get_position(text, word_pos, line_offset)
                
                # Get context (the line containing the error)
                context = all_lines[line_index] if 0 <= line_index < len(all_lines) else ""
                
                # Create error object
                error = MarkdownError(
                    line_num=line_index + 1,  # 1-based line numbers
                    column=column + 1,        # 1-based column numbers
                    text=word,
                    suggestion=corrected,
                    confidence=confidence,
                    context=context
                )
                errors.append(error)
                
            # Move past this word
            pos = text.find(word, pos) + len(word)
        
        return errors
    
    def _get_position(self, text: str, pos: int, line_offset: int) -> Tuple[int, int]:
        """
        Get line and column for a position in the text.
        
        Args:
            text: The text to search in
            pos: Position in the text
            line_offset: Line offset from the start of the document
            
        Returns:
            Tuple of (line_index, column)
        """
        # Get the text up to this position
        text_up_to_pos = text[:pos]
        
        # Count newlines to determine the line
        lines = text_up_to_pos.split('\n')
        line_index = len(lines) - 1 + line_offset
        
        # Column is the length of the last line
        column = len(lines[-1])
        
        return line_index, column
    
    def format_errors(self, errors: List[MarkdownError], show_context: bool = True) -> str:
        """
        Format errors for display.
        
        Args:
            errors: List of MarkdownError objects
            show_context: Whether to show context (the line with the error)
            
        Returns:
            Formatted error report
        """
        if not errors:
            return "No errors found!"
            
        report = []
        report.append(f"Found {len(errors)} potential errors:")
        report.append("")
        
        for i, error in enumerate(errors, 1):
            report.append(f"{i}. Line {error.line_num}, Col {error.column}: '{error.text}' → '{error.suggestion}' ({error.confidence:.2f})")
            if show_context and error.context:
                # Show context with the error highlighted (between >>> <<<)
                highlighted_context = error.context.replace(error.text, f">>>{error.text}<<<", 1)
                report.append(f"   {highlighted_context}")
                report.append("")
        
        return "\n".join(report)
    
    def validate_and_report(self, markdown_file: str, output_file: Optional[str] = None) -> str:
        """
        Validate a markdown file and generate a report.
        
        Args:
            markdown_file: Path to markdown file to validate
            output_file: Path to write report to (optional)
            
        Returns:
            Formatted error report
        """
        try:
            with open(markdown_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            errors = self.validate_markdown(content)
            report = self.format_errors(errors)
            
            if output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(report)
                self.logger.info(f"Validation report written to {output_file}")
                
            return report
            
        except Exception as e:
            self.logger.error(f"Error validating markdown file: {e}")
            return f"Error validating markdown file: {e}" 