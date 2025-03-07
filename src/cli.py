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
import glob

from .extraction.pdf_extractor import PDFExtractor
from .utils.file_handler import write_yaml, write_json, write_file
from .utils.logger import get_logger
from .validation.text_validator import TextValidator
from .validation.schema_validator import SchemaValidator
from .processing.text_processor import TextProcessor
from .nlp.text_structure import TextStructureAnalyzer
from .processing.line_processor import LineProcessor
from .processing.chapter_processor import ChapterProcessor
from .nlp.markdown_validator import MarkdownValidator

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
        ('processed', 'Fully processed with NLP corrections'),
        ('markdown', 'Process with NLP and convert to Markdown')  # New option
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
    
    # Initialize variables
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    line_content = None
    chapter_content = None
    
    # Initialize extractor with progress callback
    extractor = PDFExtractor(pdf_path, progress_callback=lambda x: None)
    
    # Build the dependency chain based on requested output type
    required_processing = []
    
    if output_type == "lines_chapters" or output_type == "lines_chapters_validation" or output_type == "processed":
        if "lines" not in required_processing:
            required_processing.append("lines")
    
    if output_type == "lines_chapters_validation" or output_type == "processed":
        if "lines_chapters" not in required_processing:
            required_processing.append("lines_chapters")
    
    # Add the requested type as the final step if not already included
    if output_type not in required_processing:
        required_processing.append(output_type)
    
    # Always extract raw text first
    print("Extracting raw text...")
    raw_text = extractor.extract(pdf_path)
    results = {
        "raw": {
            'filename': pdf_path.name,
            'extraction_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'output_type': 'raw',
            'content': raw_text
        }
    }
    
    # Save raw output for debugging
    debug_output_dir = output_dir / "debug"
    os.makedirs(debug_output_dir, exist_ok=True)
    save_output(results["raw"], output_format, debug_output_dir, pdf_path, "raw_debug")
    
    # Process each required step in order
    for step in required_processing:
        if step == "lines":
            print("Processing lines...")
            line_processor = LineProcessor()
            line_content = line_processor.process(raw_text)
            results["lines"] = {
                'filename': pdf_path.name,
                'extraction_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'output_type': 'lines',
                'content': line_content
            }
            
            # Save lines output for debugging
            save_output(results["lines"], output_format, debug_output_dir, pdf_path, "lines_debug")
            print(f"Lines debug output saved to {debug_output_dir}/lines_debug_{pdf_path.stem}.{output_format}")
        
        elif step == "lines_chapters":
            print("Processing chapters...")
            # Ensure we have line content
            if line_content is None:
                print("Warning: Line content not available, processing lines first...")
                line_processor = LineProcessor()
                line_content = line_processor.process(raw_text)
            
            chapter_processor = ChapterProcessor()
            chapter_content = chapter_processor.process(line_content['lines'])
            results["lines_chapters"] = {
                'filename': pdf_path.name,
                'extraction_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'output_type': 'lines_chapters',
                'content': chapter_content
            }
            
            # Save chapters output for debugging
            save_output(results["lines_chapters"], output_format, debug_output_dir, pdf_path, "chapters_debug")
            print(f"Chapters debug output saved to {debug_output_dir}/chapters_debug_{pdf_path.stem}.{output_format}")
        
        elif step == "processed":
            print("Processing with NLP...")
            processor = TextProcessor()
            
            # Use the chapter structure we already have
            if chapter_content:
                print("Using existing chapter structure as basis for NLP processing")
                # Create a structured content format that the TextProcessor would generate
                nlp_result = {
                    'metadata': {
                        'title': pdf_path.stem.replace('_', ' ').title(),
                        'type': 'Core Rulebook'
                    },
                    'table_of_contents': [],
                    'chapters': [],
                    'appendices': []
                }
                
                # Process chapters
                if 'chapters' in chapter_content:
                    for chapter in chapter_content['chapters']:
                        processed_chapter = {
                            'number': chapter.get('number', 0),
                            'title': chapter.get('title', 'Untitled Chapter'),
                            'sections': []
                        }
                        
                        # Convert chapter content to sections
                        if 'content' in chapter:
                            # Add main content as a section
                            if chapter['content'].get('main_content'):
                                main_content = '\n\n'.join(chapter['content']['main_content'])
                                # Only add if there's actual content
                                if main_content.strip():
                                    processed_chapter['sections'].append({
                                        'title': 'Main Content',
                                        'content': main_content
                                    })
                            
                            # Process tables if present
                            if 'tables' in chapter['content'] and chapter['content']['tables']:
                                # Process each table into a section
                                for table in chapter['content']['tables']:
                                    table_title = table.get('table_type', 'Table').replace('_', ' ').title()
                                    processed_chapter['sections'].append({
                                        'title': f"{table_title}",
                                        'content': f"Table: {table_title}\n\n" + _format_table_content(table),
                                        'is_table': True
                                    })
                            
                            # Add subchapters as sections
                            for subchapter in chapter['content'].get('subchapters', []):
                                if 'title' in subchapter and 'lines' in subchapter:
                                    # Join lines with proper paragraph breaks
                                    content = '\n\n'.join(subchapter['lines'])
                                    if content.strip():
                                        processed_chapter['sections'].append({
                                            'title': subchapter['title'],
                                            'content': content
                                        })
                        
                        nlp_result['chapters'].append(processed_chapter)
                
                # Generate a basic table of contents
                for chapter in nlp_result['chapters']:
                    if chapter['number'] > 0:  # Skip front matter
                        toc_entry = {
                            'type': 'chapter',
                            'number': chapter['number'],
                            'title': chapter['title'],
                            'sections': []
                        }
                        
                        # Add sections to TOC
                        for section in chapter['sections']:
                            if section['title'] != 'Main Content':
                                toc_entry['sections'].append({
                                    'title': section['title']
                                })
                        
                        nlp_result['table_of_contents'].append(toc_entry)
            else:
                # Fall back to regular processing if no chapter structure available
                nlp_result = processor.process(raw_text)
            
            results["processed"] = {
                'filename': pdf_path.name,
                'extraction_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'output_type': 'processed',
                'content': nlp_result
            }
    
    # Save the final requested output
    if output_type in results:
        save_output(results[output_type], output_format, output_dir, pdf_path)
    
    return results[output_type]

