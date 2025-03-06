"""
Command-line script for converting PDF extraction output to Markdown.
"""

import sys
import os
import argparse
from pathlib import Path

from .converters.markdown_converter import convert_to_markdown
from .utils.logger import get_logger

logger = get_logger(__name__)

def main():
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description="Convert PDF extraction output to Markdown")
    
    parser.add_argument(
        "input",
        help="Path to YAML or JSON file with extracted data"
    )
    
    parser.add_argument(
        "-o", "--output",
        help="Path to save Markdown output (defaults to same name with .md extension)"
    )
    
    parser.add_argument(
        "--no-toc",
        action="store_true",
        help="Disable table of contents generation"
    )
    
    parser.add_argument(
        "--include-validation",
        action="store_true",
        help="Include validation results in output"
    )
    
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Process all YAML/JSON files in directory recursively"
    )
    
    parser.add_argument(
        "--keep-front-matter",
        action="store_true",
        help="Keep the Front Matter section in the output"
    )
    
    parser.add_argument(
        "--clean-text",
        choices=["none", "light", "advanced"],
        default="light",
        help="Level of text cleaning to apply (none, light, advanced)"
    )
    
    args = parser.parse_args()
    
    # Configure options
    config = {
        'toc': not args.no_toc,
        'include_validation': args.include_validation,
        'keep_front_matter': args.keep_front_matter,
        'text_cleaning': args.clean_text
    }
    
    input_path = Path(args.input)
    
    # Check if recursive mode on directory
    if args.recursive and input_path.is_dir():
        # Find all YAML and JSON files
        yaml_files = list(input_path.glob("**/*.yaml")) + list(input_path.glob("**/*.yml"))
        json_files = list(input_path.glob("**/*.json"))
        all_files = yaml_files + json_files
        
        if not all_files:
            logger.error(f"No YAML or JSON files found in {input_path}")
            return 1
        
        # Process each file
        for file_path in all_files:
            rel_path = file_path.relative_to(input_path)
            logger.info(f"Converting {rel_path}")
            
            # Generate output path with .md extension
            if args.output:
                output_dir = Path(args.output)
                output_file = output_dir / rel_path.with_suffix('.md')
            else:
                output_file = file_path.with_suffix('.md')
            
            try:
                convert_to_markdown(file_path, output_file, config)
            except Exception as e:
                logger.error(f"Error converting {file_path}: {str(e)}")
    else:
        # Single file mode
        if not input_path.exists():
            logger.error(f"Input file or directory not found: {input_path}")
            return 1
            
        # Generate output path
        output_file = None
        if args.output:
            output_file = Path(args.output)
        else:
            output_file = input_path.with_suffix('.md')
        
        try:
            convert_to_markdown(input_path, output_file, config)
            logger.info(f"Converted {input_path} to {output_file}")
        except Exception as e:
            logger.error(f"Error converting {input_path}: {str(e)}")
            return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 