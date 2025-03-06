"""
Main entry point for the PDF Text Extractor.
"""

import sys

from .cli import main as cli_main
from .markdown_convert import main as md_convert_main

def main():
    """Route to appropriate subcommand."""
    if len(sys.argv) > 1 and sys.argv[1] == "convert-md":
        # Remove the "convert-md" argument and pass the rest to the Markdown converter
        sys.argv.pop(1)
        return md_convert_main()
    else:
        # Default to the main CLI
        return cli_main()

if __name__ == "__main__":
    sys.exit(main()) 