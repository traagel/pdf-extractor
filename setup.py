from setuptools import setup, find_packages

setup(
    name="pdf-text-extractor",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "PyMuPDF",
        "pypdf",
        "pytesseract",
        "Pillow",
        "numpy",
        "spacy>=3.0.0",
        "en-core-web-sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl",
        "nltk",
        "pyyaml",
        "inquirer",
        "blessed",
        "six",
        "wcwidth",
    ],
    extras_require={
        "dev": [
            "pytest",
            "pytest-cov",
            "black",
            "flake8",
        ],
    },
    entry_points={
        "console_scripts": [
            "pdf-extractor=src.cli:main",
        ],
    },
    python_requires=">=3.8",
    description="Extract and process text from PDF documents",
    author="Your Name",
    author_email="your.email@example.com",
    url="https://github.com/yourusername/pdf-text-extractor",
)
