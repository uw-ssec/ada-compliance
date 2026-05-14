#!/usr/bin/env python3
"""
Smoke test: add a PDF/UA-style structure tree to a PDF via pikepdf.

What this adds
--------------
- /MarkInfo /Marked true  — tells readers the document is tagged
- /StructTreeRoot           — hierarchy of logical structure elements
  └─ Document
     ├─ H1  (docling label: title)
     ├─ H2  (docling label: section_header)
     └─ P   (docling label: text / paragraph)

Each struct element carries /Pg (page reference) and /Alt (the extracted
text), so accessibility tools can announce it even without full MCID-linked
content-stream marking.

What this does NOT do
---------------------
Full WCAG PDF/UA conformance also requires BDC/EMC operators injected into
each page's raw content stream (one per element, keyed by MCID). Doing that
correctly requires a graphics-state interpreter to locate each text run by
position. That is a separate, larger undertaking.

Usage
-----
    python test_tags.py [path-to-pdf]

Output: tests/eval/sample_pdfs/output_tagged.pdf
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pikepdf
from core.extractor import extract

LABEL_TO_STRUCT = {
    "title": "H1",
    "section_header": "H2",
    "text": "P",
    "paragraph": "P",
    "list_item": "LI",
    "caption": "Caption",
    "footnote": "Note",
}

DEFAULT_PDF = Path(__file__).parent.parent / "samples" / "IV-A 2024.pdf"
OUTPUT_PDF = (
    Path(__file__).parent
    / "tests"
    / "eval"
    / "sample_pdfs"
    / "output_tagged.pdf"
)


def collect_elements(extraction: dict) -> list[dict]:
    elements = []
    for page in extraction["pages"]:
        for el in page["elements"]:
            label = el.get("docling_label", "")
            if label in LABEL_TO_STRUCT:
                elements.append(
                    {
                        "text": (el.get("text") or "").strip(),
                        "label": label,
                        "struct_type": LABEL_TO_STRUCT[label],
                        "page_no": page["page_number"],  # 1-based
                    }
                )
    return elements


def add_structure_tree(pdf: pikepdf.Pdf, elements: list[dict]) -> None:
    """Attach /MarkInfo and /StructTreeRoot to the PDF root."""

    # ── StructTreeRoot ────────────────────────────────────────────────────
    struct_root = pdf.make_indirect(
        pikepdf.Dictionary(
            Type=pikepdf.Name("/StructTreeRoot"),
            K=pikepdf.Array(),
            ParentTree=pdf.make_indirect(
                pikepdf.Dictionary(Nums=pikepdf.Array())
            ),
        )
    )

    # ── Document element (top-level container) ────────────────────────────
    doc_elem = pdf.make_indirect(
        pikepdf.Dictionary(
            Type=pikepdf.Name("/StructElem"),
            S=pikepdf.Name("/Document"),
            P=struct_root,
            K=pikepdf.Array(),
        )
    )
    struct_root.K.append(doc_elem)

    # ── One struct element per extracted element ───────────────────────────
    for el in elements:
        page_idx = el["page_no"] - 1
        page_ref = pdf.pages[page_idx].obj if page_idx < len(pdf.pages) else None

        d = pikepdf.Dictionary(
            Type=pikepdf.Name("/StructElem"),
            S=pikepdf.Name("/" + el["struct_type"]),
            P=doc_elem,
            # /Alt lets AT announce the text even without MCID content links
            Alt=pikepdf.String(el["text"][:500]),  # PDF spec recommends ≤ 512 chars
        )
        if page_ref is not None:
            d["/Pg"] = page_ref

        doc_elem.K.append(pdf.make_indirect(d))

    # ── Attach to root ────────────────────────────────────────────────────
    pdf.Root["/StructTreeRoot"] = struct_root
    pdf.Root["/MarkInfo"] = pdf.make_indirect(
        pikepdf.Dictionary(Marked=True)
    )


def print_tag_tree(elements: list[dict]) -> None:
    INDENT = {"H1": 0, "H2": 1, "P": 2, "LI": 2, "Caption": 2, "Note": 2}
    for el in elements:
        indent = "  " * INDENT.get(el["struct_type"], 2)
        preview = el["text"][:60].replace("\n", " ")
        print(f"  {indent}<{el['struct_type']}> p{el['page_no']}  {preview}")


def verify(path: Path) -> None:
    """Read back the saved PDF and confirm the structure tree is intact."""
    with pikepdf.open(path) as pdf:
        marked = pdf.Root.get("/MarkInfo", {}).get("/Marked", False)
        has_tree = "/StructTreeRoot" in pdf.Root
        if has_tree:
            doc_kids = pdf.Root["/StructTreeRoot"].K[0].K
            n = len(doc_kids)
        else:
            n = 0
        print(f"\nVerification ({path.name}):")
        print(f"  /MarkInfo /Marked  = {bool(marked)}")
        print(f"  /StructTreeRoot    = {has_tree}")
        print(f"  struct elements    = {n}")


def main() -> None:
    pdf_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PDF
    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Extracting: {pdf_path} ...")
    extraction = extract(pdf_path)

    elements = collect_elements(extraction)

    counts = {}
    for el in elements:
        counts[el["struct_type"]] = counts.get(el["struct_type"], 0) + 1

    print(f"\nTag tree to be written ({len(elements)} elements):")
    print("  <Document>")
    print_tag_tree(elements)

    OUTPUT_PDF.parent.mkdir(parents=True, exist_ok=True)

    with pikepdf.open(pdf_path) as pdf:
        add_structure_tree(pdf, elements)
        pdf.save(OUTPUT_PDF)

    print(f"\nWritten → {OUTPUT_PDF.resolve()}")
    print("  " + "  ".join(f"{k}×{v}" for k, v in sorted(counts.items())))

    verify(OUTPUT_PDF)


if __name__ == "__main__":
    main()