def save_output(data: Dict, output_format: str, output_dir: Path, pdf_path: Path, custom_name=None) -> None:
    """Save processed output to file."""
    # Create output filename
    base_name = pdf_path.stem
    if custom_name:
        output_subdir = output_dir
        filename_prefix = custom_name
    else:
        output_subdir = output_dir / data['output_type']
        filename_prefix = base_name
        os.makedirs(output_subdir, exist_ok=True)
    
    print(f"Writing to {filename_prefix}.{output_format}...", flush=True)
    
    try:
        if output_format == 'yaml':
            output_file = output_subdir / f"{filename_prefix}.yaml"
            write_yaml(data, output_file)
        elif output_format == 'json':
            output_file = output_subdir / f"{filename_prefix}.json"
            write_json(data, output_file)
        else:  # txt
            output_file = output_subdir / f"{filename_prefix}.txt"
            write_file(data['content'], output_file)
        
        logger.info(f"Output saved to {output_file}")
        print(f"Successfully saved to {output_file}")
    except Exception as e:
        logger.error(f"Error saving output: {str(e)}")
        print(f"ERROR: Failed to save output: {str(e)}")

def _format_table_content(table):
    """Format a table as markdown."""
    output = []
    
    if 'columns' not in table or 'rows' not in table:
        return "Table data unavailable"
    
    # Get columns and rows
    columns = table['columns']
    rows = table['rows']
    
    if not columns or not rows:
        return "Empty table"
    
    # Create header row
    header = "| " + " | ".join(columns) + " |"
    output.append(header)
    
    # Create separator row
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"
    output.append(separator)
    
    # Create data rows
    for row in rows:
        # Ensure row has correct number of columns
        padded_row = row + [''] * (len(columns) - len(row))
        data_row = "| " + " | ".join(str(cell) for cell in padded_row[:len(columns)]) + " |"
        output.append(data_row)
    
    return "\n".join(output)

def main():
    """Main CLI entry point."""
    # First, ask if the user wants to extract PDFs or validate markdown
    questions = [
        inquirer.List(
            'action',
            message='What would you like to do?',
            choices=[
                ('Extract text from PDF', 'extract'),
                ('Validate markdown file', 'validate')
            ],
        ),
    ]
    answers = inquirer.prompt(questions)
    
    if answers['action'] == 'extract':
        # Original PDF extraction flow
        pdf_path, output_format, processing_level = get_extraction_options()
        
        if not pdf_path:
            print("No PDF file selected. Exiting.")
            return 1
        
        print(f"\nExtracting text from {pdf_path}")
        logger.info(f"Extracting text from {pdf_path}")
        
        output_dir = Path("data/output") 
        result = process_pdf(pdf_path, output_format, output_dir, processing_level)
        
        return 0
    else:
        # New markdown validation flow
        markdown_path = select_markdown_file()
        
        if not markdown_path:
            print("No markdown file selected. Exiting.")
            return 1
        
        validate_markdown(markdown_path)
        return 0

