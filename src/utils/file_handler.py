"""
File handling utilities for the PDF Text Extractor.
"""

import os
import json
import yaml
from pathlib import Path
from typing import Union, Dict, Any, Optional

def read_file(file_path: Union[str, Path], encoding: str = 'utf-8') -> str:
    """
    Read content from a text file.
    
    Args:
        file_path: Path to the file
        encoding: File encoding
        
    Returns:
        File content as string
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
        
    with open(file_path, 'r', encoding=encoding) as f:
        return f.read()
        
def write_file(content: str, file_path: Union[str, Path], encoding: str = 'utf-8') -> None:
    """
    Write content to a text file.
    
    Args:
        content: Content to write
        file_path: Path to the file
        encoding: File encoding
    """
    file_path = Path(file_path)
    
    # Create directory if it doesn't exist
    os.makedirs(file_path.parent, exist_ok=True)
    
    with open(file_path, 'w', encoding=encoding) as f:
        f.write(content)
        
def read_json(file_path: Union[str, Path], encoding: str = 'utf-8') -> Dict[str, Any]:
    """
    Read content from a JSON file.
    
    Args:
        file_path: Path to the file
        encoding: File encoding
        
    Returns:
        Parsed JSON content
    """
    content = read_file(file_path, encoding)
    return json.loads(content)
    
def write_json(data: Dict[str, Any], file_path: Union[str, Path], encoding: str = 'utf-8', 
               indent: int = 2) -> None:
    """
    Write data to a JSON file.
    
    Args:
        data: Data to write
        file_path: Path to the file
        encoding: File encoding
        indent: JSON indentation
    """
    content = json.dumps(data, indent=indent)
    write_file(content, file_path, encoding)
    
def read_yaml(file_path: Union[str, Path], encoding: str = 'utf-8') -> Dict[str, Any]:
    """
    Read content from a YAML file.
    
    Args:
        file_path: Path to the file
        encoding: File encoding
        
    Returns:
        Parsed YAML content
    """
    content = read_file(file_path, encoding)
    return yaml.safe_load(content)
    
def write_yaml(data: Dict[str, Any], file_path: Union[str, Path], encoding: str = 'utf-8') -> None:
    """
    Write data to a YAML file.
    
    Args:
        data: Data to write
        file_path: Path to the file
        encoding: File encoding
    """
    with open(file_path, 'w', encoding=encoding) as f:
        yaml.dump(data, f, default_flow_style=False)
