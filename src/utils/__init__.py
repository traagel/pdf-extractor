"""
PDF Text Extractor - Utilities Module

This module provides utility functions for file handling, logging,
and other common operations used throughout the application.
"""

from .logger import get_logger
from .file_handler import read_file, write_file

__all__ = ['get_logger', 'read_file', 'write_file']
