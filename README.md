# PDF Text Extractor

A Python-based tool for extracting, validating, and processing text from PDF documents with advanced NLP capabilities and Markdown conversion.

## 📑 Overview

PDF Text Extractor is a comprehensive solution for transforming PDF documents into clean, structured text. It handles various PDF types including scanned documents and employs NLP techniques to correct common extraction issues like broken words, hyphenation problems, and OCR errors. The tool also provides conversion to Markdown format to make documentation more accessible.

## 🔑 Key Features

- **Versatile PDF Text Extraction**: Support for both digital and scanned PDFs
- **OCR Integration**: Extract text from images and scanned documents
- **Advanced Text Processing**:
  - Chapter and section detection
  - Table recognition and formatting
  - Document structure analysis
- **NLP-powered Text Correction**:
  - Fix broken words and spaced text (like "D u n g e o n s")
  - Correct hyphenation issues
  - Repair OCR errors
  - Identify and normalize document structure
- **Markdown Conversion**: Convert extracted content to well-formatted Markdown
- **Multi-format Output**: Export to plain text, JSON, YAML, or Markdown
- **Interactive CLI**: User-friendly command-line interface for file selection and processing

## 🛠️ Installation

### Option 1: Using UV (Recommended)

#### Clone the repository

    git clone https://github.com/traagel/pdf-extractor.git
    cd pdf-text-extractor

#### Create and activate a virtual environment with UV

    uv venv --python 3.11.11
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate

#### Install with UV

    uv pip install -e .

#### For development dependencies (testing, linting, etc.)

    uv pip install -e ".[dev]"

### Option 2: Using Standard Pip

#### Clone the repository

    git clone https://github.com/traagel/pdf-extractor.git
    cd pdf-text-extractor

#### Create and activate a virtual environment

    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate

#### Install using pip

    pip install -e .

#### For development dependencies

    pip install -e ".[dev]"

## 📋 System Requirements

- Python 3.8+ (Python 3.11 recommended)
- Dependencies:
  - PyMuPDF (fitz)
  - PyPDF
  - pytesseract
  - spaCy (with en_core_web_sm model)
  - PyYAML
  - tqdm
  - inquirer
- Tesseract OCR engine (for OCR functionality)
  - Ubuntu/Debian: `sudo apt-get install tesseract-ocr`
  - macOS: `brew install tesseract`
  - Windows: Download from [UB-Mannheim Tesseract](https://github.com/UB-Mannheim/tesseract/wiki)

## 🚀 Quick Start

### Using the Command-Line Interface

After installation, you can use the PDF Text Extractor in several ways:

1. As a console script for extraction:

       # Interactive mode (will scan input directory and prompt for choices)
       pdf-extractor

       # Specify input file and format
       pdf-extractor --file path/to/document.pdf --format yaml --type lines_chapters

2. For Markdown conversion:

       # Convert extraction output to Markdown
       pdf-extractor convert-md path/to/extracted.yaml -o output.md

       # With additional options
       pdf-extractor convert-md path/to/extracted.json --no-toc --clean-text advanced

3. As a Python module:

       python -m src

### Python API Usage

    from src.extraction.pdf_extractor import PDFExtractor
    from src.processing.text_processor import TextProcessor
    from src.converters.markdown_converter import convert_to_markdown

    # Extract text from a PDF file
    extractor = PDFExtractor()
    text = extractor.extract("data/input/document.pdf")

    # Process text into structured format
    processor = TextProcessor()
    structured_content = processor.process(text)

    # Convert to Markdown
    markdown = convert_to_markdown(structured_content, "output.md", {
        'toc': True,
        'text_cleaning': 'light'
    })

## 📦 Project Structure

    pdf-text-extractor/
    │
    ├── src/                  # Source code
    │   ├── extraction/       # PDF text extraction modules
    │   ├── processing/       # Text processing components
    │   ├── nlp/              # Natural Language Processing components
    │   ├── converters/       # Format conversion tools
    │   ├── validation/       # Text validation tools
    │   └── utils/            # Utility functions and helpers
    │
    ├── tests/                # Unit and integration tests
    ├── data/                 # Directory for input/output data and models
    │   ├── input/            # Place PDF files here for processing
    │   ├── output/           # Extracted and processed texts are saved here
    │   └── resources/        # NLP resources and word lists
    │
    ├── config/               # Configuration files
    └── docs/                 # Documentation

## 📊 Processing Pipeline

1. **Document Loading** - Load PDF from file
2. **Extraction** - Extract text using PyMuPDF, PyPDF, or OCR
3. **Line Processing** - Split text into clean lines
4. **Chapter Processing** - Identify chapters and sections
5. **NLP Processing** - Clean text and fix common issues
6. **Validation** - Check extraction quality
7. **Format Conversion** - Export to desired format (YAML, JSON, Markdown)

## 🧩 Main Components

### Extraction Module

- **PDFExtractor**: Core PDF text extraction with multiple methods
- **ImageTextExtractor**: OCR-based extraction for images and scanned PDFs

### Processing Module

- **TextProcessor**: Structures PDF content into organized sections
- **ChapterProcessor**: Identifies and extracts chapters
- **TableProcessor**: Recognizes and formats tables in text
- **LineProcessor**: Handles line-based text processing

### NLP Module

- **TextStructureAnalyzer**: Document structure analysis
- **TextCleaner**: Fixes common extraction artifacts
- **TextValidator**: Validates text quality

### Converters Module

- **MarkdownConverter**: Converts structured content to Markdown format

### Validation Module

- **TextValidator**: Checks extraction quality
- **SchemaValidator**: Validates output against schemas

### Utils Module

- **Logger**: Configurable logging
- **FileHandler**: File I/O utilities

## ⚙️ Markdown Conversion

The PDF Text Extractor includes a powerful Markdown conversion feature:

    # Convert to Markdown with table of contents
    python -m src convert-md data/output/processed/document.yaml

    # Convert without table of contents
    python -m src convert-md data/output/processed/document.json --no-toc

    # Apply advanced text cleaning
    python -m src convert-md data/output/processed/document.yaml --clean-text advanced

    # Process all files in a directory recursively
    python -m src convert-md data/output/processed/ --recursive -o docs/

Markdown conversion features:

- Table of contents generation
- Clean formatting of chapters and sections
- Table support
- Text cleaning to fix common OCR artifacts
- Front matter handling
- Custom styling options

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 📞 Contact

For questions or support, please open an issue on the GitHub repository or contact the maintainers.

## 📁 Output Organization

The PDF Text Extractor organizes output files into different directories based on the level of processing:

- **Raw Extraction** (`data/output/raw/`): Text extracted directly from PDFs
- **Lines** (`data/output/lines/`): Text split into lines with basic cleaning
- **Lines & Chapters** (`data/output/lines_chapters/`): Text organized into chapters and sections
- **Processed** (`data/output/processed/`): Text after all NLP corrections and enhancements

You can specify the desired output type using the `--type` command-line option or through the interactive prompt:

    # Using the CLI option
    pdf-extractor --file document.pdf --format yaml --type lines_chapters

    # The interactive mode will prompt you to select the output type
    pdf-extractor
