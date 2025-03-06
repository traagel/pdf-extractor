"""
Line-based text processor for splitting text into lines.
"""

import re
from typing import List, Dict

class LineProcessor:
    """Processes text into lines."""
    
    def __init__(self):
        self.max_line_length = 2000
        
    def process(self, text: str) -> Dict:
        """
        Process text into lines with basic cleaning.
        
        Args:
            text: Raw text to process
            
        Returns:
            Dictionary containing processed lines and metadata
        """
        # Initial line splitting
        raw_lines = text.split('\n')
        
        # Clean and normalize lines
        processed_lines = []
        for line in raw_lines:
            # Clean the line
            line = self._clean_line(line)
            if not line:
                continue
                
            # Split long lines
            if len(line) > self.max_line_length:
                split_lines = self._split_long_line(line)
                processed_lines.extend(split_lines)
            else:
                processed_lines.append(line)
        
        return {
            'lines': processed_lines,
            'stats': {
                'total_lines': len(processed_lines),
                'avg_line_length': sum(len(l) for l in processed_lines) / len(processed_lines) if processed_lines else 0,
                'max_line_length': max(len(l) for l in processed_lines) if processed_lines else 0
            }
        }
    
    def _clean_line(self, line: str) -> str:
        """Clean a single line of text."""
        # Remove excessive whitespace
        return re.sub(r'\s+', ' ', line.strip())
    
    def _split_long_line(self, line: str, max_length: int = 2000) -> List[str]:
        """Split a long line at sensible break points."""
        if len(line) <= max_length:
            return [line]
            
        lines = []
        current_line = []
        current_length = 0
        
        # Try to split on sentence boundaries first
        sentences = re.split(r'([.!?])\s+', line)
        
        for i in range(0, len(sentences), 2):
            sentence = sentences[i]
            punctuation = sentences[i + 1] if i + 1 < len(sentences) else ''
            
            if current_length + len(sentence) + len(punctuation) + 1 <= max_length:
                current_line.append(sentence + punctuation)
                current_length += len(sentence) + len(punctuation) + 1
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [sentence + punctuation]
                current_length = len(sentence) + len(punctuation)
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines 