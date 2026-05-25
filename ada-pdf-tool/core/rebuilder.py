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


# ── Font fallback mapping ─────────────────────────────────────────────────────
# Maps PDF font name prefixes to Word-compatible font names.
FONT_FALLBACKS = {
    "CMR": "Times New Roman",
    "CMMI": "Times New Roman",
    "CMBX": "Times New Roman",
    "Helvetica": "Arial",
    "Arial": "Arial",
    "Times": "Times New Roman",
}

_ROMAN = re.compile(r"^(I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII)\.?\s", re.IGNORECASE)
_CAPITAL_LETTER = re.compile(r"^[A-Z]\.\s")
_NUMBER = re.compile(r"^\d+\.\s")


def _resolve_font(font_name: str) -> str:
    """
    Map a PDF font name to a Word-compatible font name.

    Checks if font_name starts with any key in FONT_FALLBACKS and returns
    the mapped value. Returns "Calibri" if no mapping is found.
    """
    for prefix, mapped in FONT_FALLBACKS.items():
        if font_name.startswith(prefix):
            return mapped
    return "Calibri"


def _infer_heading_level(text: str) -> int:
    """Infer heading level from common academic numbering conventions."""
    if _ROMAN.match(text):
        return 1
    if _CAPITAL_LETTER.match(text):
        return 2
    if _NUMBER.match(text):
        return 3
    return 1


def _get_table_grid(element) -> tuple[list | None, bool]:
    """
    Extract structured cell data from a docling TableItem or extraction dict.

    Returns ``(grid, has_header)`` where ``grid`` is a list-of-lists of
    strings, or ``None`` if no structured data is available.
    """
    has_header = element.get("has_header_row") == "true" if isinstance(element, dict) else False
    # Path 1: raw docling TableItem — export_to_dataframe()
    if hasattr(element, "export_to_dataframe"):
        try:
            df = element.export_to_dataframe()
            return [list(df.columns)] + [[str(v) for v in r] for r in df.values.tolist()], True
        except Exception:
            pass
    # Path 2: raw docling TableItem — .data.grid (list[list[TableCell]])
    raw_grid = getattr(getattr(element, "data", None), "grid", None)
    if raw_grid:
        return [[getattr(c, "text", "") or "" for c in row] for row in raw_grid], has_header
    return None, has_header


def _extract_span_formatting(pdf_path: str) -> dict[int, list[dict]]:
    """
    Extract per-span formatting for every page using pymupdf.

    Parameters
    ----------
    pdf_path : str
        Path to the source PDF.

    Returns
    -------
    dict[int, list[dict]]
        Keys are 0-indexed page numbers. Each value is a list of span dicts
        with keys: ``text``, ``font``, ``size``, ``color`` (RGB tuple as
        (r, g, b) 0–255), ``bold`` (bool from flags & 16), ``italic`` (bool
        from flags & 2), ``bbox`` ([x0, y0, x1, y1]).
        Returns an empty dict on import error or any pymupdf exception.
    """
    try:
        import fitz
    except ImportError:
        return {}

    result: dict[int, list[dict]] = {}

    try:
        doc = fitz.open(pdf_path)
        for page_idx, page in enumerate(doc):
            spans: list[dict] = []
            page_dict = page.get_text("dict")
            for block in page_dict.get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        flags = span.get("flags", 0)
                        color_int = span.get("color", 0)
                        r = (color_int >> 16) & 0xFF
                        g = (color_int >> 8) & 0xFF
                        b = color_int & 0xFF
                        spans.append({
                            "text": span.get("text", ""),
                            "font": span.get("font", ""),
                            "size": float(span.get("size", 12.0)),
                            "color": (r, g, b),
                            "bold": bool(flags & 16),
                            "italic": bool(flags & 2),
                            "bbox": list(span.get("bbox", [0, 0, 0, 0])),
                        })
            result[page_idx] = spans
        doc.close()
    except Exception:
        pass

    return result


def _match_span(element_bbox: list, page_spans: list[dict]) -> dict | None:
    """
    Return the span from ``_extract_span_formatting`` whose bbox has the
    highest IoU with ``element_bbox``, or None if no match exceeds 0.3.
    """
    if not element_bbox or not page_spans:
        return None

    ax0, ay0, ax1, ay1 = element_bbox
    area_a = max(0.0, ax1 - ax0) * max(0.0, ay1 - ay0)
    if area_a <= 0:
        return None

    best_span: dict | None = None
    best_iou: float = 0.3  # minimum threshold

    for span in page_spans:
        bx0, by0, bx1, by1 = span["bbox"]
        ix0 = max(ax0, bx0)
        iy0 = max(ay0, by0)
        ix1 = min(ax1, bx1)
        iy1 = min(ay1, by1)
        if ix1 <= ix0 or iy1 <= iy0:
            continue
        inter = (ix1 - ix0) * (iy1 - iy0)
        area_b = max(0.0, bx1 - bx0) * max(0.0, by1 - by0)
        union = area_a + area_b - inter
        iou = inter / union if union > 0 else 0.0
        if iou > best_iou:
            best_iou = iou
            best_span = span

    return best_span


