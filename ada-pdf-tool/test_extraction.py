#!/usr/bin/env python3
"""
Manual extraction test script.

Usage:
    python test_extraction.py <path-to-pdf>

Runs the docling extractor on the given PDF and writes the structured JSON
output to extraction_output.json in the current directory for manual inspection.
"""

import sys
import json
from pathlib import Path

# Allow running from ada-pdf-tool/ without installing the package
sys.path.insert(0, str(Path(__file__).parent))

from core.extractor import extract


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python test_extraction.py <path-to-pdf>", file=sys.stderr)
        sys.exit(1)

    pdf_path = Path(sys.argv[1])
    if not pdf_path.exists():
        print(f"Error: file not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Extracting: {pdf_path} ...")

    try:
        result = extract(pdf_path)
    except ValueError as exc:
        print(f"Extraction failed: {exc}", file=sys.stderr)
        sys.exit(1)

    output_path = Path("extraction_output.json")
    output_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")

    page_count = result["metadata"]["page_count"]
    total_elements = sum(len(p["elements"]) for p in result["pages"])
    print(f"Done. {page_count} pages, {total_elements} elements extracted.")
    print(f"Output written to: {output_path.resolve()}")


if __name__ == "__main__":
    main()
