"""
NLP-based text cleaner for fixing PDF extraction artifacts.
"""

import re
import string
from typing import List, Dict, Any, Optional
from collections import Counter

# Try to import spaCy if available
try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

from ..utils.logger import get_logger

logger = get_logger(__name__)

class TextCleaner:
    """Uses NLP techniques to clean and normalize extracted text."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the text cleaner with configuration."""
        self.config = config or {}
        self.cleaning_level = self.config.get('cleaning_level', 'light')
        
        # Load resources
        self._load_resources()
        
    def _load_resources(self):
        """Load necessary resources for text cleaning."""
        # Common words that are often run together
        self.common_words = {
            'the', 'and', 'of', 'to', 'a', 'in', 'for', 'is', 'on', 'that', 'by',
            'this', 'with', 'you', 'it', 'not', 'or', 'be', 'are', 'from', 'at',
            'as', 'your', 'have', 'more', 'an', 'was', 'we', 'will', 'can', 'do',
            'use', 'one', 'they', 'all', 'their', 'has', 'been', 'would', 'make',
            'about', 'if', 'into', 'time', 'only', 'how', 'may', 'its', 'some', 'what',
            'when', 'out', 'up', 'no', 'who', 'see', 'get', 'which', 'go', 'than',
            'our', 'know', 'just', 'any', 'take', 'give', 'over', 'think', 'also',
            'back', 'after', 'other', 'use', 'two', 'these', 'first', 'way', 'well',
            'even', 'new', 'want', 'because', 'most', 'each', 'look', 'day', 'could',
            'come', 'both', 'between', 'must'
        }
        
        # D&D specific terms
        self.dnd_terms = {
            'dungeons', 'dragons', 'character', 'adventurer', 'roleplaying', 'fighter',
            'wizard', 'cleric', 'rogue', 'barbarian', 'druid', 'halfling', 'dwarf',
            'elf', 'game', 'dungeon', 'spellcaster', 'paladin', 'bard', 'sorcerer',
            'warlock', 'ranger', 'monk', 'human', 'gnome', 'tiefling', 'orc', 'race', 
            'class', 'abilities', 'skills', 'combat', 'spell', 'magic', 'weapon', 
            'armor', 'shield', 'potion', 'alignment', 'creature', 'monster'
        }
        
        # Load spaCy model if available and configured to use it
        self.nlp = None
        if self.cleaning_level == 'advanced' and SPACY_AVAILABLE:
            try:
                self.nlp = spacy.load("en_core_web_sm")
                logger.info("Loaded spaCy NLP model for text cleaning")
            except Exception as e:
                logger.warning(f"Failed to load spaCy model: {str(e)}")
        
    def clean_paragraph(self, text: str) -> str:
        """
        Clean a paragraph of text using NLP techniques.
        
        Args:
            text: The text to clean
            
        Returns:
            Cleaned text
        """
        if not text or len(text) < 5:
            return text
        
        # Start with basic/light cleaning
        cleaned_text = self._fix_spaced_words(text)
        cleaned_text = self._fix_common_dnd_terms(cleaned_text)
        
        # If using light or advanced level, add more processing
        if self.cleaning_level in ['light', 'advanced']:
            cleaned_text = self._fix_run_together_words(cleaned_text)
            cleaned_text = self._fix_common_spacing_issues(cleaned_text)
        
        # If using advanced level and spaCy is available, use NLP
        if self.cleaning_level == 'advanced' and self.nlp:
            cleaned_text = self._apply_spacy_cleaning(cleaned_text)
        
        return cleaned_text
        
    def _fix_spaced_words(self, text: str) -> str:
        """Fix words with abnormal spacing like 'D u n g e o n s'."""
        # Fix spaced out text (like "D u n g e o n s")
        spaced_word_pattern = r'\b([A-Za-z])\s+([A-Za-z])\s+([A-Za-z])(?:\s+[A-Za-z])*\b'
        
        # Find all instances of spaced text
        matches = list(re.finditer(spaced_word_pattern, text))
        
        # Process matches in reverse order to avoid index issues
        for match in reversed(matches):
            spaced_word = match.group(0)
            
            # If the match is long enough to be a spaced word (not just normal text)
            if len(spaced_word) >= 5 and all(c.isalpha() or c.isspace() for c in spaced_word):
                # Create normalized version by removing spaces
                normalized = re.sub(r'\s+', '', spaced_word)
                
                # Replace just the matched portion
                start, end = match.span()
                text = text[:start] + normalized + text[end:]
        
        return text
    
    def _fix_common_dnd_terms(self, text: str) -> str:
        """Fix common D&D terms that are frequently mis-spaced."""
        # Fix D&D
        text = re.sub(r'D\s*&\s*D', 'D&D', text)
        
        # Fix Dungeons & Dragons with various spacing issues
        dungeons_pattern = r'Dun\s*g?e?o?n?s?\s*&\s*Dra\s*g?o?n?s?'
        if re.search(dungeons_pattern, text, re.IGNORECASE):
            text = re.sub(dungeons_pattern, 'Dungeons & Dragons', text, flags=re.IGNORECASE)
        
        return text
    
    def _fix_run_together_words(self, text: str) -> str:
        """Fix words that are run together without proper spacing."""
        # Look for common words that might be run together
        for word in sorted(self.common_words, key=len, reverse=True):
            if len(word) >= 3:  # Only process words of reasonable length
                # Pattern to find the word not preceded by a space or start of string
                pattern = r'(?<=[a-zA-Z])(' + re.escape(word) + r')'
                text = re.sub(pattern, f" {word}", text)
                
                # Pattern to find the word not followed by a space or end of string
                pattern = r'(' + re.escape(word) + r')(?=[a-zA-Z])'
                text = re.sub(pattern, f"{word} ", text)
        
        return text
    
    def _fix_common_spacing_issues(self, text: str) -> str:
        """Fix common spacing issues in the text."""
        # Fix "you r" -> "your"
        text = re.sub(r'\byou\s+r\b', 'your', text)
        
        # Fix "m ore" -> "more"
        text = re.sub(r'\bm\s+ore\b', 'more', text)
        
        # Fix "Do you" without space
        text = re.sub(r'\bDoyou\b', 'Do you', text)
        
        # Fix "the se" -> "these"
        text = re.sub(r'\bthe\s+se\b', 'these', text)
        
        # Fix "what ever" -> "whatever"
        text = re.sub(r'\bwhat\s+ever\b', 'whatever', text)
        
        # Fix "it'sa" -> "it's a"
        text = re.sub(r'\bit\'s\s*a(\w+)', r"it's a \1", text)
        
        # Fix "som e" -> "some"
        text = re.sub(r'\bsom\s+e\b', 'some', text)
        
        # Fix "ofcharacter" -> "of character"
        text = re.sub(r'\bof(\w+)', r'of \1', text)
        
        # Fix any double spaces
        text = re.sub(r'\s{2,}', ' ', text)
        
        return text
    
    def _apply_spacy_cleaning(self, text: str) -> str:
        """Apply spaCy-based cleaning to detect and fix language errors."""
        try:
            # Parse text with spaCy
            doc = self.nlp(text)
            
            # Fix specific issues using NLP analysis
            # (This would be a more advanced implementation)
            
            # For now, return the original text
            return text
        except Exception as e:
            logger.error(f"Error during spaCy processing: {str(e)}")
            return text
            
    def clean_chapter(self, chapter: Dict[str, Any]) -> Dict[str, Any]:
        """Clean all text in a chapter."""
        if 'content' not in chapter:
            return chapter
            
        # Create a copy to avoid modifying the original
        cleaned_chapter = chapter.copy()
        cleaned_chapter['content'] = chapter['content'].copy()
        
        # Clean main content
        if 'main_content' in cleaned_chapter['content']:
            cleaned_chapter['content']['main_content'] = [
                self.clean_paragraph(line) 
                for line in cleaned_chapter['content']['main_content']
            ]
            
        # Clean subchapters
        if 'subchapters' in cleaned_chapter['content']:
            cleaned_subchapters = []
            for subchapter in cleaned_chapter['content']['subchapters']:
                cleaned_sub = subchapter.copy()
                if 'lines' in cleaned_sub:
                    cleaned_sub['lines'] = [
                        self.clean_paragraph(line) 
                        for line in cleaned_sub['lines']
                    ]
                cleaned_subchapters.append(cleaned_sub)
            cleaned_chapter['content']['subchapters'] = cleaned_subchapters
            
        return cleaned_chapter 