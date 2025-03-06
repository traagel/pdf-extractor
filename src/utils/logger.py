"""
Logging utility for the PDF Text Extractor.
"""

import logging
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """
    Get a configured logger instance.
    
    Args:
        name: Name of the logger (typically __name__)
        level: Optional log level
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    if level is not None:
        logger.setLevel(level)
    elif not logger.level:
        logger.setLevel(logging.INFO)
        
    # Add console handler if logger has no handlers
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger

def enable_debug_logging():
    """Enable debug logging for all loggers."""
    # Get the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Update all existing handlers
    for handler in root_logger.handlers:
        handler.setLevel(logging.DEBUG)
    
    # Also update any existing module loggers
    for name in logging.root.manager.loggerDict:
        if name.startswith('src.nlp'):
            logging.getLogger(name).setLevel(logging.DEBUG)
