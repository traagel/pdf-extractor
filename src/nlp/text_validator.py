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

class TextValidator:
    """Validates text with a more lightweight approach."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        
        # Load a simple word list instead of using NLTK
        self.logger.debug("Loading common English words...")
        self.common_words = self._load_common_words()
        
        # D&D specific terms to ignore
        self.dnd_terms = {
            'dnd', 'dexterity', 'charisma', 'proficiency', 'longsword', 'shortsword',
            'quarterstaff', 'crossbow', 'spellcaster', 'hitpoints', 'hp', 'ac',
            'multiclass', 'subclass', 'druid', 'barbarian', 'paladin', 'warlock',
            'sorcerer', 'rogue', 'ranger', 'wizard', 'bard', 'cleric', 'monk',
            'fighter', 'halfling', 'dwarf', 'elf', 'gnome', 'tiefling', 'aasimar',
            'proficiencies', 'spellcasting', 'cantrip', 'cantrips', 'unarmored'
        }
        
        # Add the D&D terms to our common words
        self.common_words.update(self.dnd_terms)
        
        # Configure validation parameters
        self.min_word_length = 3
        self.min_english_word_ratio = 0.75
    
    def _load_common_words(self):
        """Load a basic set of common English words."""
        # Start with a small set of very common words
        common_words = set([
            'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'it',
            'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at', 'this',
            'but', 'his', 'by', 'from', 'they', 'we', 'say', 'her', 'she', 'or',
            'an', 'will', 'my', 'one', 'all', 'would', 'there', 'their', 'what',
            'so', 'up', 'out', 'if', 'about', 'who', 'get', 'which', 'go', 'me',
            # ... add more common words as needed
        ])
        
        # Try to load a more extensive list from a file if available
        try:
            word_file = 'data/resources/common_words.txt'
            with open(word_file, 'r') as f:
                for line in f:
                    word = line.strip().lower()
                    if word:
                        common_words.add(word)
            self.logger.debug(f"Loaded {len(common_words)} words from {word_file}")
        except Exception as e:
            self.logger.warning(f"Could not load word file: {e}")
        
        return common_words
    
    def simple_tokenize(self, text):
        """Simple tokenization function."""
        # Remove punctuation and convert to lowercase
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        # Split on whitespace and filter out empty strings
        return [word for word in text.split() if word]
    
    def validate_text(self, text: str, timeout_sec=0.1) -> Dict:
        """
        Validate text for potential issues with a timeout.
        
        Args:
            text: String to validate
            timeout_sec: Timeout in seconds to prevent hanging
            
        Returns:
            Dictionary containing validation results
        """
        self.logger.debug(f"Validating text: {text[:50]}...")
        
        # Skip if text is too short
        if not text or len(text) < 10:
            self.logger.debug("Text too short, skipping validation")
            return {'text': text, 'issues': [], 'valid': True}
        
        start_time = time.time()
        
        # Tokenize the text (simple method to avoid NLTK issues)
        words = self.simple_tokenize(text)
        words = [w for w in words if len(w) >= self.min_word_length]
        
        # Skip if too few words
        if len(words) < 3:
            return {'text': text, 'issues': [], 'valid': True}
        
        # Find unknown words (not in our common word list)
        unknown_words = [w for w in words if w not in self.common_words]
        
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
            'text': text,
            'issues': issues,
            'valid': len(issues) == 0,
            'metrics': {
                'total_words': len(words),
                'unknown_words': len(unknown_words)
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
        self.logger.debug(f"Validating chapter {chapter.get('number', 'unknown')}: {chapter.get('title', 'untitled')}")
        
        results = {
            'chapter_number': chapter.get('number'),
            'chapter_title': chapter.get('title'),
            'main_content': [],
            'subchapters': [],
            'tables': []
        }
        
        # Get content to validate
        main_content = chapter['content']['main_content']
        subchapters = chapter['content']['subchapters']
        tables = chapter['content']['tables']
        
        # Calculate total items to validate for progress bar
        total_items = len(main_content) + len(subchapters) + len(tables)
        
        # Create progress bar if requested
        pbar = None
        if with_progress and total_items > 10:
            pbar = tqdm(total=total_items, desc=f"Validating Ch.{chapter.get('number', '?')}")
        
        try:
            # Validate main content with sampling to avoid getting stuck
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
                        pbar.update(1)
            
            # ... handle subchapters and tables similarly
            
        finally:
            if pbar:
                pbar.close()
        
        return results 