#!/usr/bin/env python3
"""
Smoke test: extract heading structure and write PDF bookmarks via pikepdf.

Usage:
    python test_bookmarks.py [path-to-pdf]

Defaults to ../samples/IV-A 2024.pdf relative to this script.
Output is written to tests/eval/sample_pdfs/output_bookmarks.pdf — the
original PDF is never modified.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running from ada-pdf-tool/ without installing the package
sys.path.insert(0, str(Path(__file__).parent))

import pikepdf
from core.extractor import extract

HEADING_LABELS = {"section_header", "title"}

DEFAULT_PDF = Path(__file__).parent.parent / "samples" / "IV-A 2024.pdf"
OUTPUT_PDF = (
    Path(__file__).parent
    / "tests"
    / "eval"
    / "sample_pdfs"
    / "output_bookmarks.pdf"
)


def collect_headings(extraction: dict) -> list[tuple[str, int]]:
    """Return [(heading_text, page_number_1based), ...] in document order."""
    headings: list[tuple[str, int]] = []
    for page in extraction["pages"]:
        pn = page["page_number"]
        for el in page["elements"]:
            if el.get("docling_label") in HEADING_LABELS:
                text = (el.get("text") or "").strip()
                if text:
                    headings.append((text, pn))
    return headings


def write_bookmarks(
    src_pdf: Path, headings: list[tuple[str, int]], dest_pdf: Path
) -> None:
    """Open src_pdf, attach outlines from headings, save to dest_pdf."""
    dest_pdf.parent.mkdir(parents=True, exist_ok=True)

    with pikepdf.open(src_pdf) as pdf:
        with pdf.open_outline() as outline:
            for text, page_no in headings:
                # pikepdf OutlineItem page numbers are 0-based
                item = pikepdf.OutlineItem(text, page_no - 1)
                outline.root.append(item)

        # Tell viewers to open the bookmarks panel on launch
        pdf.Root["/PageMode"] = pikepdf.Name("/UseOutlines")

        pdf.save(dest_pdf)


def main() -> None:
    pdf_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PDF

    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Extracting: {pdf_path} ...")
    extraction = extract(pdf_path)

    headings = collect_headings(extraction)
    if not headings:
        print("No headings found (SECTION_HEADER or TITLE elements). Nothing to write.")
        sys.exit(0)

    write_bookmarks(pdf_path, headings, OUTPUT_PDF)

    labels = [text for text, _ in headings]
    print(f"\nAdded {len(labels)} bookmarks: {labels}")
    print(f"\nOutput written to: {OUTPUT_PDF.resolve()}")


if __name__ == "__main__":
    main()
