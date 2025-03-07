"""
Advanced NLP-based validator for markdown content using language models and grammar checking libraries.
"""

import re
import markdown
from typing import Dict, List, Tuple, Optional, Set, Any
from dataclasses import dataclass
from bs4 import BeautifulSoup
import spacy
from spacy.tokens import Doc, Span
import language_tool_python
from contextlib import contextmanager
import time
import threading
import queue
import os

from ..utils.logger import get_logger

@dataclass
class TextError:
    """Represents an error found in text content."""
    line_num: int
    column: int
    text: str
    suggestion: str
    confidence: float
    context: str
    error_type: str
    rule_id: Optional[str] = None
    description: Optional[str] = None

class AdvancedTextValidator:
    """
    Advanced text validator that uses NLP libraries for more comprehensive error detection.
    
    This validator leverages language models and grammar checking libraries to find
    spelling errors, grammar issues, and stylistic problems in text.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize the advanced validator with configuration options."""
        self.config = config or {}
        self.logger = get_logger(__name__)
        
        # Configure parameters
        self.min_confidence = self.config.get('min_confidence', 0.7)
        self.ignore_code_blocks = self.config.get('ignore_code_blocks', True)
        self.max_errors_per_section = self.config.get('max_errors_per_section', 20)
        self.timeout = self.config.get('timeout', 30)  # seconds per validation operation
        
        # Initialize NLP components
        self._initialize_nlp()
        
        # Load D&D-specific terminology
        self.dnd_terms = self._load_dnd_terms()
        
    def _initialize_nlp(self):
        """Initialize NLP components."""
        self.logger.info("Initializing NLP components...")
        print("Initializing NLP components...")
        
        # Initialize LanguageTool for grammar checking
        try:
            self.language_tool = language_tool_python.LanguageTool('en-US')
            self.logger.info("LanguageTool initialized")
            print("LanguageTool initialized")
        except Exception as e:
            self.logger.error(f"Error initializing LanguageTool: {e}")
            self.language_tool = None
            
        # Initialize OCR pattern detection
        self._initialize_ocr_patterns()
        
        # Initialize spaCy for linguistic analysis
        try:
            # Try to load a larger model if available, fall back to smaller one
            try:
                self.nlp = spacy.load("en_core_web_md")
            except:
                self.nlp = spacy.load("en_core_web_sm")
            
            # Increase max_length to handle larger texts
            self.nlp.max_length = 1500000  # Still keep a reasonable limit
            
            self.logger.info(f"spaCy initialized with model: {self.nlp.meta['name']}")
            print(f"spaCy initialized with model: {self.nlp.meta['name']}")
        except Exception as e:
            self.logger.error(f"Error initializing spaCy: {e}")
            self.nlp = None
    
    def _initialize_ocr_patterns(self):
        """Initialize patterns for OCR error detection."""
        # Common spacing errors (split words)
        self.split_word_patterns = [
            # Common D&D terms with spaces - put these first for higher priority
            (r'w\s+eapon', 'weapon', 0.95),
            (r'ar\s+mor', 'armor', 0.95),
            (r'c\s+haracter', 'character', 0.95),
            (r's\s+pell', 'spell', 0.95),
            (r'm\s+agic', 'magic', 0.95),
            (r'a\s+bility', 'ability', 0.95),
            (r's\s+kill', 'skill', 0.95),
            (r'c\s+lass', 'class', 0.95),
            (r'r\s+ace', 'race', 0.95),
            (r'd\s+amage', 'damage', 0.95),
            (r'c\s+reature', 'creature', 0.95),
            (r'a\s+ttack', 'attack', 0.95),
            
            # Split pronouns with space
            (r'you\s+r\b', 'your', 0.95),
            (r'you\s+rs\b', 'yours', 0.95),
            (r'o\s+ur\b', 'our', 0.95),
            (r'w\s+e\b', 'we', 0.95),
            (r'th\s+ey\b', 'they', 0.95),
            (r'th\s+em\b', 'them', 0.95),
            (r'th\s+eir\b', 'their', 0.95),
            
            # Common word breaks at the end of lines
            (r'(\w{2,})-\s*\n\s*(\w{2,})', r'\1\2', 0.9),
            
            # Additional common OCR spacing errors
            (r'som\s+e', 'some', 0.95),
            (r'wh\s+at', 'what', 0.95),
            (r'th\s+at', 'that', 0.95),
            (r'th\s+is', 'this', 0.95),
            (r'th\s+an', 'than', 0.95),
            (r'wh\s+en', 'when', 0.95),
            (r'wh\s+ere', 'where', 0.95),
            (r'th\s+ere', 'there', 0.95),
        ]
        
        # More general pattern for any word split by a space - added as a separate list
        # so we can filter results differently
        self.general_split_patterns = [
            (r'\b(\w{2,})\s+(\w{2,})\b', lambda m: m.group(1) + m.group(2), 0.85),
        ]
        
        # Add pattern for joined words (missing spaces)
        self.joined_word_patterns = [
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
        ]
        
        # Words to ignore in split word detection (false positives)
        self.ignore_words = [
            # Dates and numbers
            r'\d{2,4}\s+\d{2,4}',  # Like 2025 03 or 07 11
            r'\d+\s+\w+\s+\d+',   # Like 7 Mar 2025
            
            # Common proper nouns that might contain spaces
            r'Dungeons\s+Dragons',
            r'Dungeon\s+Master',
            r'Players\s+Handbook',
            
            # Headings and titles that might have spaces
            r'Chapter\s+\d+',
            r'Table\s+\d+',
            r'Figure\s+\d+',
            r'Part\s+\d+',
            r'Appendix\s+\w+',
            r'Table\s+of',  # Table of Contents
            r'Index\s+of',
            r'List\s+of',
            
            # Common phrases that should have spaces
            r'hit\s+points',
            r'armor\s+class',
            r'ability\s+score',
            r'saving\s+throw',
            r'spell\s+slot',
            r'attack\s+roll',
            r'spell\s+casting',
            r'action\s+economy',
            r'bonus\s+action',
            r'damage\s+type',
            r'damage\s+roll',
            r'ability\s+check',
            r'character\s+sheet',
            r'character\s+class',
            r'character\s+level',
            r'skill\s+check',
            r'concentration\s+check',
            
            # Common verbs with prepositions
            r'based\s+on',
            r'depends\s+on',
            r'focuses\s+on',
            r'relies\s+on',
            r'consists\s+of',
            r'made\s+of',
            r'part\s+of',
            r'type\s+of',
            r'kind\s+of',
            r'sort\s+of',
            r'bunch\s+of',
            r'group\s+of',
            r'set\s+of',
            r'lot\s+of',
            r'full\s+of',
            r'capable\s+of',
            
            # Common document phrases
            r'Table\s+of\s+Contents',
            r'Extracted\s+on',
            r'Created\s+by',
            r'Written\s+by',
            r'Edited\s+by',
            r'Published\s+by',
            r'Illustrated\s+by',
        ]
    
    def _load_dnd_terms(self) -> Set[str]:
        """Load D&D-specific terminology."""
        terms = {
            # Basic D&D terms
            'dungeons', 'dragons', 'd&d', 'dnd', 'dm', 'pc', 'npc', 'gm',
            
            # Core rulebooks
            "player's handbook", "dungeon master's guide", "monster manual",
            
            # Classes
            'barbarian', 'bard', 'cleric', 'druid', 'fighter', 'monk', 'paladin',
            'ranger', 'rogue', 'sorcerer', 'warlock', 'wizard', 'artificer',
            
            # Races
            'dwarf', 'elf', 'halfling', 'human', 'dragonborn', 'gnome', 'half-elf',
            'half-orc', 'tiefling', 'aasimar', 'genasi', 'goliath', 'firbolg',
            
            # Abilities
            'strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma',
            'str', 'dex', 'con', 'int', 'wis', 'cha',
            
            # Common game terms
            'initiative', 'proficiency', 'spell slot', 'cantrip', 'saving throw',
            'attack roll', 'armor class', 'hit points', 'temporary hit points',
            'short rest', 'long rest', 'bonus action', 'reaction', 'concentration',
            
            # Additional terms
            'multiclass', 'subclass', 'alignment', 'background', 'feat', 'skill check',
            'ability check', 'spell save dc', 'spell attack modifier', 'spellcasting',
            'magic item', 'attunement', 'inspiration', 'exhaustion', 'condition'
        }
        
        # Add uppercase and title case versions
        expanded_terms = set()
        for term in terms:
            expanded_terms.add(term)
            expanded_terms.add(term.upper())
            expanded_terms.add(term.title())
            
        return expanded_terms
        
    @contextmanager
    def _timeout_context(self, seconds):
        """Context manager for operation timeout."""
        result_queue = queue.Queue()
        exception_queue = queue.Queue()
        
        def target(result_queue, exception_queue):
            try:
                yield
            except Exception as e:
                exception_queue.put(e)
            
        timer = threading.Timer(seconds, lambda: exception_queue.put(TimeoutError(f"Operation timed out after {seconds} seconds")))
        timer.start()
        
        try:
            yield result_queue
        except Exception as e:
            exception_queue.put(e)
        finally:
            timer.cancel()
            
        if not exception_queue.empty():
            raise exception_queue.get()
    
    def _clean_markdown(self, content: str) -> str:
        """Convert markdown to plain text for validation."""
        # Convert markdown to HTML
        html = markdown.markdown(content)
        
        # Convert HTML to plain text
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text()
        
        return text
    
    def _extract_sections(self, lines: List[str]) -> List[Dict]:
        """Extract sections from markdown content."""
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
        """Get line and column for a position in the text."""
        # Get the text up to this position
        text_up_to_pos = text[:pos]
        
        # Count newlines to determine the line
        lines = text_up_to_pos.split('\n')
        line_index = len(lines) - 1 + line_offset
        
        # Column is the length of the last line
        column = len(lines[-1])
        
        return line_index, column
    
    def _check_grammar(self, text: str, line_offset: int, all_lines: List[str]) -> List[TextError]:
        """
        Check grammar and spelling in text.
        
        Args:
            text: Text to check
            line_offset: Line offset from the start of the document
            all_lines: All lines of the markdown content
            
        Returns:
            List of TextError objects
        """
        errors = []
        
        # Skip if no language tool
        if not self.language_tool:
            return errors
        
        # Skip if text is too short
        if len(text.strip()) < 5:
            return errors
        
        # Limit text size for language tool
        max_text_size = 100000
        if len(text) > max_text_size:
            self.logger.warning(f"Text too large for grammar check ({len(text)} chars), using first {max_text_size} chars")
            text = text[:max_text_size]
        
        try:
            with self._timeout_context(self.timeout):
                # Check text with LanguageTool
                matches = self.language_tool.check(text)
                
                # Filter matches by confidence and category
                filtered_matches = []
                for match in matches:
                    # Handle missing attributes safely
                    try:
                        # Get category and rule_id with fallbacks
                        category = (
                            match.category.upper() 
                            if hasattr(match, 'category') and match.category 
                            else 'UNKNOWN'
                        )
                        
                        rule_id = (
                            match.ruleId 
                            if hasattr(match, 'ruleId') 
                            else (match.rule_id if hasattr(match, 'rule_id') else 'UNKNOWN')
                        )
                        
                        # Skip matches in disabled categories
                        if hasattr(self, 'disabled_categories') and category in self.disabled_categories:
                            continue
                        
                        # Convert confidence (higher is better)
                        is_spelling = (
                            (hasattr(match, 'ruleId') and str(match.ruleId).startswith("MORFOLOGIK_")) or
                            (hasattr(match, 'rule_id') and str(match.rule_id).startswith("MORFOLOGIK_"))
                        )
                        confidence = 0.9 if is_spelling else 0.7
                        
                        if confidence < self.min_confidence:
                            continue
                        
                        # Store additional info for later use
                        match._rule_id = rule_id
                        match._category = category
                        match._confidence = confidence
                        
                        filtered_matches.append(match)
                    except Exception as e:
                        self.logger.debug(f"Error processing match: {e}")
                        continue
                        
                # Convert matches to TextError objects
                for match in filtered_matches:
                    try:
                        # Get offset and error length
                        offset = match.offset if hasattr(match, 'offset') else 0
                        error_length = (
                            match.errorLength if hasattr(match, 'errorLength') 
                            else len(match.context) if hasattr(match, 'context') else 1
                        )
                        
                        # Calculate line and column
                        line_index, column = self._get_position(text, offset, line_offset)
                        
                        # Get context (the line containing the error)
                        context = all_lines[line_index] if 0 <= line_index < len(all_lines) else ""
                        
                        # Get text and suggested replacement
                        error_text = text[offset:offset + error_length] if offset + error_length <= len(text) else "?"
                        
                        # Get replacements in a safe way
                        if hasattr(match, 'replacements') and match.replacements:
                            suggestion = match.replacements[0]
                        else:
                            suggestion = ""
                        
                        # Get message/description
                        description = match.message if hasattr(match, 'message') else "Grammar or spelling issue"
                        
                        # Create error object
                        error = TextError(
                            line_num=line_index + 1,  # 1-based line numbers
                            column=column + 1,        # 1-based column numbers
                            text=error_text,
                            suggestion=suggestion,
                            confidence=match._confidence,
                            context=context,
                            error_type='spelling' if match._rule_id.startswith("MORFOLOGIK_") else 'grammar',
                            rule_id=match._rule_id,
                            description=description
                        )
                        errors.append(error)
                    except Exception as e:
                        self.logger.debug(f"Error creating TextError: {e}")
                        continue
        
        except TimeoutError:
            self.logger.warning(f"Grammar check timed out after {self.timeout} seconds")
        except Exception as e:
            self.logger.error(f"Error in grammar check: {e}")
            print(f"Error in grammar check: {e}")
        
        return errors
    
    def _check_text_coherence(self, text: str, line_offset: int, all_lines: List[str]) -> List[TextError]:
        """
        Check text coherence using spaCy.
        
        Args:
            text: Text to check
            line_offset: Line offset from the start of the document
            all_lines: All lines of the markdown content
            
        Returns:
            List of TextError objects
        """
        errors = []
        
        # Skip if no spaCy
        if not self.nlp:
            return errors
        
        # Skip if text is too short
        if len(text.strip()) < 20:
            return errors
        
        # Limit text size for spaCy processing
        max_text_size = 100000
        if len(text) > max_text_size:
            self.logger.warning(f"Text too large for coherence check ({len(text)} chars), using first {max_text_size} chars")
            text = text[:max_text_size]
        
        try:
            with self._timeout_context(self.timeout):
                doc = self.nlp(text)
                
                # Check for subject-verb agreement issues
                for sent in doc.sents:
                    # Skip short sentences
                    if len(sent) < 4:
                        continue
                        
                    # Find subjects and their verbs
                    for token in sent:
                        if token.dep_ == "nsubj" and token.head.pos_ == "VERB":
                            subject = token
                            verb = token.head
                            
                            # Check agreement (very simplified)
                            if (subject.text.lower() in ["i", "you", "we", "they"] and 
                                verb.text.lower().endswith("s") and
                                not verb.text.lower() in ["is", "was"]):
                                
                                # Get position in text
                                verb_pos = verb.idx
                                line_index, column = self._get_position(text, verb_pos, line_offset)
                                
                                # Get context
                                context = all_lines[line_index] if 0 <= line_index < len(all_lines) else ""
                                
                                # Create error
                                error = TextError(
                                    line_num=line_index + 1,
                                    column=column + 1,
                                    text=verb.text,
                                    suggestion=f"Check subject-verb agreement with '{subject.text}'",
                                    confidence=0.7,
                                    context=context,
                                    error_type='grammar',
                                    description=f"Possible subject-verb agreement issue between '{subject.text}' and '{verb.text}'"
                                )
                                errors.append(error)
                
        except TimeoutError:
            self.logger.warning(f"Text coherence check timed out after {self.timeout} seconds")
        except Exception as e:
            self.logger.error(f"Error in text coherence check: {e}")
        
        return errors
    
    def _check_split_words(self, text: str, line_offset: int, all_lines: List[str]) -> List[TextError]:
        """
        Check for split words (OCR errors where spaces are inserted in words).
        
        Args:
            text: Text to check
            line_offset: Line offset from the start of the document
            all_lines: All lines of the markdown content
            
        Returns:
            List of TextError objects
        """
        errors = []
        
        # Skip if text is too short
        if len(text.strip()) < 5:
            return errors
        
        # Process specific patterns first (higher confidence)
        for pattern, replacement, confidence in self.split_word_patterns:
            # Find all occurrences of the pattern
            for match in re.finditer(pattern, text, re.IGNORECASE):
                # Skip if confidence is below threshold
                if confidence < self.min_confidence:
                    continue
                    
                # Get the matched text
                matched_text = match.group(0)
                
                # Skip if this matches any of our ignore patterns
                if any(re.search(ignore_pat, matched_text, re.IGNORECASE) for ignore_pat in self.ignore_words):
                    continue
                    
                # Calculate line and column
                line_index, column = self._get_position(text, match.start(), line_offset)
                
                # Get context (the line containing the error)
                context = all_lines[line_index] if 0 <= line_index < len(all_lines) else ""
                
                # Create error object
                error = TextError(
                    line_num=line_index + 1,  # 1-based line numbers
                    column=column + 1,        # 1-based column numbers
                    text=matched_text,
                    suggestion=replacement if isinstance(replacement, str) else replacement(match),
                    confidence=confidence,
                    context=context,
                    error_type='split_word',
                    description=f"Split word detected: '{matched_text}' → '{replacement if isinstance(replacement, str) else replacement(match)}'"
                )
                errors.append(error)
        
        # Now handle general split word pattern with extra validation
        for pattern, replacement_fn, confidence in self.general_split_patterns:
            # Find all occurrences of the pattern
            for match in re.finditer(pattern, text, re.IGNORECASE):
                # Skip if confidence is below threshold
                if confidence < self.min_confidence:
                    continue
                    
                # Get the matched text
                matched_text = match.group(0)
                
                # Generate suggested replacement
                if callable(replacement_fn):
                    replacement = replacement_fn(match)
                else:
                    replacement = replacement_fn
                    
                # Skip known false positives
                if any(re.search(ignore_pat, matched_text, re.IGNORECASE) for ignore_pat in self.ignore_words):
                    continue
                    
                # Skip words with numbers like dates
                if re.search(r'\d', matched_text):
                    continue
                    
                # Skip words with proper formatting like "Chapter 5"
                if re.match(r'[A-Z][a-z]+\s+\d+', matched_text):
                    continue
                    
                # Skip multi-word proper names
                if re.match(r'[A-Z][a-z]+\s+[A-Z][a-z]+', matched_text):
                    continue
                
                # Skip common prepositions
                prepositions = ['of', 'on', 'in', 'at', 'by', 'for', 'with', 'to', 'from']
                if any(matched_text.lower().endswith(f" {prep}") for prep in prepositions):
                    continue
                
                # Skip common conjunctions
                conjunctions = ['and', 'or', 'but', 'nor', 'yet', 'so']
                if any(matched_text.lower().endswith(f" {conj}") for conj in conjunctions):
                    continue
                
                # Skip if it looks like a sentence boundary (first word capitalized)
                words = matched_text.split()
                if len(words) == 2 and words[1][0].isupper():
                    continue
                
                # Calculate line and column
                line_index, column = self._get_position(text, match.start(), line_offset)
                
                # Get context (the line containing the error)
                context = all_lines[line_index] if 0 <= line_index < len(all_lines) else ""
                
                # Create error object
                error = TextError(
                    line_num=line_index + 1,  # 1-based line numbers
                    column=column + 1,        # 1-based column numbers
                    text=matched_text,
                    suggestion=replacement,
                    confidence=confidence,
                    context=context,
                    error_type='split_word',
                    description=f"Split word detected: '{matched_text}' → '{replacement}'"
                )
                errors.append(error)
        
        return errors

    def _check_joined_words(self, text: str, line_offset: int, all_lines: List[str]) -> List[TextError]:
        """
        Check for joined words (OCR errors where spaces are missing between words).
        
        Args:
            text: Text to check
            line_offset: Line offset from the start of the document
            all_lines: All lines of the markdown content
            
        Returns:
            List of TextError objects
        """
        errors = []
        
        # Skip if text is too short
        if len(text.strip()) < 5:
            return errors
        
        # Check each pattern
        for pattern, replacement, confidence in self.joined_word_patterns:
            # Find all occurrences of the pattern
            for match in re.finditer(pattern, text, re.IGNORECASE):
                # Skip if confidence is below threshold
                if confidence < self.min_confidence:
                    continue
                    
                # Get the matched text
                matched_text = match.group(0)
                
                # Calculate line and column
                line_index, column = self._get_position(text, match.start(), line_offset)
                
                # Get context (the line containing the error)
                context = all_lines[line_index] if 0 <= line_index < len(all_lines) else ""
                
                # Create error object
                error = TextError(
                    line_num=line_index + 1,  # 1-based line numbers
                    column=column + 1,        # 1-based column numbers
                    text=matched_text,
                    suggestion=replacement,
                    confidence=confidence,
                    context=context,
                    error_type='joined_word',
                    description=f"Joined word detected: '{matched_text}' → '{replacement}'"
                )
                errors.append(error)
        
        return errors
    
    def validate_text(self, content: str) -> List[TextError]:
        """
        Validate text content to detect errors.
        
        Args:
            content: Text content to validate
            
        Returns:
            List of TextError objects
        """
        self.logger.debug("Validating text content...")
        
        # Get enabled validation types
        enabled_validations = self.config.get('enabled_validations', ['split_word', 'joined_word', 'grammar', 'coherence'])
        
        # Split content into lines for better error reporting
        lines = content.split('\n')
        
        # Extract sections to process (skip code blocks if configured)
        sections = self._extract_sections(lines)
        
        # Validate each section
        errors = []
        for section in sections:
            # Skip code blocks
            if section["type"] == "code" and self.ignore_code_blocks:
                continue
                
            # Join lines in this section
            text = "\n".join(section["text"])
            line_offset = section["start_line"]
            
            section_errors = []
            
            # Detect OCR-specific errors (split and joined words)
            if 'split_word' in enabled_validations:
                split_word_errors = self._check_split_words(text, line_offset, lines)
                section_errors.extend(split_word_errors)
                
            if 'joined_word' in enabled_validations:
                joined_word_errors = self._check_joined_words(text, line_offset, lines)
                section_errors.extend(joined_word_errors)
            
            # Check grammar and spelling (if enabled)
            if 'grammar' in enabled_validations:
                grammar_errors = self._check_grammar(text, line_offset, lines)
                section_errors.extend(grammar_errors)
            
            # Check text coherence (if enabled)
            if 'coherence' in enabled_validations:
                coherence_errors = self._check_text_coherence(text, line_offset, lines)
                section_errors.extend(coherence_errors)
            
            # Limit number of errors per section
            errors.extend(section_errors[:self.max_errors_per_section])
            
            # Add an indication if errors were truncated
            if len(section_errors) > self.max_errors_per_section:
                self.logger.debug(f"Truncated {len(section_errors) - self.max_errors_per_section} errors in section")
        
        self.logger.debug(f"Found {len(errors)} errors in text content")
        return errors
    
    def validate_markdown(self, content: str) -> List[TextError]:
        """
        Validate markdown content to detect errors.
        
        Args:
            content: Markdown content to validate
            
        Returns:
            List of TextError objects
        """
        # Clean markdown first to get plain text
        clean_content = self._clean_markdown(content)
        
        # Then validate the text
        return self.validate_text(clean_content)
    
    def format_errors(self, errors: List[TextError], show_context: bool = True) -> str:
        """
        Format errors for display.
        
        Args:
            errors: List of TextError objects
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
            
            # Include rule ID and description if available
            rule_info = ""
            if error.rule_id:
                rule_info = f" [{error.rule_id}]"
                
            suggestion_text = f"→ '{error.suggestion}'" if error.suggestion else ""
            
            report.append(f"{i}. {type_label}{rule_info} Line {error.line_num}, Col {error.column}: '{error.text}' {suggestion_text} ({error.confidence:.2f})")
            
            # Add description if available
            if error.description:
                report.append(f"   Note: {error.description}")
                
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
            
            # Split content into chapters
            chapters = self._split_into_chapters(content)
            self.logger.info(f"Split markdown into {len(chapters)} chapters")
            print(f"Processing document in {len(chapters)} chapters...")
            
            # Validate each chapter separately
            all_errors = []
            for i, chapter in enumerate(chapters, 1):
                print(f"Processing chapter {i}/{len(chapters)}...")
                try:
                    chapter_errors = self.validate_markdown(chapter)
                    all_errors.extend(chapter_errors)
                    print(f"  Found {len(chapter_errors)} issues in chapter {i}")
                except Exception as e:
                    self.logger.error(f"Error validating chapter {i}: {e}")
                    print(f"  Error in chapter {i}: {e}")
            
            # Format and save report
            report = self.format_errors(all_errors)
            
            if output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(report)
                self.logger.info(f"Validation report written to {output_file}")
            
            return report
            
        except Exception as e:
            self.logger.error(f"Error validating markdown file: {e}")
            return f"Error validating markdown file: {e}"
    
    def _split_into_chapters(self, content: str) -> List[str]:
        """
        Split markdown content into chapters based on heading patterns.
        
        Args:
            content: The full markdown content
            
        Returns:
            List of chapter contents as strings
        """
        # Split on headings (# or ## at start of line)
        lines = content.split("\n")
        
        # Detect chapter breaks (level 1 or 2 headings)
        chapter_breaks = []
        heading_pattern = re.compile(r"^#{1,2}\s+")
        
        for i, line in enumerate(lines):
            if heading_pattern.match(line):
                chapter_breaks.append(i)
        
        # If no chapters detected or only one heading, use a different approach
        if len(chapter_breaks) <= 1:
            # Try to split into roughly equal chunks of at most 50K characters
            max_chunk_size = 50000
            if len(content) > max_chunk_size:
                chunks = []
                current_chunk = []
                current_size = 0
                
                for line in lines:
                    line_size = len(line) + 1  # +1 for newline
                    if current_size + line_size > max_chunk_size and current_chunk:
                        chunks.append("\n".join(current_chunk))
                        current_chunk = [line]
                        current_size = line_size
                    else:
                        current_chunk.append(line)
                        current_size += line_size
                
                if current_chunk:
                    chunks.append("\n".join(current_chunk))
                
                return chunks
            
            # If it's small enough, return as single chapter
            return [content]
        
        # Extract chapters based on detected breaks
        chapters = []
        for i in range(len(chapter_breaks)):
            start_idx = chapter_breaks[i]
            end_idx = chapter_breaks[i+1] if i < len(chapter_breaks)-1 else len(lines)
            chapter_content = "\n".join(lines[start_idx:end_idx])
            chapters.append(chapter_content)
        
        # If the document has content before the first heading, include it as a chapter
        if chapter_breaks[0] > 0:
            first_part = "\n".join(lines[:chapter_breaks[0]])
            chapters.insert(0, first_part)
        
        return chapters
    
    def fix_errors_in_file(self, input_file: str, output_file: Optional[str] = None, 
                         min_confidence: float = 0.9, types_to_fix: Optional[List[str]] = None) -> Tuple[str, int]:
        """
        Fix detected errors in a markdown file and write the corrected version.
        
        Args:
            input_file: Path to the input markdown file
            output_file: Path to write the corrected file (if None, overwrites input)
            min_confidence: Minimum confidence threshold for applying fixes
            types_to_fix: Types of errors to fix (e.g., ['split_word', 'joined_word'])
            
        Returns:
            Tuple of (report of changes, number of changes made)
        """
        # Use default output file if not specified
        if not output_file:
            output_file = input_file
        
        # Use default types if not specified
        if not types_to_fix:
            types_to_fix = ['split_word', 'joined_word']
        
        try:
            # Read input file
            with open(input_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Split content into chapters
            chapters = self._split_into_chapters(content)
            self.logger.info(f"Split markdown into {len(chapters)} chapters for fixing")
            print(f"Processing document in {len(chapters)} chapters...")
            
            # Detect errors in each chapter and collect fixes
            all_fixes = []
            for i, chapter in enumerate(chapters, 1):
                print(f"Processing chapter {i}/{len(chapters)}...")
                
                # Get chapter offset in the full content
                if i == 1:
                    chapter_offset = 0
                else:
                    chapter_offset = content.find(chapter[:100])  # Use first 100 chars as anchor
                
                try:
                    # Validate chapter to find errors
                    chapter_errors = self.validate_markdown(chapter)
                    
                    # Filter errors by type and confidence
                    filtered_errors = [
                        err for err in chapter_errors 
                        if err.error_type in types_to_fix and err.confidence >= min_confidence
                    ]
                    
                    # Convert errors to fixes with adjusted positions
                    for error in filtered_errors:
                        # Calculate global position in the full content
                        line_in_chapter = error.line_num - 1
                        chapter_lines = chapter.split('\n')
                        
                        # Find character offset within the chapter
                        char_offset = sum(len(line) + 1 for line in chapter_lines[:line_in_chapter])
                        char_offset += error.column - 1  # -1 because column is 1-based
                        
                        # Calculate global position
                        global_pos = chapter_offset + char_offset
                        
                        # Add to fixes
                        all_fixes.append({
                            'start': global_pos,
                            'end': global_pos + len(error.text),
                            'original': error.text,
                            'replacement': error.suggestion,
                            'confidence': error.confidence,
                            'type': error.error_type
                        })
                    
                    print(f"  Found {len(filtered_errors)} fixable issues in chapter {i}")
                except Exception as e:
                    self.logger.error(f"Error processing fixes for chapter {i}: {e}")
                    print(f"  Error in chapter {i}: {e}")
            
            # Sort fixes in reverse order (from end to beginning) to avoid position shifts
            all_fixes.sort(key=lambda x: x['start'], reverse=True)
            
            # Apply fixes to content
            fixed_content = content
            num_applied = 0
            for fix in all_fixes:
                # Verify the text at this position matches what we expect
                text_at_pos = fixed_content[fix['start']:fix['end']]
                if text_at_pos == fix['original']:
                    before = fixed_content[:fix['start']]
                    after = fixed_content[fix['end']:]
                    fixed_content = before + fix['replacement'] + after
                    num_applied += 1
                else:
                    self.logger.warning(
                        f"Skipping fix: expected '{fix['original']}' but found '{text_at_pos}'"
                    )
            
            # Write output file
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(fixed_content)
            
            # Generate report
            fix_types = {}
            for fix in all_fixes[:num_applied]:  # Only count applied fixes
                fix_type = fix['type']
                if fix_type not in fix_types:
                    fix_types[fix_type] = 0
                fix_types[fix_type] += 1
            
            report_lines = []
            report_lines.append(f"Applied {num_applied} fixes to {os.path.basename(input_file)}")
            report_lines.append("")
            
            for fix_type, count in fix_types.items():
                report_lines.append(f"- Fixed {count} {fix_type} issues")
            
            report_lines.append("")
            report_lines.append(f"Corrected file saved to: {output_file}")
            
            return "\n".join(report_lines), num_applied
            
        except Exception as e:
            self.logger.error(f"Error fixing file: {e}")
            return f"Error fixing file: {e}", 0 