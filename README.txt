# OpenDataLoader PDF starter (Windows)

## 1) Confirm versions
Open Command Prompt or PowerShell and run:

python --version
java -version

You need:
- Python 3.10+
- Java 11+

## 2) Install the package
pip install -U opendataloader-pdf

## 3) Put your PDF in this folder
Rename your PDF to:
sample.pdf

## 4) Run
Double-click:
run_opendataloader.bat

Or run manually:
python convert_pdf.py

## 5) Output
Files will appear in:
output/

- sample.md
- sample.json

## Notes
- Batch multiple PDFs in one call when possible, because each convert() call starts a JVM process.
- For scanned PDFs or OCR-heavy PDFs, see hybrid_example.txt.
