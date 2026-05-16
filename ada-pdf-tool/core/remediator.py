"""
Remediation layer — applies approved fixes to a PDF using pikepdf.

Only metadata fixes (language, title) and bookmark generation can be
applied programmatically. Structural fixes (heading tags, alt text,
link tags, table headers) require editing the source document.
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