def rebuild_as_docx(
    extraction: dict,
    audit_report: AuditReport,
    user_inputs: dict,
    output_path: str,
    pdf_path: str | None = None,
) -> str:
    """
    Reconstruct a properly structured Word document from a PDF extraction.

    Parameters
    ----------
    extraction:
        Output of extract() — the docling extraction JSON dict.
    audit_report:
        AuditReport from the analysis layer, used to read metadata fixes.
    user_inputs:
        Mapping of element_id → user-provided alt text or description.
    output_path:
        Path where the reconstructed .docx will be written.
    pdf_path:
        Optional path to the source PDF. When provided, pymupdf span
        formatting (font name, size, color, bold, italic) is extracted and
        applied to text runs in the rebuilt document.

    Returns
    -------
    str — the output_path after writing.
    """
    from docx import Document as DocxDocument
    from docx.shared import Pt, RGBColor
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = DocxDocument()

    # ── Extract span formatting from source PDF if path is available ──────
    span_data: dict[int, list[dict]] = (
        _extract_span_formatting(pdf_path) if pdf_path else {}
    )

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

    # ── Iterate elements in page order ────────────────────────────────────
    for page in extraction.get("pages", []):
        page_no = page.get("page_number", 1)
        # span_data is 0-indexed; page_number is 1-indexed
        page_spans = span_data.get(page_no - 1, [])

        for element in page.get("elements", []):
            label = element.get("docling_label", "text")
            text = (element.get("text") or "").strip()
            element_id = element.get("id", "")
            elem_bbox = element.get("bbox")

            if label in ("page_header", "page_footer"):
                continue  # document chrome, not content

            elif label == "title":
                if text:
                    doc.add_heading(text, level=0)

            elif label == "section_header":
                if text:
                    level = _infer_heading_level(text)
                    doc.add_heading(text, level=level)

            elif label in ("text", "paragraph", "list_item", "caption", "footnote"):
                if not text:
                    continue

                if label == "list_item":
                    p = doc.add_paragraph(style="List Bullet")
                elif label == "caption":
                    p = doc.add_paragraph()
                    try:
                        p.style = doc.styles["Caption"]
                    except KeyError:
                        p.style = doc.styles["Normal"]
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                elif label == "footnote":
                    p = doc.add_paragraph()
                    p.style = doc.styles["Normal"]
                else:
                    p = doc.add_paragraph()

                run = p.add_run(text)

                # Apply pymupdf span formatting when a bbox match is found.
                span = _match_span(elem_bbox, page_spans)
                if span:
                    run.bold = span["bold"]
                    run.italic = span["italic"]
                    run.font.size = Pt(span["size"])
                    run.font.color.rgb = RGBColor(*span["color"])
                    run.font.name = _resolve_font(span["font"])
                elif label == "footnote":
                    run.font.size = Pt(9)  # fallback for footnotes

            elif label == "picture":
                alt_text = user_inputs.get(element_id, "")
                img_bytes: bytes | None = None

                if pdf_path and elem_bbox:
                    page_images = _extract_page_images(pdf_path, page_no - 1)
                    if page_images:
                        # Nearest-center match between element bbox and image bboxes
                        ex = (elem_bbox[0] + elem_bbox[2]) / 2
                        ey = (elem_bbox[1] + elem_bbox[3]) / 2
                        best = min(
                            page_images,
                            key=lambda b: ((b[0]+b[2])/2 - ex)**2 + ((b[1]+b[3])/2 - ey)**2,
                        )
                        img_bytes = page_images[best]
                    if not img_bytes:
                        img_bytes = _crop_region_as_image(pdf_path, page_no - 1, elem_bbox)

                if img_bytes:
                    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                    tmp.write(img_bytes)
                    tmp.close()
                    try:
                        doc.add_picture(tmp.name)
                        p_img = doc.paragraphs[-1]
                        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        # python-docx has no native alt-text API for inline images.
                        # Set descr on wp:docPr — the attribute screen readers use.
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
                    run = p.add_run()
                    if alt_text:
                        run.add_text(f"[Image: {alt_text}]")
                    else:
                        run.add_text("[Image — alt text required: describe this image]")

            elif label == "formula":
                alt_text = user_inputs.get(element_id, "")
                rendered = False
                if pdf_path and elem_bbox:
                    img_bytes = _crop_region_as_image(
                        pdf_path, page_no - 1, elem_bbox, dpi=200
                    )
                    if img_bytes:
                        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                        tmp.write(img_bytes)
                        tmp.close()
                        try:
                            doc.add_picture(tmp.name)
                            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
                            rendered = True
                        finally:
                            os.unlink(tmp.name)
                if not rendered:
                    p = doc.add_paragraph()
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    fb = p.add_run(f"[Equation: {alt_text}]" if alt_text else "[Equation — provide plain text description]")
                    fb.italic = True
                # Caption paragraph after formula image
                cap = doc.add_paragraph()
                cap_run = cap.add_run("[Formula — edit in source document]")
                cap_run.italic = True
                cap_run.font.size = Pt(9)
                cap_run.font.color.rgb = RGBColor(128, 128, 128)

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
                    # Fallback: render table region as image
                    rendered = False
                    if pdf_path and elem_bbox:
                        logger.warning("Table %s: no structured cell data, falling back to image crop", element_id)
                        img_bytes = _crop_region_as_image(pdf_path, page_no - 1, elem_bbox, dpi=150)
                        if img_bytes:
                            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                            tmp.write(img_bytes)
                            tmp.close()
                            try:
                                doc.add_picture(tmp.name)
                                doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
                                rendered = True
                            finally:
                                os.unlink(tmp.name)
                    if not rendered:
                        doc.add_paragraph("[Table — could not extract content]")
                doc.add_paragraph()  # spacing after table

    doc.save(output_path)
    return output_path
