"""
Main entry point for the PDF Text Extractor.
"""

import sys
import argparse
import os
from pathlib import Path

from .cli import main as cli_main, process_pdf
from .markdown_convert import main as md_convert_main
from .utils.logger import get_logger
from datetime import datetime

logger = get_logger(__name__)

def process_pdf_command():
    """Process a PDF and optionally convert to markdown."""
    parser = argparse.ArgumentParser(description="Process PDF and convert to Markdown")
    
    parser.add_argument(
        "pdf_path",
        help="Path to the PDF file to process"
    )
    
    parser.add_argument(
        "-o", "--output",
        help="Path to save Markdown output (default: same name with .md extension)"
    )
    
    parser.add_argument(
        "--format",
        choices=["yaml", "json", "txt"],
        default="yaml",
        help="Intermediate format for processing (default: yaml)"
    )
    
    parser.add_argument(
        "--type",
        choices=["raw", "lines", "validated", "processed", "lines_chapters", "lines_chapters_validation"],
        default="processed",
        help="Level of processing to apply (default: processed)"
    )
    
    parser.add_argument(
        "--output-dir", 
        type=str,
        default="data/output",
        help="Directory to save output files (default: data/output)"
    )
    
    parser.add_argument(
        "--no-toc",
        action="store_true",
        help="Disable table of contents in Markdown output"
    )
    
    parser.add_argument(
        "--clean-text",
        choices=["none", "light", "advanced"],
        default="light",
        help="Level of text cleaning for Markdown output (none, light, advanced)"
    )
    
    parser.add_argument(
        "--to-markdown",
        action="store_true",
        help="Convert processed output to Markdown"
    )
    
    args = parser.parse_args(sys.argv[2:])
    
    # Process the PDF
    pdf_path = Path(args.pdf_path)
    output_dir = Path(args.output_dir)
    
    # Create directories
    os.makedirs(output_dir, exist_ok=True)
    for subdir in ["raw", "lines", "validated", "processed", "markdown"]:
        os.makedirs(output_dir / subdir, exist_ok=True)
    
    print(f"Processing PDF: {pdf_path}")
    result = process_pdf(pdf_path, args.format, output_dir, args.type)
    
    # Convert to markdown if requested
    if args.to_markdown:
        try:
            from .converters.markdown_converter import convert_to_markdown
            
            # Determine output path for Markdown
            if args.output:
                md_output = Path(args.output)
            else:
                md_output = output_dir / 'markdown' / (pdf_path.stem + '.md')
            
            os.makedirs(md_output.parent, exist_ok=True)
            
            # Configure Markdown options
            md_config = {
                'toc': not args.no_toc,
                'text_cleaning': args.clean_text
            }
            
            # Get the intermediate file path
            intermediate_path = None
            if args.format == 'yaml':
                intermediate_path = output_dir / args.type / (pdf_path.stem + '.yaml')
            elif args.format == 'json':
                intermediate_path = output_dir / args.type / (pdf_path.stem + '.json')
            
            if intermediate_path and intermediate_path.exists():
                print(f"\nConverting to Markdown: {intermediate_path} -> {md_output}")
                convert_to_markdown(intermediate_path, md_output, md_config)
                print(f"Markdown saved to {md_output}")
            else:
                print(f"Warning: Could not find processed file to convert to Markdown")
        except Exception as e:
            logger.error(f"Error converting to Markdown: {str(e)}")
            print(f"ERROR: Failed to convert to Markdown: {str(e)}")
    
    return 0

def main():
    """Route to appropriate subcommand."""
    if len(sys.argv) < 2:
        # If no subcommand, run the interactive CLI
        return cli_main()
    
    # Handle subcommands
    if sys.argv[1] == "convert-md":
        # Remove the "convert-md" argument and pass the rest to the Markdown converter
        sys.argv.pop(1)
        return md_convert_main()
    elif sys.argv[1] == "process-pdf":
        # Process a PDF and optionally convert to markdown
        return process_pdf_command()
    else:
        # Default to the main CLI for other commands or flags
        return cli_main()

if __name__ == "__main__":
    sys.exit(main()) 