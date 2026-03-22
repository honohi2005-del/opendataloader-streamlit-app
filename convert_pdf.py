import sys
from pathlib import Path
import opendataloader_pdf

HERE = Path(__file__).resolve().parent
pdf_path = HERE / "sample.pdf"
output_dir = HERE / "output"

if not pdf_path.exists():
    raise FileNotFoundError(
        f"Could not find {pdf_path.name}. Put your PDF in this folder and rename it to sample.pdf"
    )

output_dir.mkdir(exist_ok=True)

opendataloader_pdf.convert(
    input_path=[str(pdf_path)],
    output_dir=str(output_dir),
    format="markdown,json"
)

print("Done.")
print(f"Input:  {pdf_path}")
print(f"Output: {output_dir}")
