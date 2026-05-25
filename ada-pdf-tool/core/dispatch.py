"""
Pipeline dispatch layer.

Three named pipeline functions share the same input contract:

    func(file_path, extraction, approved_fixes) -> str

Each applies the appropriate remediation strategy for its input type
and returns the path to the output file. The output may be a PDF (.pdf)
for tagged PDFs or a Word document (.docx) for untagged PDFs and docx.

Use get_pipeline(input_type) to select the right function by type name,
and get_last_result() to retrieve the applied/skipped/errors dict after
calling any pipeline function.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from core.models import AuditReport
from core.remediator import remediate as _remediate_pdf
from core.remediator import remediate_docx as _remediate_docx
from core.rebuilder import rebuild_as_docx


# Module-level result cache — set by each pipeline call, read by app.py
# via get_last_result(). Reset on every pipeline invocation.
_last_result: dict = {"applied": [], "skipped": [], "errors": []}


def get_last_result() -> dict:
    """Return the applied/skipped/errors dict from the most recent pipeline call."""
    return _last_result


def remediate_tagged_pdf(pdf_path: str, extraction: dict, approved_fixes: list) -> str:
    """
    Apply in-place PDF fixes (metadata, bookmarks) to a tagged PDF.

    Wraps the pikepdf remediator. Metadata (language, title) and bookmark
    fixes are written directly. Structural fixes that require tag-tree
    editing are not yet implemented and will be skipped.

    Parameters
    ----------
    pdf_path : str
        Path to the source PDF.
    extraction : dict
        Docling extraction dict (unused here; reserved for future tag-tree work).
    approved_fixes : list
        Approved fix list from Stage 3.

    Returns
    -------
    str — path to the remediated PDF.
    """
    global _last_result
    suffix = Path(pdf_path).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=f"_remediated{suffix}") as tmp:
        output_path = tmp.name
    _last_result = _remediate_pdf(pdf_path, output_path, approved_fixes)
    return output_path


def remediate_untagged_pdf(pdf_path: str, extraction: dict, approved_fixes: list) -> str:
    """
    Reconstruct an untagged PDF as a structured Word document.

    This is the only path that rebuilds the document from scratch.
    Returns a .docx path, not a PDF path. The caller (Stage 4) should
    present the output as a Word download and guide the user through
    re-exporting as a tagged PDF.

    TODO(B-E): Wire in fidelity improvements — actual image extraction,
    table cell content, fine-grained heading inference from font metadata,
    and user_inputs (alt text / equation descriptions).

    Parameters
    ----------
    pdf_path : str
        Path to the source PDF.
    extraction : dict
        Docling extraction dict passed directly to rebuild_as_docx.
    approved_fixes : list
        Approved fix list from Stage 3. Metadata fixes (set_language,
        set_title) are forwarded to the rebuilt document.

    Returns
    -------
    str — path to the reconstructed .docx.
    """
    global _last_result

    # Lift metadata fixes from approved_fixes into the stub AuditReport
    # so the rebuilder applies title/language to the output docx.
    metadata_fixes: list[dict] = []
    for fix in approved_fixes:
        if fix.get("fix_type") == "set_language":
            metadata_fixes.append({"field": "language", "value": "en-US"})
        elif fix.get("fix_type") == "set_title":
            val = fix.get("value", "")
            if val:
                metadata_fixes.append({"field": "title", "value": val})

    stub_report = AuditReport(
        findings=[],
        preserve=[],
        metadata_fixes=metadata_fixes,
    )

    # TODO(B-E): user_inputs (alt text, equation descriptions) are not yet
    # threaded through this signature. Passing {} for now means images and
    # equations will show placeholder text in the rebuilt document.
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        output_path = tmp.name

    rebuild_as_docx(
        extraction,
        stub_report,
        {},
        output_path,
        pdf_path=pdf_path,
        approved_fixes=approved_fixes,
    )

    applied_descs = ["Reconstructed document structure from PDF content"]
    if metadata_fixes:
        applied_descs.append(f"Applied {len(metadata_fixes)} metadata fix(es) to rebuilt document")

    _last_result = {"applied": applied_descs, "skipped": [], "errors": []}
    return output_path


def remediate_docx(docx_path: str, extraction: dict, approved_fixes: list) -> str:
    """
    Apply in-place fixes to a Word document.

    Wraps the python-docx remediator. All structural fix types
    (headings, alt text, table headers, language, title) are writable.

    TODO(B-E): user_inputs (alt text values provided in Stage 2) are not
    yet threaded through this signature. Passing {} for now means
    set_alt_text fixes will be skipped. Extend approved_fixes entries to
    include pre-resolved values, or add user_inputs to the contract.

    Parameters
    ----------
    docx_path : str
        Path to the source .docx.
    extraction : dict
        Docling extraction dict (unused here; reserved for future work).
    approved_fixes : list
        Approved fix list from Stage 3.

    Returns
    -------
    str — path to the remediated .docx.
    """
    global _last_result
    with tempfile.NamedTemporaryFile(delete=False, suffix="_remediated.docx") as tmp:
        output_path = tmp.name
    # TODO(B-E): pass real user_inputs once threaded through signature
    _last_result = _remediate_docx(docx_path, output_path, approved_fixes, {})
    return output_path


def get_pipeline(input_type: str):
    """
    Return the pipeline function for a given input type string.

    Parameters
    ----------
    input_type : str
        One of "tagged_pdf", "untagged_pdf", or "docx".

    Returns
    -------
    callable with signature (file_path, extraction, approved_fixes) -> str
    """
    pipelines = {
        "tagged_pdf": remediate_tagged_pdf,
        "untagged_pdf": remediate_untagged_pdf,
        "docx": remediate_docx,
    }
    if input_type not in pipelines:
        raise ValueError(f"Unknown input type: {input_type!r}. Expected one of {list(pipelines)}")
    return pipelines[input_type]
