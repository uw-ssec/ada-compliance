"""
Content validation helpers for the untagged-PDF rebuild pipeline.

Both functions are read-only and return empty dicts on any error so the
caller can degrade gracefully.
"""
from __future__ import annotations


def count_source_elements(extraction: dict) -> dict[str, int]:
    """Count pictures, formulae, and tables in a docling extraction dict."""
    counts = {"pictures": 0, "formulae": 0, "tables": 0}
    for page in extraction.get("pages", []):
        for el in page.get("elements", []):
            label = el.get("docling_label", "")
            if label == "picture":
                counts["pictures"] += 1
            elif label == "formula":
                counts["formulae"] += 1
            elif label == "table":
                counts["tables"] += 1
    return counts


def count_docx_elements(docx_path: str) -> dict[str, int]:
    """
    Count inline images and tables in a rebuilt docx.

    Formulae are inserted as images during rebuild, so they count toward
    the images total — the caller should compare actual images against
    source pictures + formulae combined.
    """
    try:
        from docx import Document as DocxDocument
        from docx.oxml.ns import qn
    except ImportError:
        return {"images": 0, "tables": 0}

    try:
        doc = DocxDocument(docx_path)
        # w:drawing covers both inline image crops and formula crops
        images = len(doc.element.body.findall(f".//{qn('w:drawing')}"))
        return {"images": images, "tables": len(doc.tables)}
    except Exception:
        return {"images": 0, "tables": 0}
