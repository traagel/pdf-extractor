"""
Schema validation for structured output formats.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass

@dataclass
class SchemaValidationResult:
    """Container for schema validation results."""
    is_valid: bool
    errors: List[str]

class SchemaValidator:
    """
    Validates structured output against predefined schemas.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        
    def validate_output(self, data: Dict[str, Any], format_type: str) -> SchemaValidationResult:
        """
        Validate output data against schema for specified format.
        
        Args:
            data: Data to validate
            format_type: Type of format (yaml, json)
            
        Returns:
            SchemaValidationResult containing validation status and errors
        """
        errors = []
        
        # Check required fields
        required_fields = ['filename', 'extraction_date', 'output_type', 'content']
        for field in required_fields:
            if field not in data:
                errors.append(f"Missing required field: {field}")
                
        # Validate field types
        if 'filename' in data and not isinstance(data['filename'], str):
            errors.append("Field 'filename' must be a string")
            
        if 'extraction_date' in data and not isinstance(data['extraction_date'], str):
            errors.append("Field 'extraction_date' must be a string")
            
        if 'output_type' in data and not isinstance(data['output_type'], str):
            errors.append("Field 'output_type' must be a string")
            
        # Content can be either a string (raw text) or a dictionary (structured content)
        if 'content' in data:
            if not isinstance(data['content'], (str, dict)):
                errors.append("Field 'content' must be either a string or a dictionary")
            
            # If it's structured content, validate its structure
            if isinstance(data['content'], dict):
                content_errors = self._validate_structured_content(data['content'])
                errors.extend(content_errors)
                
        # Additional format-specific validation
        if format_type == 'yaml':
            yaml_errors = self._validate_yaml_specific(data)
            errors.extend(yaml_errors)
        elif format_type == 'json':
            json_errors = self._validate_json_specific(data)
            errors.extend(json_errors)
            
        return SchemaValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
        
    def _validate_structured_content(self, content: Dict[str, Any]) -> List[str]:
        """Validate the structure of processed content."""
        errors = []
        
        # Check required sections
        required_sections = ['metadata', 'table_of_contents', 'chapters', 'appendices']
        for section in required_sections:
            if section not in content:
                errors.append(f"Structured content missing required section: {section}")
                
        # Validate metadata
        if 'metadata' in content:
            if not isinstance(content['metadata'], dict):
                errors.append("Metadata must be a dictionary")
            else:
                for field in ['title', 'type']:
                    if field not in content['metadata']:
                        errors.append(f"Metadata missing required field: {field}")
                        
        # Validate table of contents
        if 'table_of_contents' in content and not isinstance(content['table_of_contents'], list):
            errors.append("Table of contents must be a list")
            
        # Validate chapters
        if 'chapters' in content:
            if not isinstance(content['chapters'], list):
                errors.append("Chapters must be a list")
            else:
                for i, chapter in enumerate(content['chapters']):
                    if not isinstance(chapter, dict):
                        errors.append(f"Chapter {i+1} must be a dictionary")
                    else:
                        for field in ['number', 'title', 'sections']:
                            if field not in chapter:
                                errors.append(f"Chapter {i+1} missing required field: {field}")
                                
        # Validate appendices
        if 'appendices' in content:
            if not isinstance(content['appendices'], list):
                errors.append("Appendices must be a list")
            else:
                for i, appendix in enumerate(content['appendices']):
                    if not isinstance(appendix, dict):
                        errors.append(f"Appendix {i+1} must be a dictionary")
                    else:
                        for field in ['letter', 'title', 'content', 'sections']:
                            if field not in appendix:
                                errors.append(f"Appendix {i+1} missing required field: {field}")
                                
        return errors
        
    def _validate_yaml_specific(self, data: Dict[str, Any]) -> List[str]:
        """Additional YAML-specific validation."""
        errors = []
        
        # For PDF content, we'll escape YAML-unsafe characters rather than report them
        unsafe_chars = ['*', '&', '[', ']', '{', '}']
        for key, value in data.items():
            if isinstance(value, str):
                # Instead of reporting errors, escape the characters
                for char in unsafe_chars:
                    if char in value:
                        data[key] = value.replace(char, f'\\{char}')
                        
        return errors
        
    def _validate_json_specific(self, data: Dict[str, Any]) -> List[str]:
        """Additional JSON-specific validation."""
        errors = []
        
        # Check for JSON compatibility
        try:
            import json
            json.dumps(data)
        except TypeError as e:
            errors.append(f"Data is not JSON-serializable: {str(e)}")
            
        return errors
