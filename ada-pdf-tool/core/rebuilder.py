"""
PDF-to-docx reconstruction for retrospective PDFs with no source document.

Rebuilds a properly structured Word document from a docling extraction,
which can then be re-exported as a fully tagged PDF.
"""

from __future__ import annotations

import re
from pathlib import Path

from core.models import AuditReport


_ROMAN = re.compile(r"^(I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII)\.?\s", re.IGNORECASE)
_CAPITAL_LETTER = re.compile(r"^[A-Z]\.\s")
_NUMBER = re.compile(r"^\d+\.\s")


def _infer_heading_level(text: str) -> int:
    """Infer heading level from common academic numbering conventions."""
    if _ROMAN.match(text):
        return 1
    if _CAPITAL_LETTER.match(text):
        return 2
    if _NUMBER.match(text):
        return 3
    return 1


def rebuild_as_docx(
    extraction: dict,
    audit_report: AuditReport,
    user_inputs: dict,
    output_path: str,
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

    Returns
    -------
    str — the output_path after writing.
    """
    from docx import Document as DocxDocument
    from docx.shared import Inches, Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = DocxDocument()

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

    # ── Iterate elements in reading order ─────────────────────────────────
    all_elements: list[dict] = []
    for page in extraction.get("pages", []):
        all_elements.extend(page.get("elements", []))

    for element in all_elements:
        label = element.get("docling_label", "text")
        text = (element.get("text") or "").strip()
        element_id = element.get("id", "")

        if label in ("page_header", "page_footer"):
            continue  # document chrome, not content

        elif label == "title":
            if text:
                doc.add_heading(text, level=0)

        elif label == "section_header":
            if text:
                level = _infer_heading_level(text)
                doc.add_heading(text, level=level)

        elif label in ("text", "paragraph"):
            if text:
                doc.add_paragraph(text)

        elif label == "list_item":
            if text:
                doc.add_paragraph(text, style="List Bullet")

        elif label == "caption":
            if text:
                p = doc.add_paragraph(text)
                try:
                    p.style = doc.styles["Caption"]
                except KeyError:
                    p.style = doc.styles["Normal"]
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        elif label == "footnote":
            if text:
                p = doc.add_paragraph(text)
                p.style = doc.styles["Normal"]
                if p.runs:
                    p.runs[0].font.size = Pt(9)

        elif label == "picture":
            alt_text = user_inputs.get(element_id, "")
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run()
            # TODO: if element contains image_bytes or image_path, insert
            # the actual image with doc.add_picture() and set alt text on
            # the drawing XML element. For now use placeholder text.
            if alt_text:
                run.add_text(f"[Image: {alt_text}]")
            else:
                run.add_text("[Image — alt text required: describe this image]")

        elif label == "formula":
            alt_text = user_inputs.get(element_id, "")
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if alt_text:
                run = p.add_run(f"[Equation: {alt_text}]")
            else:
                run = p.add_run("[Equation — provide plain text description]")
            run.italic = True

        elif label == "table":
            rows = element.get("rows") or 2
            cols = element.get("cols") or 2
            table = doc.add_table(rows=rows, cols=cols)
            try:
                table.style = "Table Grid"
            except KeyError:
                pass

            # Apply header style to first row
            header_style = None
            try:
                header_style = doc.styles["Table Header"]
            except KeyError:
                header_style = doc.styles["Normal"]

            for cell in table.rows[0].cells:
                for para in cell.paragraphs:
                    para.style = header_style
                    if header_style.name == "Normal":
                        for run in para.runs:
                            run.bold = True

            # Mark first header cell
            if table.rows[0].cells:
                first_para = table.rows[0].cells[0].paragraphs[0]
                first_para.text = "[Table — fill in content]"

    doc.save(output_path)
    return output_path
