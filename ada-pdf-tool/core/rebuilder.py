"""
PDF-to-docx reconstruction for retrospective PDFs with no source document.

Rebuilds a properly structured Word document from a docling extraction,
which can then be re-exported as a fully tagged PDF.
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
from pathlib import Path

from core._image_helpers import _crop_region_as_image, _extract_page_images
from core.models import AuditReport

logger = logging.getLogger(__name__)


def _infer_heading_level(text: str) -> int:
    """
    Infer heading level from common academic numbering conventions and casing.

    Rules (in priority order):
      Roman numeral prefix  → H1  (e.g. "I. Introduction", "IV Results")
      Capital letter prefix → H2  (e.g. "A. Background")
      Digit prefix          → H3  (e.g. "1. Method")
      ALL-CAPS short text   → H1  (e.g. "ABSTRACT", "RESULTS")
      Anything else         → H2  (safer default than H1 — prevents body text
                                    mislabelled as section_header from dominating
                                    document structure)
    """
    t = text.strip()
    if re.match(r"^(I|II|III|IV|V|VI|VII|VIII|IX|X)[\.\s]", t, re.IGNORECASE):
        return 1
    if re.match(r"^[A-Z]\.\s", t):
        return 2
    if re.match(r"^\d+\.\s", t):
        return 3
    if t.isupper() and len(t.split()) <= 12:
        return 1
    return 2


def _calculate_image_width(element: dict):
    """
    Return a python-docx ``Inches`` width for an image element based on its
    bbox relative to a standard letter-page width (612 pts).

    The ratio is clamped to [0.2, 0.85] so images are never tiny slivers or
    bleed-edge wide. Falls back to 4.5 inches when no bbox is available.
    """
    from docx.shared import Inches
    bbox = element.get("bbox")
    if bbox and len(bbox) == 4:
        img_width_pts = bbox[2] - bbox[0]
        ratio = img_width_pts / 612.0
        ratio = max(0.2, min(ratio, 0.85))
        return Inches(6.5 * ratio)
    return Inches(4.5)


def _get_table_grid(element: dict) -> tuple[list | None, bool]:
    """
    Read cell content from the extraction dict's ``cells`` field.

    Returns ``(grid, has_header)`` where ``grid`` is a non-empty list-of-lists
    of strings, or ``None`` when no structured data is available.
    The ``cells`` field is populated by ``extractor.extract()`` /
    ``extractor.extract_docx()`` from the underlying docling or python-docx
    table representation.
    """
    has_header = element.get("has_header_row") == "true"
    cells = element.get("cells")
    if cells and isinstance(cells, list) and len(cells) > 0:
        return cells, has_header
    return None, has_header


def rebuild_as_docx(
    extraction: dict,
    audit_report: AuditReport,
    user_inputs: dict,
    output_path: str,
    pdf_path: str | None = None,
    approved_fixes: list[dict] | None = None,
) -> str:
    """
    Reconstruct a structured Word document from a PDF extraction.

    Parameters: extraction (docling dict), audit_report (metadata fixes),
    user_inputs (element_id → alt text), output_path (.docx path),
    pdf_path (source PDF for image/formula/table extraction),
    approved_fixes (Stage 3 fixes).
    Returns output_path after writing.
    """
    from docx import Document as DocxDocument
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = DocxDocument()

    # ── Build O(1) lookup for approved fixes keyed by element_id ─────────
    fixes_by_element_id: dict[str, dict] = {
        f["element_id"]: f
        for f in (approved_fixes or [])
        if f.get("element_id")
    }

    # ── Document metadata ─────────────────────────────────────────────────
    title = extraction.get("metadata", {}).get("title") or ""
    language = "en-US"
    for fix in (audit_report.metadata_fixes or []):
        if fix.get("field") == "language" and fix.get("value"):
            language = fix["value"]
        if fix.get("field") == "title" and fix.get("value") and not title:
            title = fix["value"]

    doc.core_properties.title = title
    doc.core_properties.language = language

    # ── State for page-header deduplication and title detection ──────────
    title_added: bool = False
    seen_page_headers: set[str] = set()

    # ── Flatten all elements with page number for look-ahead ─────────────
    all_elements: list[tuple[int, dict]] = []
    for page in extraction.get("pages", []):
        pno = page.get("page_number", 1)
        for el in page.get("elements", []):
            all_elements.append((pno, el))

    for i, (page_no, element) in enumerate(all_elements):
        next_el = all_elements[i + 1][1] if i + 1 < len(all_elements) else None

        label = element.get("docling_label", "text")
        text = (element.get("text") or "").strip()
        element_id = element.get("id", "")
        elem_bbox = element.get("bbox")

        # ── Page footer — always skip ─────────────────────────────────
        if label == "page_footer":
            continue

        # ── Page header — recover title / unique identifiers ─────────
        elif label == "page_header":
            if not text:
                continue
            # Skip bare page numbers: "3", "Page 3", "Page  3", etc.
            if re.fullmatch(r"Page\s*\d+|\d+", text, re.IGNORECASE):
                continue
            if text in seen_page_headers:
                continue  # recurring header already included
            seen_page_headers.add(text)
            if page_no == 1 and not title_added:
                # Treat as document title
                doc.add_heading(text, level=0)
                title_added = True
            else:
                # Unique section identifier — centered italic
                p = doc.add_paragraph()
                run = p.add_run(text)
                run.italic = True
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # ── Title ─────────────────────────────────────────────────────
        elif label == "title":
            if not text:
                continue
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(text)
            run.bold = True
            run.font.size = Pt(14)
            run.font.color.rgb = RGBColor(0, 0, 0)
            run.font.name = "Times New Roman"
            title_added = True

        # ── Section header ────────────────────────────────────────────
        elif label == "section_header":
            if not text:
                continue
            fix = fixes_by_element_id.get(element_id, {})
            level = (
                int(fix["value"])
                if fix.get("value") and str(fix["value"]).isdigit()
                else _infer_heading_level(text)
            )
            h = doc.add_heading(text, level=level)
            for run in h.runs:
                run.font.color.rgb = RGBColor(0, 0, 0)

        # ── Body text / paragraph ─────────────────────────────────────
        elif label in ("text", "paragraph"):
            if not text:
                continue
            next_label = next_el.get("docling_label", "") if next_el else ""
            is_likely_heading = (
                re.match(r"^(I|II|III|IV|V|VI|VII|VIII|IX|X)[\.\s]", text, re.IGNORECASE)
                or re.match(r"^[A-Z]\.\s", text)
                or (text.isupper() and len(text.split()) <= 12)
                or (len(text.split()) <= 7 and next_label in ("text", "paragraph", "list_item"))
            )
            if is_likely_heading:
                level = _infer_heading_level(text)
                h = doc.add_heading(text, level=level)
                for run in h.runs:
                    run.font.color.rgb = RGBColor(0, 0, 0)
            else:
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                p.paragraph_format.first_line_indent = Inches(0.5)
                run = p.add_run(text)
                run.font.name = "Times New Roman"
                run.font.size = Pt(11)

        # ── Caption ───────────────────────────────────────────────────
        elif label == "caption":
            if not text:
                continue
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(text)
            run.italic = True
            run.font.name = "Times New Roman"
            run.font.size = Pt(10)

        # ── Footnote ──────────────────────────────────────────────────
        elif label == "footnote":
            if not text:
                continue
            p = doc.add_paragraph()
            run = p.add_run(text)
            run.font.name = "Times New Roman"
            run.font.size = Pt(9)

        # ── List item ─────────────────────────────────────────────────
        elif label == "list_item":
            if not text:
                continue
            doc.add_paragraph(text, style="List Bullet")

        # ── Code ──────────────────────────────────────────────────────
        elif label == "code":
            if not text:
                continue
            p = doc.add_paragraph()
            run = p.add_run(text)
            run.font.name = "Courier New"
            run.font.size = Pt(10)

        # ── Formula ───────────────────────────────────────────────────
        elif label == "formula":
            _fix = fixes_by_element_id.get(element_id, {})
            alt_text = _fix.get("user_value") or _fix.get("value") or user_inputs.get(element_id, "")
            rendered = False
            if pdf_path and elem_bbox:
                img_bytes = _crop_region_as_image(pdf_path, page_no - 1, elem_bbox, dpi=200)
                if img_bytes:
                    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                    tmp.write(img_bytes)
                    tmp.close()
                    try:
                        doc.add_picture(tmp.name, width=_calculate_image_width(element))
                        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
                        rendered = True
                    finally:
                        os.unlink(tmp.name)
            if not rendered:
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                fb = p.add_run(f"[Equation: {alt_text}]" if alt_text else "[Equation — provide plain text description]")
                fb.italic = True
            cap = doc.add_paragraph()
            cap_run = cap.add_run("[Formula — edit in source document]")
            cap_run.italic = True
            cap_run.font.size = Pt(9)
            cap_run.font.color.rgb = RGBColor(128, 128, 128)

        # ── Picture ───────────────────────────────────────────────────
        elif label == "picture":
            _fix = fixes_by_element_id.get(element_id, {})
            alt_text = _fix.get("user_value") or _fix.get("value") or user_inputs.get(element_id, "")
            img_bytes: bytes | None = None

            if pdf_path and elem_bbox:
                page_images = _extract_page_images(pdf_path, page_no - 1)
                if page_images:
                    ex = (elem_bbox[0] + elem_bbox[2]) / 2
                    ey = (elem_bbox[1] + elem_bbox[3]) / 2
                    best = min(
                        page_images,
                        key=lambda b: ((b[0] + b[2]) / 2 - ex) ** 2 + ((b[1] + b[3]) / 2 - ey) ** 2,
                    )
                    img_bytes = page_images[best]
                if not img_bytes:
                    img_bytes = _crop_region_as_image(pdf_path, page_no - 1, elem_bbox)

            if img_bytes:
                tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                tmp.write(img_bytes)
                tmp.close()
                try:
                    doc.add_picture(tmp.name, width=_calculate_image_width(element))
                    p_img = doc.paragraphs[-1]
                    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    if alt_text:
                        _WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
                        for p_run in p_img.runs:
                            for doc_pr in p_run._r.iter(f"{{{_WP}}}docPr"):
                                doc_pr.set("descr", alt_text)
                                break
                finally:
                    os.unlink(tmp.name)
            else:
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                placeholder = f"[Image: {alt_text}]" if alt_text else "[Image — alt text required: describe this image]"
                p.add_run(placeholder)

        # ── Table ─────────────────────────────────────────────────────
        elif label == "table":
            grid, has_header = _get_table_grid(element)

            if grid:
                n_rows = len(grid)
                n_cols = max((len(row) for row in grid), default=1)
                table = doc.add_table(rows=n_rows, cols=n_cols)
                try:
                    table.style = "Table Grid"
                except KeyError:
                    pass
                table.alignment = WD_TABLE_ALIGNMENT.LEFT
                for row_idx, row_data in enumerate(grid):
                    for col_idx, cell_text in enumerate(row_data):
                        if col_idx < n_cols:
                            cell = table.cell(row_idx, col_idx)
                            cell.paragraphs[0].text = str(cell_text or "")
                            if has_header and row_idx == 0:
                                for r in cell.paragraphs[0].runs:
                                    r.bold = True
            else:
                rendered = False
                if pdf_path and elem_bbox:
                    logger.warning("Table %s: no structured data, falling back to image crop", element_id)
                    img_bytes = _crop_region_as_image(pdf_path, page_no - 1, elem_bbox, dpi=150)
                    if img_bytes:
                        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                        tmp.write(img_bytes)
                        tmp.close()
                        try:
                            doc.add_picture(tmp.name, width=_calculate_image_width(element))
                            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
                            rendered = True
                        finally:
                            os.unlink(tmp.name)
                if not rendered:
                    doc.add_paragraph("[Table — could not extract content]")
            doc.add_paragraph()  # spacing after table

        # ── Unrecognised label — treat as body paragraph ──────────────
        else:
            if not text:
                continue
            logger.warning("Unrecognised docling_label %r for element %s — treating as body paragraph", label, element_id)
            p = doc.add_paragraph()
            run = p.add_run(text)
            run.font.name = "Times New Roman"
            run.font.size = Pt(11)

    doc.save(output_path)
    return output_path
