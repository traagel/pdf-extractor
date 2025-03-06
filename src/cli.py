"""
Command-line interface for the PDF Text Extractor.
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Literal
import inquirer
from datetime import datetime
from tqdm import tqdm  # Import tqdm for progress bars
import time

from .extraction.pdf_extractor import PDFExtractor
from .utils.file_handler import write_yaml, write_json, write_file
from .utils.logger import get_logger
from .validation.text_validator import TextValidator
from .validation.schema_validator import SchemaValidator
from .processing.text_processor import TextProcessor
from .nlp.text_structure import TextStructureAnalyzer
from .processing.line_processor import LineProcessor
from .processing.chapter_processor import ChapterProcessor

logger = get_logger(__name__)

# Define output types
OutputType = Literal["raw", "lines", "validated", "processed", "lines_chapters"]

def get_pdf_files(directory: Union[str, Path]) -> List[Path]:
    """
    Scan a directory for PDF files.
    
    Args:
        directory: Directory to scan
        
    Returns:
        List of paths to PDF files
    """
    directory = Path(directory)
    if not directory.exists() or not directory.is_dir():
        logger.error(f"Directory does not exist: {directory}")
        return []
        
    pdf_files = list(directory.glob("**/*.pdf"))
    return sorted(pdf_files)
    
def select_pdf_file(pdf_files: List[Path]) -> Optional[Path]:
    """
    Display an interactive prompt for the user to select a PDF file.
    
    Args:
        pdf_files: List of PDF files to choose from
        
    Returns:
        Selected PDF file path or None if cancelled
    """
    if not pdf_files:
        logger.error("No PDF files found")
        return None
        
    # Format choices with relative paths for better display
    choices = [str(pdf_file) for pdf_file in pdf_files]
    
    questions = [
        inquirer.List(
            'pdf_file',
            message="Select a PDF file to process",
            choices=choices
        )
    ]
    
    try:
        answers = inquirer.prompt(questions)
        if answers and answers.get('pdf_file'):
            selected = answers['pdf_file']
            return next((pdf for pdf in pdf_files if str(pdf) == selected), None)
        return None
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        return None
        
def select_output_format() -> Optional[str]:
    """
    Display an interactive prompt for the user to select an output format.
    
    Returns:
        Selected output format or None if cancelled
    """
    formats = ['yaml', 'json', 'txt']
    
    questions = [
        inquirer.List(
            'format',
            message="Select output format",
            choices=formats
        )
    ]
    
    try:
        answers = inquirer.prompt(questions)
        return answers.get('format') if answers else None
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        return None

def select_output_type() -> Optional[OutputType]:
    """
    Display an interactive prompt for the user to select output type.
    
    Returns:
        Selected output type or None if cancelled
    """
    types = [
        ('raw', 'Raw extraction without processing'),
        ('lines', 'Split into cleaned lines'),
        ('lines_chapters', 'Split into lines and process chapters'),
        ('validated', 'Validated output with error checks'),
        ('processed', 'Fully processed with NLP corrections')
    ]
    
    questions = [
        inquirer.List(
            'type',
            message="Select output processing level",
            choices=[t[0] for t in types],
            carousel=True
        )
    ]
    
    try:
        answers = inquirer.prompt(questions)
        return answers.get('type') if answers else None
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        return None
        
def process_pdf(pdf_path: str, output_format: str, output_dir: str, output_type: str = "raw"):
    """Process PDF file."""
    logger.info(f"Extracting text from {pdf_path}")
    print(f"\nProcessing {os.path.basename(pdf_path)}...")
    
    # Initialize the variable before using it
    line_content = None
    
    # Process based on output type
    content = None
    validation_result = None
    
    # Show progress indicator for extraction
    with tqdm(desc="Extracting text", unit="pages") as pbar:
        if output_type == "lines":
            # Process into lines
            extractor = PDFExtractor(pdf_path, progress_callback=pbar.update)
            extracted_text = extractor.extract(pdf_path)
            line_processor = LineProcessor()
            line_content = line_processor.process(extracted_text)
            content = line_content
        elif output_type == "lines_chapters":
            # Process into lines first
            extractor = PDFExtractor(pdf_path, progress_callback=pbar.update)
            extracted_text = extractor.extract(pdf_path)
            line_processor = LineProcessor()
            line_content = line_processor.process(extracted_text)
            
            # Then process chapters
            chapter_processor = ChapterProcessor()
            content = {
                'lines': line_content['lines'],
                'chapters': chapter_processor.process(line_content['lines'])
            }
            content['stats'] = line_content['stats']  # Keep line stats
        elif output_type in ["validated", "processed"]:
            # Full NLP processing
            analyzer = TextStructureAnalyzer()
            content = analyzer.analyze_document(pdf_path)
        elif output_type == "lines_chapters_validation":
            extractor = PDFExtractor(pdf_path, progress_callback=pbar.update)
            extracted_text = extractor.extract(pdf_path)
            line_processor = LineProcessor()
            lines = line_processor.process(extracted_text)
            line_content = {'lines': lines['lines']}
            
            # Show progress for chapter processing
            with tqdm(desc="Processing chapters", unit="chapters") as chapter_pbar:
                # Set a timeout for chapter processing
                max_processing_time = 120  # seconds
                start_time = time.time()
                
                try:
                    chapter_processor = ChapterProcessor(progress_callback=chapter_pbar.update)
                    
                    # Process with timeout monitoring
                    content = chapter_processor.process(line_content['lines'])
                    
                    # Check if we've exceeded the timeout
                    if time.time() - start_time > max_processing_time:
                        print("\nWarning: Chapter processing took longer than expected.")
                    
                except Exception as e:
                    logger.error(f"Error during chapter processing: {str(e)}")
                    print(f"\nError processing chapters: {str(e)}")
                    content = {'chapters': [], 'validation': [], 'stats': {'total_chapters': 0}}
        else:
            raise ValueError(f"Unknown output type: {output_type}")
    
    # Add debugging point
    print("\nPreparing data for output...", flush=True)
    
    # Prepare output data with more progress indicators
    data = {
        'filename': os.path.basename(pdf_path),
        'extraction_date': datetime.now().isoformat(),
        'output_type': output_type,
        'content': content
    }
    
    # Add validation info if present
    if validation_result:
        print("Adding validation results...", flush=True)
        data['validation'] = {
            'is_valid': validation_result.is_valid,
            'issues': validation_result.issues,
            'metrics': validation_result.metrics
        }
    
    # Save output with clear progress indication
    print(f"Saving to {output_format} format...", flush=True)
    save_output(data, output_format, output_dir, pdf_path)
    print("Output saved successfully.")

    # Validation results display
    if output_type == 'lines_chapters_validation' and content.get('validation'):
        print("\nPreparing validation report...", flush=True)
        # Print validation results
        print("==================")
        
        # Limit the number of issues shown to prevent overwhelming output
        max_issues_per_section = 10
        issue_count = 0
        
        for chapter_validation in content.get('validation', []):
            chapter_num = chapter_validation['chapter_number']
            chapter_title = chapter_validation['chapter_title']
            
            # Skip chapters with no issues
            if not any([chapter_validation['main_content'], 
                      chapter_validation['subchapters'], 
                      chapter_validation['tables']]):
                continue
                
            print(f"\nChapter {chapter_num}: {chapter_title}")
            
            # Print main content issues
            if chapter_validation['main_content']:
                print("\nMain Content Issues:")
                for result in chapter_validation['main_content'][:max_issues_per_section]:
                    print(f"\nLine: {result['text'][:80]}...")
                    for issue in result['issues'][:3]:  # Limit issues per line
                        print(f"  - '{issue['word']}' might be misspelled. "
                              f"Suggestion: '{issue['suggestion']}' "
                              f"(confidence: {issue['confidence']:.2f})")
                    issue_count += 1
                    if issue_count >= max_issues_per_section:
                        print("... (more issues omitted)")
                        break
            
            # Limit the remainder of validation output similarly
            if chapter_validation['subchapters']:
                print("\nSubchapter Issues:")
                for subchapter in chapter_validation['subchapters'][:max_issues_per_section]:
                    print(f"\n  {subchapter['title']}:")
                    for result in subchapter['content'][:3]:  # Limit issues per subchapter
                        print(f"    Line: {result['text'][:80]}...")
                        for issue in result['issues'][:3]:  # Limit issues per line
                            print(f"      - '{issue['word']}' might be misspelled. "
                                  f"Suggestion: '{issue['suggestion']}' "
                                  f"(confidence: {issue['confidence']:.2f})")
                    issue_count += 1
                    if issue_count >= max_issues_per_section:
                        print("... (more issues omitted)")
                        break
            
            if chapter_validation['tables']:
                print("\nTable Issues:")
                for table in chapter_validation['tables'][:max_issues_per_section]:
                    print(f"\n  Table Type: {table['table_type']}")
                    for result in table['issues'][:3]:  # Limit issues per table
                        print(f"    Cell: {result['text'][:80]}...")
                        for issue in result['issues'][:3]:  # Limit issues per cell
                            print(f"      - '{issue['word']}' might be misspelled. "
                                  f"Suggestion: '{issue['suggestion']}' "
                                  f"(confidence: {issue['confidence']:.2f})")
                    issue_count += 1
                    if issue_count >= max_issues_per_section:
                        print("... (more issues omitted)")
                        break

def save_output(data: Dict, output_format: str, output_dir: Path, pdf_path: Path) -> None:
    """Save processed output to file."""
    # Create output filename
    base_name = pdf_path.stem
    output_subdir = output_dir / data['output_type']
    os.makedirs(output_subdir, exist_ok=True)
    
    print(f"Writing to {base_name}.{output_format}...", flush=True)
    
    try:
        if output_format == 'yaml':
            output_file = output_subdir / f"{base_name}.yaml"
            write_yaml(data, output_file)
        elif output_format == 'json':
            output_file = output_subdir / f"{base_name}.json"
            write_json(data, output_file)
        else:  # txt
            output_file = output_subdir / f"{base_name}.txt"
            write_file(data['content'], output_file)
        
        logger.info(f"Output saved to {output_file}")
        print(f"Successfully saved to {output_file}")
    except Exception as e:
        logger.error(f"Error saving output: {str(e)}")
        print(f"ERROR: Failed to save output: {str(e)}")

def main():
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description="PDF Text Extractor CLI")
    
    parser.add_argument(
        "--input-dir", 
        type=str,
        default="data/input",
        help="Directory containing PDF files (default: data/input)"
    )
    
    parser.add_argument(
        "--output-dir", 
        type=str,
        default="data/output",
        help="Directory to save output files (default: data/output)"
    )
    
    parser.add_argument(
        "--format", 
        type=str,
        choices=["yaml", "json", "txt"],
        help="Output format (if not specified, will prompt)"
    )
    
    parser.add_argument(
        "--file", 
        type=str,
        help="Specific PDF file to process (if not specified, will show selection)"
    )
    
    parser.add_argument(
        "--type",
        type=str,
        choices=["raw", "lines", "validated", "processed", "lines_chapters", "lines_chapters_validation"],
        default="lines_chapters",
        help="Level of processing to apply (default: lines_chapters)"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    
    args = parser.parse_args()
    
    # Create directories if they don't exist
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    
    # Create output subdirectories
    for subdir in ["raw", "lines", "validated", "processed"]:
        os.makedirs(output_dir / subdir, exist_ok=True)
    
    # Get PDF files
    if args.file:
        pdf_path = Path(args.file)
        if not pdf_path.exists():
            logger.error(f"File not found: {pdf_path}")
            return 1
        pdf_files = [pdf_path]
    else:
        pdf_files = get_pdf_files(input_dir)
        if not pdf_files:
            logger.error(f"No PDF files found in {input_dir}")
            return 1
    
    # Select PDF file if not specified
    if args.file:
        selected_pdf = Path(args.file)
    else:
        selected_pdf = select_pdf_file(pdf_files)
        if not selected_pdf:
            logger.error("No PDF file selected")
            return 1
    
    # Select output format if not specified
    if args.format:
        output_format = args.format
    else:
        output_format = select_output_format()
        if not output_format:
            logger.error("No output format selected")
            return 1
            
    # Select output type if using interactive mode
    output_type = args.type
    if args.file is None and args.format is None:
        selected_type = select_output_type()
        if selected_type:
            output_type = selected_type
    
    # Enable debug logging if requested
    if args.debug:
        from .utils.logger import enable_debug_logging
        enable_debug_logging()
        logger.debug("Debug logging enabled")
    
    # Process the PDF
    process_pdf(selected_pdf, output_format, output_dir, output_type)
    return 0

if __name__ == "__main__":
    sys.exit(main()) 