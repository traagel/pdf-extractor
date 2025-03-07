"""
Alternative text validator with better progress tracking and simplified processing.
"""

import re
from typing import List, Dict, Tuple, Optional
import string
from tqdm import tqdm
from collections import Counter
import time

from ..utils.logger import get_logger
from .word_correction import WordCorrector

class TextValidator:
    """Validates text with a more lightweight approach."""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.logger = get_logger(__name__)
        
        # Initialize word corrector
        self.word_corrector = WordCorrector(self.config.get('word_correction', {}))
        
        # Load a simple word list instead of using NLTK
        self.logger.debug("Loading common English words...")
        self.common_words = self.word_corrector.common_words
        self.dnd_terms = self.word_corrector.dnd_terms
        
        # Configure validation parameters
        self.min_word_length = self.config.get('min_word_length', 3)
        self.min_english_word_ratio = self.config.get('min_english_word_ratio', 0.75)
        self.validation_timeout = self.config.get('validation_timeout', 0.5)  # Increased timeout
    
    def simple_tokenize(self, text):
        """Simple tokenization function."""
        # Remove punctuation and convert to lowercase
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        # Split on whitespace and filter out empty strings
        return [word for word in text.split() if word]
    
    def validate_text(self, text: str, timeout_sec=None) -> Dict:
        """
        Validate text for potential issues with a timeout.
        
        Args:
            text: String to validate
            timeout_sec: Timeout in seconds to prevent hanging
            
        Returns:
            Dictionary containing validation results
        """
        if timeout_sec is None:
            timeout_sec = self.validation_timeout
            
        self.logger.debug(f"Validating text: {text[:50]}...")
        
        # Skip if text is too short
        if not text or len(text) < 10:
            self.logger.debug("Text too short, skipping validation")
            return {'text': text, 'issues': [], 'valid': True}
        
        start_time = time.time()
        
        # Apply word correction first
        corrected_text = self.word_corrector.correct_text(text)
        
        # Check if text was corrected
        was_corrected = corrected_text != text
        
        # Tokenize the text (simple method to avoid NLTK issues)
        words = self.simple_tokenize(corrected_text)
        words = [w for w in words if len(w) >= self.min_word_length]
        
        # Skip if too few words
        if len(words) < 3:
            return {'text': corrected_text, 'issues': [], 'valid': True}
        
        # Find unknown words (not in our common word list)
        unknown_words = [w for w in words if w not in self.common_words and w not in self.dnd_terms]
        
        # Check for potential issues, but respect the timeout
        issues = []
        for word in unknown_words[:10]:  # Limit to 10 unknown words to avoid hanging
            # Check if we're approaching the timeout
            if time.time() - start_time > timeout_sec:
                self.logger.warning(f"Validation timeout reached after processing {len(issues)} issues")
                break
                
            # Simple suggestion - just a placeholder for now
            suggestion = self._simple_suggestion(word)
            if suggestion:
                issues.append({
                    'word': word,
                    'suggestion': suggestion,
                    'confidence': 0.7  # Placeholder confidence
                })
        
        return {
            'text': corrected_text,
            'original_text': text if was_corrected else None,
            'issues': issues,
            'valid': len(issues) == 0,
            'metrics': {
                'total_words': len(words),
                'unknown_words': len(unknown_words),
                'was_corrected': was_corrected
            }
        }
    
    def _simple_suggestion(self, word):
        """Very simple word suggestion."""
        # This is just a placeholder - in a real implementation,
        # you'd want a more sophisticated approach
        if len(word) <= 3:
            return None
            
        # Return a similar word from our common words list
        for common_word in self.common_words:
            if common_word.startswith(word[:2]) and abs(len(common_word) - len(word)) <= 2:
                return common_word
                
        return None
    
    def validate_chapter(self, chapter, with_progress=True):
        """
        Validate a chapter with progress tracking.
        
        Args:
            chapter: Chapter data to validate
            with_progress: Whether to show a progress bar
            
        Returns:
            Validation results
        """
        # Get the actual chapter number and title
        chapter_num = chapter.get('number', 0)
        chapter_title = chapter.get('title', 'untitled')
        
        self.logger.debug(f"Validating chapter {chapter_num}: {chapter_title}")
        
        results = {
            'chapter_number': chapter_num,
            'chapter_title': chapter_title,
            'main_content': [],
            'subchapters': [],
            'tables': []
        }
        
        # Safety check for content
        if 'content' not in chapter:
            self.logger.warning(f"Chapter {chapter_num} has no content")
            return results
            
        # Get content to validate
        main_content = chapter.get('content', {}).get('main_content', [])
        subchapters = chapter.get('content', {}).get('subchapters', [])
        tables = chapter.get('content', {}).get('tables', [])
        
        # Calculate total items to validate for progress bar
        total_items = len(main_content) + len(subchapters) + len(tables)
        
        # Create progress bar if requested and if there are items
        pbar = None
        if with_progress and total_items > 0:
            pbar = tqdm(
                total=total_items,
                desc=f"Validating Ch.{chapter_num}",
                leave=True
            )
        
        try:
            # Validate main content with sampling for large contents
            if main_content:
                sample_size = min(50, len(main_content))  # Validate at most 50 lines
                if sample_size > 0:
                    # Use systematic sampling for representative coverage
                    sample_indices = [i * len(main_content) // sample_size for i in range(sample_size)]
                    for i in sample_indices:
                        if i < len(main_content):
                            validation = self.validate_text(main_content[i])
                            if not validation['valid']:
                                results['main_content'].append(validation)
                        
                if pbar:
                    pbar.update(len(main_content))
            
            # Validate subchapters 
            for subchapter in subchapters:
                if 'lines' in subchapter and subchapter['lines']:
                    # Just sample a few lines from each subchapter
                    lines = subchapter['lines']
                    sample = [lines[0]] if lines else []  # First line
                    if len(lines) > 1:
                        sample.append(lines[-1])  # Last line
                    if len(lines) > 10:
                        sample.append(lines[len(lines)//2])  # Middle line
                    
                    sub_issues = []
                    for line in sample:
                        validation = self.validate_text(line)
                        if not validation['valid']:
                            sub_issues.append(validation)
                    
                    if sub_issues:
                        results['subchapters'].append({
                            'title': subchapter.get('title', 'Untitled'),
                            'issues': sub_issues
                        })
                
                if pbar:
                    pbar.update(1)
                    
            # Validate tables (just count them for progress)
            if pbar and tables:
                pbar.update(len(tables))
            
        except Exception as e:
            self.logger.error(f"Error validating chapter {chapter_num}: {e}")
        finally:
            if pbar:
                pbar.close()
        
        return results 