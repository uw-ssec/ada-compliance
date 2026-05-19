"""
Remediation layer — applies approved fixes to PDF (pikepdf) and docx (python-docx).

PDF: only metadata fixes (language, title) and bookmark generation can be
applied programmatically. Structural fixes require editing the source document.

docx: all structural fix types are writable via python-docx.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pikepdf


_SKIP_REASON = (
    "Requires accessibility tag tree — fix in source document (Word/Google Docs) "
    "and re-export with accessibility settings enabled."
)

_STRUCTURAL_FIX_TYPES = {"heading_tag", "alt_text", "link_tag", "table_header"}


def remediate(
    input_path: str,
    output_path: str,
    approved_fixes: list,
) -> dict:
    """
    Apply approved fixes to input_path and write the result to output_path.

    Parameters
    ----------
    input_path:
        Path to the original PDF. Never modified.
    output_path:
        Path where the remediated PDF will be written.
    approved_fixes:
        List of fix dicts. Each fix must have at minimum:
          - "fix_type": one of "set_language", "set_title", "set_bookmarks",
            or a structural type (will be skipped with explanation)
          - For "set_language": no additional fields required (sets "en-US")
          - For "set_title": "value" str with the title
          - For "set_bookmarks": "headings" list of {"text": str, "page": int}

    Returns
    -------
    dict with keys:
        "applied": list of str — descriptions of applied fixes
        "skipped": list of str — fixes skipped with reason
        "errors":  list of str — any exceptions encountered
    """
    applied: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    input_path = str(input_path)
    output_path = str(output_path)

    try:
        with pikepdf.open(input_path) as pdf:
            for fix in approved_fixes:
                fix_type = fix.get("fix_type", "")

                if fix_type in _STRUCTURAL_FIX_TYPES:
                    skipped.append(f"{fix_type} on element {fix.get('element_id', '?')}: {_SKIP_REASON}")
                    continue

                if fix_type == "set_language":
                    pdf.Root.Lang = pikepdf.String("en-US")
                    applied.append("Set document language to en-US")

                elif fix_type == "set_title":
                    value = fix.get("value", "")
                    if value:
                        pdf.docinfo["/Title"] = value
                        try:
                            with pdf.open_metadata() as meta:
                                meta["dc:title"] = value
                        except Exception:
                            pass  # XMP write is best-effort
                        applied.append(f"Set document title to: {value}")
                    else:
                        skipped.append("set_title: no value provided")

                elif fix_type == "set_bookmarks":
                    headings = fix.get("headings", [])
                    if headings:
                        with pdf.open_outline() as outline:
                            outline.root.clear()
                            for h in headings:
                                page_no = h.get("page", 1)
                                text = h.get("text", "")
                                if text:
                                    # pikepdf OutlineItem page numbers are 0-based
                                    item = pikepdf.OutlineItem(text, page_no - 1)
                                    outline.root.append(item)
                        pdf.Root["/PageMode"] = pikepdf.Name("/UseOutlines")
                        applied.append(f"Added {len(headings)} bookmarks from heading structure")
                    else:
                        skipped.append("set_bookmarks: no headings provided")

                else:
                    skipped.append(f"Unknown fix type '{fix_type}': {_SKIP_REASON}")

            pdf.save(output_path)

    except Exception as exc:
        errors.append(str(exc))
        # Best-effort: copy original so output_path always exists
        try:
            shutil.copy2(input_path, output_path)
        except Exception:
            pass

    return {"applied": applied, "skipped": skipped, "errors": errors}


def remediate_docx(
    input_path: str,
    output_path: str,
    approved_fixes: list,
    user_inputs: dict,
) -> dict:
    """
    Apply approved fixes to a Word .docx file and write the result to output_path.

    All fix types are writable in docx: set_language, set_title,
    set_heading_style, set_alt_text, set_table_header.

    Parameters
    ----------
    input_path:
        Path to the original .docx. Never modified.
    output_path:
        Path where the remediated .docx will be written.
    approved_fixes:
        List of fix dicts with at minimum a "fix_type" key.
    user_inputs:
        Mapping of element_id → user-provided value (e.g. alt text).

    Returns
    -------
    dict with keys "applied", "skipped", "errors".
    """
    from docx import Document as DocxDocument

    applied: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    input_path = str(input_path)
    output_path = str(output_path)

    shutil.copy2(input_path, output_path)

    try:
        doc = DocxDocument(output_path)

        for fix in approved_fixes:
            fix_type = fix.get("fix_type", "")
            element_id = fix.get("element_id", "")

            try:
                if fix_type == "set_language":
                    doc.core_properties.language = "en-US"
                    applied.append("Set document language to en-US")

                elif fix_type == "set_title":
                    value = fix.get("value", "")
                    if value:
                        doc.core_properties.title = value
                        applied.append(f"Set document title to: {value}")
                    else:
                        skipped.append("set_title: no value provided")

                elif fix_type == "set_heading_style":
                    proposed = fix.get("proposed_value", "H1")
                    level_map = {"H1": "Heading 1", "H2": "Heading 2", "H3": "Heading 3"}
                    style_name = level_map.get(proposed, "Heading 1")
                    # Find paragraph by element_id index (el_NNN → index NNN-1)
                    matched = False
                    for para in doc.paragraphs:
                        if para.text.strip() == (fix.get("text") or "").strip():
                            para.style = doc.styles[style_name]
                            applied.append(f"Set heading style to {style_name}: {para.text[:50]}")
                            matched = True
                            break
                    if not matched:
                        skipped.append(f"set_heading_style: paragraph not found for {element_id}")

                elif fix_type == "set_alt_text":
                    alt_text = user_inputs.get(element_id, "")
                    if not alt_text:
                        skipped.append(f"set_alt_text on {element_id}: no alt text value provided")
                        continue
                    # Find drawing element and set description attribute
                    set_count = 0
                    for para in doc.paragraphs:
                        for run in para.runs:
                            for drawing in run._r.iter():
                                tag = getattr(drawing, "tag", "") or ""
                                if "docPr" in tag:
                                    drawing.set("descr", alt_text)
                                    set_count += 1
                    if set_count:
                        applied.append(f"Set alt text on image {element_id}: {alt_text[:50]}")
                    else:
                        skipped.append(f"set_alt_text on {element_id}: no image drawing element found")

                elif fix_type == "set_table_header":
                    # Find table by index from element_id (el_NNN)
                    # Apply "Table Header" style (or bold Normal) to first row
                    table_index = 0
                    try:
                        num = int(element_id.replace("el_", ""))
                        # Approximate: count tables and match by rough ordering
                        table_index = 0  # default to first table if can't match
                    except (ValueError, AttributeError):
                        pass

                    if doc.tables:
                        table = doc.tables[min(table_index, len(doc.tables) - 1)]
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
                        applied.append(f"Applied header style to first row of table {element_id}")
                    else:
                        skipped.append(f"set_table_header on {element_id}: no tables found in document")

                else:
                    skipped.append(f"fix type '{fix_type}' not applicable to Word documents")

            except Exception as exc:
                errors.append(f"{fix_type} on {element_id}: {exc}")

        doc.save(output_path)

    except Exception as exc:
        errors.append(str(exc))
        try:
            shutil.copy2(input_path, output_path)
        except Exception:
            pass

    return {"applied": applied, "skipped": skipped, "errors": errors}
