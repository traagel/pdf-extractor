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
    error_type: str = "word"  # "word", "phrase", "spacing", "grammar"

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
        
        # Enable different validation types
        self.enable_word_validation = self.config.get('enable_word_validation', True)
        self.enable_phrase_validation = self.config.get('enable_phrase_validation', True)
        self.enable_spacing_validation = self.config.get('enable_spacing_validation', True)
        
        # Initialize pattern lists
        self._initialize_patterns()
        
    def _initialize_patterns(self):
        """Initialize pattern lists for different validation types."""
        # Common spacing errors (split words)
        self.spacing_patterns = [
            # Split pronouns with space
            (r'you\s+r\b', 'your', 0.95),
            (r'you\s+rs\b', 'yours', 0.95),
            (r'o\s+ur\b', 'our', 0.95),
            (r'w\s+e\b', 'we', 0.95),
            (r'th\s+ey\b', 'they', 0.95),
            (r'th\s+em\b', 'them', 0.95),
            (r'th\s+eir\b', 'their', 0.95),
            
            # Common articles and conjunctions
            (r't\s+he\b', 'the', 0.95),
            (r'a\s+nd\b', 'and', 0.95),
            (r'o\s+f\b', 'of', 0.95),
            (r'i\s+n\b', 'in', 0.95),
            (r'o\s+n\b', 'on', 0.95),
            (r'a\s+t\b', 'at', 0.95),
            (r'b\s+ut\b', 'but', 0.95),
            (r'f\s+or\b', 'for', 0.95),
            
            # Common D&D terms with spaces
            (r'w\s+eapon', 'weapon', 0.95),
            (r'ar\s+mor', 'armor', 0.95),
            (r'c\s+haracter', 'character', 0.95),
            (r's\s+pell', 'spell', 0.95),
            (r'm\s+agic', 'magic', 0.95),
            (r'a\s+bility', 'ability', 0.95),
            (r's\s+kill', 'skill', 0.95),
            (r'c\s+lass', 'class', 0.95),
            (r'r\s+ace', 'race', 0.95),
            
            # Common word breaks at the end of lines
            (r'(\w{2,})-\s*\n\s*(\w{2,})', r'\1\2', 0.9),
            
            # Additional common OCR spacing errors
            (r'som\s+e', 'some', 0.95),
            (r'what\s+ever', 'whatever', 0.95),
            (r'to\s+o', 'too', 0.95),
            (r'with\s+in', 'within', 0.95),
            (r'with\s+out', 'without', 0.95),
            (r'any\s+one', 'anyone', 0.95),
            (r'every\s+one', 'everyone', 0.95),
            (r'some\s+one', 'someone', 0.95),
            (r'no\s+one', 'no one', 0.95),
            
            # More general pattern for any word split by a space
            (r'\b(\w{2})\s+(\w{2,})\b', r'\1\2', 0.85),
        ]
        
        # Add pattern for joined words (missing spaces)
        self.word_join_patterns = [
            (r'weuse', 'we use', 0.95),
            (r'youcan', 'you can', 0.95),
            (r'youhave', 'you have', 0.95),
            (r'youare', 'you are', 0.95),
            (r'youmay', 'you may', 0.95),
            (r'youmust', 'you must', 0.95),
            (r'youmight', 'you might', 0.95),
            (r'youshould', 'you should', 0.95),
            (r'youdo', 'you do', 0.95),
            (r'youget', 'you get', 0.95),
            (r"it'sa", "it's a", 0.95),
            (r"that's(\w+)", r"that's \1", 0.95),
            (r"it's(\w+)", r"it's \1", 0.95),
            (r"there's(\w+)", r"there's \1", 0.95),
            
            # More general pattern for contracted words missing spaces
            (r"(\w+)'s(\w+)", r"\1's \2", 0.9),
        ]
        
        # Common phrase errors
        self.phrase_patterns = [
            # Possessives
            (r'characters?\s+sheet', "character's sheet", 0.9),
            (r'players?\s+handbook', "player's handbook", 0.9),
            (r'dungeon\s+masters?\s+guide', "dungeon master's guide", 0.9),
            
            # D&D-specific phrases
            (r'role\s+play', 'roleplay', 0.9),
            (r'skill\s+check', 'skill check', 0.9),
            (r'saving\s+throws?', 'saving throw', 0.9),
            (r'hit\s+points?', 'hit points', 0.9),
            
            # Common OCR phrase errors
            (r'what ever', 'whatever', 0.95),
            (r'which ever', 'whichever', 0.95),
            (r'how ever', 'however', 0.95),
            (r'when ever', 'whenever', 0.95),
            (r'where ever', 'wherever', 0.95),
            (r'who ever', 'whoever', 0.95),
        ]
        
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
            # Run different validators based on configuration
            section_errors = []
            
            if self.enable_word_validation:
                word_errors = self._validate_words(section, lines)
                section_errors.extend(word_errors)
                
            if self.enable_phrase_validation:
                phrase_errors = self._validate_phrases(section, lines)
                section_errors.extend(phrase_errors)
                
            if self.enable_spacing_validation:
                spacing_errors = self._validate_spacing(section, lines)
                section_errors.extend(spacing_errors)
                # Add word join validation as part of spacing validation
                join_errors = self._validate_word_joins(section, lines)
                section_errors.extend(join_errors)
            
            # Limit number of errors per section to avoid overwhelming output
            errors.extend(section_errors[:self.max_errors_per_section])
            
            # Add an indication if errors were truncated
            if len(section_errors) > self.max_errors_per_section:
                self.logger.debug(f"Truncated {len(section_errors) - self.max_errors_per_section} errors in section")
        
        self.logger.debug(f"Found {len(errors)} errors in markdown content")
        return errors
    
    def _validate_words(self, section: Dict, all_lines: List[str]) -> List[MarkdownError]:
        """
        Validate individual words in a section.
        
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
                    context=context,
                    error_type="word"
                )
                errors.append(error)
                
            # Move past this word
            pos = text.find(word, pos) + len(word)
        
        return errors
        
    def _validate_spacing(self, section: Dict, all_lines: List[str]) -> List[MarkdownError]:
        """
        Validate text for spacing issues.
        
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
        line_offset = section["start_line"]
        
        # Check each spacing pattern
        for pattern, replacement, confidence in self.spacing_patterns:
            # Find all occurrences of the pattern
            for match in re.finditer(pattern, text):
                # Get the matched text
                matched_text = match.group(0)
                
                # Calculate line and column
                line_index, column = self._get_position(text, match.start(), line_offset)
                
                # Get context (the line containing the error)
                context = all_lines[line_index] if 0 <= line_index < len(all_lines) else ""
                
                # Create error object
                error = MarkdownError(
                    line_num=line_index + 1,  # 1-based line numbers
                    column=column + 1,        # 1-based column numbers
                    text=matched_text,
                    suggestion=replacement,
                    confidence=confidence,
                    context=context,
                    error_type="spacing"
                )
                errors.append(error)
        
        return errors
    
    def _validate_phrases(self, section: Dict, all_lines: List[str]) -> List[MarkdownError]:
        """
        Validate text for phrase-level issues.
        
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
        line_offset = section["start_line"]
        
        # Check each phrase pattern
        for pattern, replacement, confidence in self.phrase_patterns:
            # Find all occurrences of the pattern
            for match in re.finditer(pattern, text, re.IGNORECASE):
                # Get the matched text
                matched_text = match.group(0)
                
                # Calculate line and column
                line_index, column = self._get_position(text, match.start(), line_offset)
                
                # Get context (the line containing the error)
                context = all_lines[line_index] if 0 <= line_index < len(all_lines) else ""
                
                # Create error object
                error = MarkdownError(
                    line_num=line_index + 1,  # 1-based line numbers
                    column=column + 1,        # 1-based column numbers
                    text=matched_text,
                    suggestion=replacement,
                    confidence=confidence,
                    context=context,
                    error_type="phrase"
                )
                errors.append(error)
        
        return errors
            
    def _validate_word_joins(self, section: Dict, all_lines: List[str]) -> List[MarkdownError]:
        """
        Validate text for words that should have spaces between them.
        
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
        line_offset = section["start_line"]
        
        # Check each pattern
        for pattern, replacement, confidence in self.word_join_patterns:
            # Find all occurrences of the pattern
            for match in re.finditer(pattern, text, re.IGNORECASE):
                # Get the matched text
                matched_text = match.group(0)
                
                # Calculate line and column
                line_index, column = self._get_position(text, match.start(), line_offset)
                
                # Get context (the line containing the error)
                context = all_lines[line_index] if 0 <= line_index < len(all_lines) else ""
                
                # Create error object
                error = MarkdownError(
                    line_num=line_index + 1,  # 1-based line numbers
                    column=column + 1,        # 1-based column numbers
                    text=matched_text,
                    suggestion=replacement,
                    confidence=confidence,
                    context=context,
                    error_type="joined_words"
                )
                errors.append(error)
        
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
            
        # Group errors by type
        errors_by_type = {}
        for error in errors:
            if error.error_type not in errors_by_type:
                errors_by_type[error.error_type] = []
            errors_by_type[error.error_type].append(error)
            
        report = []
        report.append(f"Found {len(errors)} potential errors:")
        report.append("")
        
        # Print error count by type
        for error_type, type_errors in errors_by_type.items():
            report.append(f"- {len(type_errors)} {error_type} issues")
        report.append("")
        
        # Print all errors
        for i, error in enumerate(errors, 1):
            type_label = f"[{error.error_type.upper()}]"
            report.append(f"{i}. {type_label} Line {error.line_num}, Col {error.column}: '{error.text}' → '{error.suggestion}' ({error.confidence:.2f})")
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