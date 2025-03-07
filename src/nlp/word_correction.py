"""
Word correction module for improving text quality after PDF extraction.
"""

import re
import string
from typing import Dict, List, Tuple, Optional, Set
from collections import Counter
import difflib
from ..utils.logger import get_logger

class WordCorrector:
    """
    Implements word-level correction for text extracted from PDFs.
    
    This class focuses on fixing common OCR errors and word-level issues
    that may remain after broader text cleaning.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize the word corrector with configuration options."""
        self.config = config or {}
        self.logger = get_logger(__name__)
        
        # Load resources
        self._load_resources()
        
        # Configure correction parameters
        self.min_word_length = self.config.get('min_word_length', 3)
        self.min_confidence = self.config.get('min_confidence', 0.7)
        self.context_window = self.config.get('context_window', 2)
        self.max_edit_distance = self.config.get('max_edit_distance', 2)
        self.aggressive_mode = self.config.get('aggressive_mode', False)
        self.fix_hyphenation = self.config.get('fix_hyphenation', True)
        
    def _load_resources(self):
        """Load word dictionaries and other correction resources."""
        # Common English words
        self.common_words = self._load_english_words()
        
        # D&D specific terminology
        self.dnd_terms = {
            # Basic D&D terms
            'dungeons', 'dragons', 'd&d', 'dnd', 'dm', 'pc', 'npc', 'gm',
            
            # Core mechanics
            'hitpoints', 'hp', 'ac', 'xp', 'proficiency', 'initiative', 'multiclass', 
            'subclass', 'feat', 'feats', 'cantrip', 'cantrips', 'spellcasting',
            
            # Abilities and stats
            'str', 'dex', 'con', 'int', 'wis', 'cha', 'strength', 'dexterity',
            'constitution', 'intelligence', 'wisdom', 'charisma',
            
            # Classes
            'barbarian', 'bard', 'cleric', 'druid', 'fighter', 'monk', 'paladin',
            'ranger', 'rogue', 'sorcerer', 'warlock', 'wizard',
            
            # Races
            'dwarf', 'dwarves', 'elf', 'elves', 'halfling', 'human', 'dragonborn',
            'gnome', 'tiefling', 'half-elf', 'half-orc', 'aasimar', 'genasi',
            
            # Equipment
            'longsword', 'shortsword', 'greatsword', 'greataxe', 'battleaxe',
            'quarterstaff', 'crossbow', 'longbow', 'shortbow', 'warhammer',
            'mace', 'dagger', 'rapier', 'shield', 'armor', 'armour', 'potion',
            
            # Other common terms
            'adventurer', 'adventurers', 'spellcaster', 'unarmored', 'roleplaying',
            'dungeon', 'monster', 'creature', 'alignment', 'skill', 'skills',
            'saving', 'save', 'attack', 'damage', 'magic', 'magical', 'spell', 'spells',
            'circumstances', 'circumstance'  # Adding the specific example
        }
        
        # Add D&D terms to our valid words
        self.valid_words = self.common_words.union(self.dnd_terms)
        
        # Common OCR error patterns
        self.error_patterns = {
            r'\bm(?:\s*)ore\b': 'more',
            r'\bw(?:\s*)ith\b': 'with',
            r'\bt(?:\s*)he\b': 'the',
            r'\ba(?:\s*)n(?:\s*)d\b': 'and',
            r'\bf(?:\s*)or\b': 'for',
            r'\by(?:\s*)ou(?:\s*)r\b': 'your',
            r'\bt(?:\s*)o\b': 'to',
            r'\bt(?:\s*)hat\b': 'that',
            r'\bo(?:\s*)f\b': 'of',
            r'\bD(?:\s*)&(?:\s*)D\b': 'D&D',
            r'\bDun(?:\s*)geo(?:\s*)ns?(?:\s*)&(?:\s*)Dra(?:\s*)go(?:\s*)ns?\b': 'Dungeons & Dragons'
        }
        
        # Word hyphenation patterns
        self.hyphenation_patterns = [
            # Match soft-hyphen followed by newlines and continuation
            r'(\w{2,})\xad\s*\n+\s*(\w{2,})',
            # Match normal hyphen followed by newlines
            r'(\w{2,})-\s*\n+\s*(\w{2,})',
            # Match space-hyphen patterns
            r'(\w{2,})\s+-\s*(\w{2,})',
        ]
        
    def _load_english_words(self) -> Set[str]:
        """Load a set of common English words."""
        # Start with a smaller set of very common words
        common_words = {
            'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'it',
            'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at', 'this',
            'but', 'his', 'by', 'from', 'they', 'we', 'say', 'her', 'she', 'or',
            'an', 'will', 'my', 'one', 'all', 'would', 'there', 'their', 'what',
            'so', 'up', 'out', 'if', 'about', 'who', 'get', 'which', 'go', 'me',
            'when', 'make', 'can', 'like', 'time', 'no', 'just', 'him', 'know',
            'take', 'people', 'into', 'year', 'your', 'good', 'some', 'could',
            'them', 'see', 'other', 'than', 'then', 'now', 'look', 'only', 'come',
            'its', 'over', 'think', 'also', 'back', 'after', 'use', 'two', 'how',
            'our', 'work', 'first', 'well', 'way', 'even', 'new', 'want', 'because',
            'any', 'these', 'give', 'day', 'most', 'us'
        }
        
        # Try to load a more comprehensive list from file if available
        try:
            word_file = 'data/resources/common_words.txt'
            with open(word_file, 'r') as f:
                for line in f:
                    word = line.strip().lower()
                    if word:
                        common_words.add(word)
            self.logger.debug(f"Loaded {len(common_words)} common words from {word_file}")
        except Exception as e:
            self.logger.warning(f"Could not load word file: {e}")
            
        return common_words
    
    def _fix_hyphenated_words(self, text: str) -> str:
        """Fix hyphenated words that were split across lines."""
        # Handle soft hyphens and regular hyphens at line breaks
        for pattern in self.hyphenation_patterns:
            def join_hyphenated(match):
                part1, part2 = match.groups()
                joined = part1 + part2
                
                # Check if the joined word is valid
                if joined.lower() in self.valid_words:
                    return joined
                
                # Try to check with a dictionary lookup if available
                corrected, confidence = self.correct_word(joined)
                if confidence > 0.9:  # Higher threshold for joining
                    return corrected
                
                # If we can't validate the joined word, keep original with a space
                return part1 + " " + part2
            
            text = re.sub(pattern, join_hyphenated, text)
        
        # Remove any remaining soft hyphens
        text = text.replace('\xad', '')
        
        return text
        
    def correct_word(self, word: str) -> Tuple[str, float]:
        """
        Correct a single word.
        
        Args:
            word: The word to correct
            
        Returns:
            A tuple containing (corrected_word, confidence)
        """
        if not word or len(word) < self.min_word_length:
            return word, 1.0
            
        # Already correct?
        word_lower = word.lower()
        if word_lower in self.valid_words:
            return word, 1.0
            
        # Check for patterns of common OCR errors
        for pattern, replacement in self.error_patterns.items():
            if re.match(pattern, word):
                return replacement, 0.95
                
        # Potential corrections based on edit distance
        candidates = []
        
        # Only try to correct if the word is not too long or short
        if 3 <= len(word) <= 20:  
            # Find similar words
            for valid_word in self.valid_words:
                # Skip words with very different lengths
                if abs(len(valid_word) - len(word)) > self.max_edit_distance:
                    continue
                    
                # Check if the starts match (faster initial filter)
                if valid_word[:2] == word_lower[:2]:
                    # Calculate edit distance
                    similarity = difflib.SequenceMatcher(None, word_lower, valid_word).ratio()
                    if similarity > 0.8:  # Threshold for similarity
                        candidates.append((valid_word, similarity))
            
            # Sort by similarity score
            candidates.sort(key=lambda x: x[1], reverse=True)
            
            # Return best match if it exists
            if candidates and candidates[0][1] >= self.min_confidence:
                # Preserve original casing if first letter is capitalized
                if word[0].isupper() and candidates[0][0][0].islower():
                    corrected = candidates[0][0].capitalize()
                else:
                    corrected = candidates[0][0]
                return corrected, candidates[0][1]
        
        # No good correction found
        return word, 1.0
    
    def correct_text(self, text: str) -> str:
        """
        Correct a piece of text, preserving formatting.
        
        Args:
            text: The text to correct
            
        Returns:
            Corrected text
        """
        if not text:
            return text
        
        # Fix hyphenated words first if enabled
        if self.fix_hyphenation:
            text = self._fix_hyphenated_words(text)
            
        # Apply pattern-based corrections
        for pattern, replacement in self.error_patterns.items():
            text = re.sub(pattern, replacement, text)
        
        # Then process word by word
        if self.aggressive_mode:
            # Split text into tokens
            tokens = []
            current_word = []
            current_non_word = []
            
            for char in text:
                if char.isalnum() or char == "'":  # Part of a word
                    if current_non_word:
                        tokens.append((''.join(current_non_word), False))
                        current_non_word = []
                    current_word.append(char)
                else:  # Non-word character
                    if current_word:
                        tokens.append((''.join(current_word), True))
                        current_word = []
                    current_non_word.append(char)
            
            # Add any remaining tokens
            if current_word:
                tokens.append((''.join(current_word), True))
            if current_non_word:
                tokens.append((''.join(current_non_word), False))
            
            # Correct each word token
            corrected_tokens = []
            for token, is_word in tokens:
                if is_word and len(token) >= self.min_word_length:
                    corrected, confidence = self.correct_word(token)
                    corrected_tokens.append(corrected if confidence >= self.min_confidence else token)
                else:
                    corrected_tokens.append(token)
            
            return ''.join(corrected_tokens)
        else:
            # Simple word-boundary-based approach
            words = re.findall(r'\b(\w+)\b', text)
            for word in words:
                if len(word) >= self.min_word_length:
                    corrected, confidence = self.correct_word(word)
                    if confidence >= self.min_confidence:
                        # Replace only complete words with word boundaries
                        text = re.sub(r'\b' + re.escape(word) + r'\b', corrected, text)
            
            return text
    
    def correct_paragraph(self, paragraph: str) -> str:
        """
        Correct a paragraph of text, with contextual awareness.
        
        Args:
            paragraph: The paragraph to correct
            
        Returns:
            Corrected paragraph
        """
        return self.correct_text(paragraph)
    
    def correct_document(self, document: List[str]) -> List[str]:
        """
        Correct an entire document represented as a list of paragraphs.
        
        Args:
            document: List of paragraphs to correct
            
        Returns:
            Corrected list of paragraphs
        """
        return [self.correct_paragraph(paragraph) for paragraph in document]
        
    def batch_correct(self, texts: List[str]) -> List[str]:
        """
        Batch correct multiple text items.
        
        Args:
            texts: List of text items to correct
            
        Returns:
            List of corrected texts
        """
        return [self.correct_text(text) for text in texts]