def select_markdown_file():
    """Let the user select a markdown file to validate."""
    # Find all markdown files in the output directory
    markdown_files = glob.glob("data/output/markdown/*.md")
    
    if not markdown_files:
        print("No markdown files found in data/output/markdown/")
        # Ask if user wants to specify a different path
        questions = [
            inquirer.Confirm(
                'custom_path',
                message='No files found. Would you like to specify a custom path?',
                default=False
            ),
        ]
        answers = inquirer.prompt(questions)
        
        if answers['custom_path']:
            # Ask for a custom path
            questions = [
                inquirer.Path(
                    'markdown_path',
                    message='Enter the path to the markdown file:',
                    path_type=inquirer.Path.FILE,
                    exists=True,
                ),
            ]
            answers = inquirer.prompt(questions)
            return Path(answers['markdown_path'])
        else:
            return None
    
    # Create a list of markdown files for selection
    markdown_choices = [(f"{Path(f).name} ({Path(f).stat().st_size / 1024:.1f} KB)", f) for f in markdown_files]
    
    questions = [
        inquirer.List(
            'markdown_file',
            message='Select a markdown file to validate:',
            choices=markdown_choices,
        ),
    ]
    
    answers = inquirer.prompt(questions)
    return Path(answers['markdown_file'])

def validate_markdown(markdown_path):
    """Validate a markdown file and show results."""
    print(f"Validating markdown file: {markdown_path}")
    
    # Generate default output path
    default_output_path = str(markdown_path.parent / (markdown_path.stem + "_validation.txt"))
    
    # Ask for validation options
    questions = [
        inquirer.Confirm(
            'ignore_code',
            message='Ignore code blocks during validation?',
            default=True
        ),
        inquirer.List(
            'confidence',
            message='Select confidence threshold for reporting errors:',
            choices=[
                ('High (0.9) - Fewer false positives', 0.9),
                ('Medium (0.85) - Balanced', 0.85),
                ('Low (0.8) - More suggestions', 0.8),
            ],
            default=1,
        ),
        inquirer.Text(
            'output_path',
            message='Enter path for validation report (or leave empty for default):',
            default=default_output_path,
        ),
    ]
    
    answers = inquirer.prompt(questions)
    
    # Use default path if empty
    if not answers['output_path'].strip():
        answers['output_path'] = default_output_path
    
    # Configure validator
    validator_config = {
        'ignore_code_blocks': answers['ignore_code'],
        'min_confidence': answers['confidence'],
        'word_correction': {}
    }
    
    try:
        # Ensure output directory exists
        output_path = Path(answers['output_path'])
        os.makedirs(output_path.parent, exist_ok=True)
        
        validator = MarkdownValidator(validator_config)
        report = validator.validate_and_report(str(markdown_path), str(output_path))
        
        # Print a summary to console
        report_lines = report.split('\n')
        if len(report_lines) > 15:
            # Show first 15 lines if report is long
            print('\n'.join(report_lines[:15]))
            print(f"... and more. Full report saved to {answers['output_path']}")
        else:
            print(report)
            
        # Ask if user wants to open the report in a text editor
        if len(report_lines) > 5:  # Only if there are errors
            questions = [
                inquirer.Confirm(
                    'open_report',
                    message='Would you like to open the validation report?',
                    default=False
                ),
            ]
            answers = inquirer.prompt(questions)
            
            if answers['open_report']:
                import subprocess
                import platform
                
                try:
                    if platform.system() == 'Darwin':  # macOS
                        subprocess.call(('open', str(output_path)))
                    elif platform.system() == 'Windows':
                        os.startfile(str(output_path))
                    else:  # linux variants
                        subprocess.call(('xdg-open', str(output_path)))
                except Exception as e:
                    print(f"Could not open report: {e}")
        
        return True
    except Exception as e:
        print(f"Error validating markdown: {e}")
        return False

if __name__ == "__main__":
    sys.exit(main()) 