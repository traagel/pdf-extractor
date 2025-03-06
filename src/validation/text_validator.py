"""
Text validation module for checking the quality of extracted text.
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

@dataclass
class ValidationResult:
    """Container for validation results."""
    is_valid: bool
    issues: List[str]
    metrics: Dict[str, float]
    cleaned_text: Optional[str] = None

class TextValidator:
    """
    Validates and analyzes extracted text for common issues and quality metrics.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        
        # Configure validation thresholds with more PDF-appropriate defaults
        self.min_words = self.config.get('min_words', 50)
        self.max_line_length = self.config.get('max_line_length', 2000)  # Increased for PDF content
        self.max_repeated_chars = self.config.get('max_repeated_chars', 100)  # Increased for table of contents
        self.min_avg_word_length = self.config.get('min_avg_word_length', 2)  # Decreased for abbreviations
        self.max_avg_word_length = self.config.get('max_avg_word_length', 15)
        
        # Characters that are allowed to repeat (for formatting)
        self.allowed_repeating_chars = set('._- \t')
        
    def validate(self, text: str) -> ValidationResult:
        """
        Validate extracted text for common issues.
        
        Args:
            text: Text to validate
            
        Returns:
            ValidationResult containing validation status and details
        """
        issues = []
        metrics = {}
        
        # Basic text cleanup
        cleaned_text = self._clean_text(text)
        
        # Perform various validations
        word_count = self._count_words(cleaned_text)
        avg_word_length = self._average_word_length(cleaned_text)
        line_issues = self._check_line_issues(cleaned_text)
        char_issues = self._check_character_issues(cleaned_text)
        
        # Record metrics
        metrics['word_count'] = word_count
        metrics['avg_word_length'] = avg_word_length
        metrics['unique_chars'] = len(set(cleaned_text))
        
        # Check word count
        if word_count < self.min_words:
            issues.append(f"Text contains too few words ({word_count} < {self.min_words})")
            
        # Check average word length
        if avg_word_length < self.min_avg_word_length:
            issues.append(f"Average word length too short ({avg_word_length:.1f} < {self.min_avg_word_length})")
        elif avg_word_length > self.max_avg_word_length:
            issues.append(f"Average word length too long ({avg_word_length:.1f} > {self.max_avg_word_length})")
            
        # Add line and character issues
        issues.extend(line_issues)
        issues.extend(char_issues)
        
        # Determine if text is valid
        is_valid = len(issues) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            issues=issues,
            metrics=metrics,
            cleaned_text=cleaned_text
        )
        
    def _clean_text(self, text: str) -> str:
        """Basic text cleanup."""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove excessive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()
        
    def _count_words(self, text: str) -> int:
        """Count words in text."""
        return len(text.split())
        
    def _average_word_length(self, text: str) -> float:
        """Calculate average word length."""
        words = text.split()
        if not words:
            return 0.0
        return sum(len(word) for word in words) / len(words)
        
    def _check_line_issues(self, text: str) -> List[str]:
        """Check for issues with line formatting."""
        issues = []
        
        # Check for overly long lines
        lines = text.split('\n')
        for i, line in enumerate(lines, 1):
            if len(line) > self.max_line_length:
                issues.append(f"Line {i} exceeds maximum length ({len(line)} > {self.max_line_length})")
                
        # Check for potential header/footer repetition
        if self._detect_header_footer_repetition(lines):
            issues.append("Detected possible header/footer repetition")
            
        return issues
        
    def _check_character_issues(self, text: str) -> List[str]:
        """Check for character-level issues."""
        issues = []
        
        # Check for repeated characters (possible OCR errors)
        for match in re.finditer(r'(.)\1{' + str(self.max_repeated_chars) + ',}', text):
            char = match.group(1)
            # Skip reporting repeating characters that are allowed
            if char not in self.allowed_repeating_chars:
                count = len(match.group(0))
                issues.append(f"Found {count} repeated '{char}' characters")
            
        # Check for unusual character combinations, excluding common PDF patterns
        unusual_patterns = [
            (r'[^\x00-\x7F]+', "Non-ASCII characters detected")
        ]
        
        for pattern, message in unusual_patterns:
            if re.search(pattern, text):
                issues.append(message)
                
        return issues
        
    def _detect_header_footer_repetition(self, lines: List[str]) -> bool:
        """Detect potential header/footer repetition."""
        if len(lines) < 4:
            return False
            
        # Check first and last lines of consecutive pages
        line_groups = [lines[i:i+2] for i in range(0, len(lines)-1, 2)]
        headers = [group[0] for group in line_groups]
        footers = [group[-1] for group in line_groups]
        
        # Check if headers or footers are suspiciously similar
        return (len(set(headers)) == 1 and len(headers) > 2) or \
               (len(set(footers)) == 1 and len(footers) > 2)
