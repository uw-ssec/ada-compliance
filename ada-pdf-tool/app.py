"""
ADA Document Accessibility Auditor — Streamlit application.

Four stages:
  1. Upload
  2. Audit Results
  3. Review and Approve Fixes
  4. Download
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Suppress noisy transformers __path__ alias warnings before any imports
# load the transformers library (docling transitive dependency).
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")

# Allow running from ada-pdf-tool/ without installing as a package
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from streamlit.errors import StreamlitDuplicateElementKey

load_dotenv()

from core.analyzer import analyze
from core.backends.hyak_backend import HyakBackend, HyakGatewayError
from core.diff_reporter import generate_diff_report
from core.dispatch import get_last_result, get_pipeline, remediate_untagged_pdf
from core.extractor import extract, extract_docx, is_tagged_pdf, render_element_thumbnail
from core.models import AuditReport, Finding
from core.remediator import validate_fixes

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ADA Document Accessibility Auditor",
    page_icon="♿",
    layout="wide",
)

# ── Session state init ─────────────────────────────────────────────────────────
_KEYS = [
    "stage", "extraction", "audit_report", "uploaded_filename",
    "uploaded_bytes", "user_inputs", "approved_fixes", "remediated_path",
    "diff_report_path", "applied_fixes", "audit_csv", "structural_items",
    "file_type", "pdf_subtype", "detection_message", "source_docx_path",
    "pdf_path", "thumbnails", "user_notes", "heading_levels", "validation_result",
    "skipped_by_user",
]

if "stage" not in st.session_state:
    st.session_state.stage = 1
if "user_inputs" not in st.session_state:
    st.session_state.user_inputs = {}
if "approved_fixes" not in st.session_state:
    st.session_state.approved_fixes = []
if "thumbnails" not in st.session_state:
    st.session_state.thumbnails = {}
if "user_notes" not in st.session_state:
    st.session_state.user_notes = {}
if "heading_levels" not in st.session_state:
    st.session_state.heading_levels = {}


def _reset():
    # Clean up the persistent PDF temp file used for thumbnail rendering
    pdf_path = st.session_state.get("pdf_path")
    if pdf_path:
        try:
            os.unlink(pdf_path)
        except OSError:
            pass
    for key in _KEYS:
        if key in st.session_state:
            del st.session_state[key]
    st.session_state.stage = 1
    st.session_state.user_inputs = {}
    st.session_state.approved_fixes = []
    st.session_state.thumbnails = {}
    st.session_state.user_notes = {}
    st.session_state.heading_levels = {}


def _trunc(text: str | None, n: int = 60) -> str:
    s = str(text or "")
    return s[:n] + "…" if len(s) > n else s


def _get_element_thumbnail(el: dict, pdf_path: str, page_number: int) -> bytes | None:
    """
    Return cached thumbnail bytes for any element with a bbox, or None.

    Applies type-specific bbox adjustments:
    - text / link: 5pt padding, raw bbox used
    - table: crop to top 150pts if taller than 200pts
    - image / formula: bbox as-is
    Wraps render_element_thumbnail in try/except; returns None on failure.
    """
    bbox = el.get("bbox")
    if not bbox:
        return None
    el_type = el.get("type", "text")
    el_label = el.get("docling_label", "")

    # Adjust bbox by element type
    x0, y0, x1, y1 = bbox[0], bbox[1], bbox[2], bbox[3]
    if el_type == "table":
        height = abs(y0 - y1)  # docling y is bottom-origin, y0 > y1 means y0=top, y1=bottom
        # If bbox height > 200pts, restrict to top 150pts
        if height > 200:
            # y0 is the top (larger value in bottom-origin coords), y1 is the bottom
            # Show top 150pts: new bottom = y0 - 150
            y1 = max(y1, y0 - 150)
        render_bbox = [x0, y0, x1, y1]
    elif el_type in ("text", "link") or el_label in (
        "text", "paragraph", "section_header", "title", "list_item", "caption",
        "footnote", "page_header", "page_footer", "code",
    ):
        # Add 5pt padding
        render_bbox = [x0 - 5, y0 + 5, x1 + 5, y1 - 5]
    else:
        render_bbox = [x0, y0, x1, y1]

    cache_key = f"{el.get('id', '')}_{page_number}"
    cached = st.session_state.thumbnails.get(cache_key)
    if cached is not None:
        return cached
    try:
        thumb = render_element_thumbnail(pdf_path, page_number, render_bbox)
        st.session_state.thumbnails[cache_key] = thumb
        return thumb
    except Exception:
        return None


def _infer_level_from_proposed_fix(proposed_fix: str | None) -> int:
    """Extract heading level digit from strings like 'Tag as H2' or 'Heading 2'."""
    import re
    if proposed_fix:
        m = re.search(r"[Hh](\d)", proposed_fix)
        if m:
            level = int(m.group(1))
            if 1 <= level <= 4:
                return level
    return 2


def _badge(label: str, color: str) -> str:
    return f'<span style="background:{color};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;margin-left:6px;">{label}</span>'


def _severity_color(sev: str) -> str:
    return {"critical": "#dc2626", "serious": "#ea580c", "moderate": "#d97706", "minor": "#6b7280"}.get(sev, "#6b7280")


def _page_label(page) -> str:
    """Return 'Document metadata' for page 0/None, else 'Page N'."""
    if not page or page == 0:
        return "Document metadata"
    return f"Page {page}"


def _confidence_badge(confidence: str | None) -> str:
    if confidence == "high":
        return (
            '<span style="background-color: #1a7f37; color: white; padding: 2px 8px; '
            'border-radius: 4px; font-size: 12px; font-weight: 500;">high</span>'
        )
    elif confidence == "medium":
        return (
            '<span style="background-color: #bf8700; color: white; padding: 2px 8px; '
            'border-radius: 4px; font-size: 12px; font-weight: 500;">medium</span>'
        )
    else:
        return ""  # None, null, or anything else — no badge shown


def _is_heading_selector_finding(f: Finding, element_lookup: dict, file_type: str) -> bool:
    """Return True for 1.3.1 text/image findings on untagged PDFs — these get H1-H4 picker."""
    if f.wcag_criterion != "1.3.1":
        return False
    if file_type != "pdf":
        return False
    el = element_lookup.get(f.element_id, {})
    return el.get("type") in ("text", "image")


def _is_pdf_structural(f: Finding) -> bool:
    """Return True if this auto-fix finding cannot be written directly into a PDF."""
    return (
        f.wcag_criterion != "3.1.1"
        and f.wcag_criterion != "2.4.2"
        and "bookmark" not in (f.proposed_fix or "").lower()
    )


def _needs_user_input(f: Finding) -> bool:
    """Return True only for findings where the user types the fix value."""
    return f.wcag_criterion in ("1.1.1", "2.4.4", "3.1.2")


def _word_instruction(f: Finding) -> str:
    """Return a criterion-specific Word editing instruction for a finding."""
    criterion = getattr(f, "wcag_criterion", "") or ""
    page = getattr(f, "page", "?")

    instructions = {
        "1.1.1": (
            f"In Word: click the image on or near page {page} → "
            "right-click → 'Edit Alt Text' → type a description "
            "of what the image shows → click outside to save."
        ),
        "1.3.1": (
            (
                f"In Word: click inside the table on or near page {page} "
                "→ click the first row to select it → go to Table Design tab "
                "→ check 'Header Row' in the Table Style Options group."
            )
            if any(
                kw in (getattr(f, "current_state", "") or "").lower()
                or kw in (getattr(f, "proposed_fix", "") or "").lower()
                for kw in ("table", "header row", "column header")
            )
            else (
                f"In Word: select the heading text on or near page {page} "
                "→ in the Home tab, apply the correct Heading style "
                "(Heading 1, Heading 2 etc.) from the Styles panel."
            )
        ),
        "1.3.2": (
            f"In Word: review the reading order on page {page}. "
            "Cut and paste any out-of-order content into the correct "
            "position in the document flow."
        ),
        "1.4.5": (
            f"On page {page}: this image may contain text. If possible, "
            "replace it with real text in the document, or add alt text "
            "describing the text content of the image."
        ),
        "2.4.4": (
            f"In Word: find the hyperlink on or near page {page} → "
            "right-click → 'Edit Hyperlink' → change the display text "
            "to something descriptive (e.g. 'UW Accessibility Guide' "
            "instead of 'click here')."
        ),
        "2.4.6": (
            f"In Word: find the heading on page {page} → rewrite it "
            "to describe the section content (e.g. 'Methodology' "
            "instead of 'Section 3')."
        ),
        "3.1.2": (
            f"In Word: select the non-English text on page {page} → "
            "go to Review tab → Language → Set Proofing Language → "
            "choose the correct language."
        ),
    }
    return instructions.get(
        criterion,
        f"In Word: manually review and fix the issue on or near "
        f"page {page} per WCAG criterion {criterion}.",
    )


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 1 — Upload
# ══════════════════════════════════════════════════════════════════════════════
def stage_1():
    st.title("ADA Document Accessibility Auditor")
    st.markdown("Upload a PDF or Word document to audit for WCAG 2.1 AA compliance.")

    uploaded = st.file_uploader(
        "Upload your PDF or Word document (.pdf or .docx)",
        type=["pdf", "docx"],
        help="Programmatic PDFs and Word .docx files are supported. Scanned PDFs are not supported.",
    )

    if uploaded is None:
        return

    suffix = Path(uploaded.name).suffix.lower()
    file_bytes = uploaded.read()

    # ── Early untagged-PDF detection ──────────────────────────────────────────
    # Run is_tagged_pdf before the Analyze button so the source-docx uploader
    # can be rendered while the user is still on Stage 1.
    source_docx = None
    early_subtype: str | None = None

    if suffix == ".pdf":
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as peek_tmp:
            peek_tmp.write(file_bytes)
            peek_path = peek_tmp.name
        try:
            early_subtype = "tagged_pdf" if is_tagged_pdf(peek_path) else "untagged_pdf"
        finally:
            try:
                os.unlink(peek_path)
            except OSError:
                pass

        if early_subtype == "untagged_pdf":
            source_docx = st.file_uploader(
                "Do you have the original Word document for this PDF? "
                "Upload it for the most faithful output.",
                type=["docx"],
                key="source_docx_upload",
            )
            st.info(
                "This PDF has no accessibility tag tree. The tool will "
                "rebuild it as a properly structured Word document. "
                "If you still have the original Word file this PDF was "
                "created from, uploading it improves the output — but "
                "it's not required."
            )

    if st.button("Analyze Document", type="primary"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        # Use early detection result; fall back to re-checking if needed
        if suffix == ".pdf":
            pdf_subtype = early_subtype or ("tagged_pdf" if is_tagged_pdf(tmp_path) else "untagged_pdf")
        else:
            pdf_subtype = "docx"

        # Write source docx to a temp file if provided
        source_docx_path: str | None = None
        if source_docx is not None:
            source_docx_bytes = source_docx.read()
            with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as src_tmp:
                src_tmp.write(source_docx_bytes)
                source_docx_path = src_tmp.name

        _DETECTION_MESSAGES = {
            "tagged_pdf": "Tagged PDF detected — fixes will be written directly to the PDF.",
            "untagged_pdf": (
                "No tag tree detected — this document will be reconstructed "
                "as Word for remediation."
            ),
            "docx": "Word document detected — fixes will be written directly.",
        }
        detection_message = _DETECTION_MESSAGES[pdf_subtype]
        if pdf_subtype == "untagged_pdf" and source_docx_path:
            detection_message = (
                "Source Word document detected — audit findings from the PDF will "
                "be applied to your Word document for the most complete remediation."
            )

        try:
            with st.status("Analyzing document…", expanded=True) as status:
                if pdf_subtype == "untagged_pdf" and source_docx_path:
                    st.write("Step 1 of 2: Reading PDF structure for audit…")
                else:
                    st.write("Step 1 of 2: Reading document structure…")

                if suffix == ".pdf":
                    extraction = extract(tmp_path)
                elif suffix == ".docx":
                    extraction = extract_docx(tmp_path)
                else:
                    st.error(f"Unsupported file type: {suffix}")
                    return

                # Scanned PDF guard (docx always has elements)
                total_elements = sum(len(p.get("elements", [])) for p in extraction.get("pages", []))
                if total_elements == 0 and suffix == ".pdf":
                    st.error(
                        "This appears to be a scanned PDF. This tool requires a programmatic PDF "
                        "with embedded text. Scanned documents are not supported."
                    )
                    return

                if source_docx_path:
                    st.write("Step 1b: Reading source Word document…")
                    # extract_docx result is not needed for audit; path is stored for remediation

                st.write("Step 2 of 2: Auditing for accessibility issues…")
                backend = HyakBackend()
                audit_report = analyze(extraction, backend)
                status.update(label="Analysis complete", state="complete", expanded=False)

        except HyakGatewayError as exc:
            st.error(
                str(exc)
                + "\n\nTip: set `HYAK_ENDPOINT_URL=https://api.anthropic.com/v1` "
                "and `HYAK_MODEL=claude-sonnet-4-5-20251001` to use the Anthropic API directly."
            )
            return
        except ValueError as exc:
            st.error(str(exc))
            return
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        # Write a persistent copy of the PDF for thumbnail rendering in Stage 2/3.
        # This file is cleaned up by _reset() when the user starts a new session.
        pdf_path: str | None = None
        if suffix == ".pdf":
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as pdf_persist:
                pdf_persist.write(file_bytes)
                pdf_path = pdf_persist.name

        st.session_state.extraction = extraction
        st.session_state.audit_report = audit_report
        st.session_state.uploaded_filename = uploaded.name
        st.session_state.uploaded_bytes = file_bytes
        st.session_state.file_type = extraction.get("file_type", "pdf")
        st.session_state.pdf_subtype = pdf_subtype
        st.session_state.detection_message = detection_message
        st.session_state.source_docx_path = source_docx_path
        st.session_state.pdf_path = pdf_path
        st.session_state.stage = 2
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 2 — Audit Results
# ══════════════════════════════════════════════════════════════════════════════
def stage_2():
    report: AuditReport = st.session_state.audit_report
    filename: str = st.session_state.uploaded_filename
    file_type: str = st.session_state.get("file_type", "pdf")
    pdf_subtype: str = st.session_state.get("pdf_subtype", "tagged_pdf")

    # Build element lookup for heading selector classification
    _el_lookup: dict = {}
    for _pg in st.session_state.get("extraction", {}).get("pages", []):
        for _el in _pg.get("elements", []):
            _el_lookup[_el["id"]] = _el

    # Reclassify 1.3.1 text/image findings on untagged PDFs as auto-fix
    # so they appear in the auto-fix section with H1-H4 picker (do once).
    # Also promote table header findings (1.3.1, type==table) for both
    # untagged PDF and docx paths — rebuilder/remediator both handle it.
    _to_promote = []
    for _f in report.human_review:
        _el_f = _el_lookup.get(_f.element_id, {})
        if _is_heading_selector_finding(_f, _el_lookup, file_type):
            _to_promote.append(_f)
        elif (
            _f.wcag_criterion == "1.3.1"
            and _el_f.get("type") == "table"
            and (file_type == "docx" or pdf_subtype == "untagged_pdf")
        ):
            if not _f.proposed_fix:
                _f.proposed_fix = "Mark first row as header row"
            _to_promote.append(_f)
    if _to_promote:
        for _f in _to_promote:
            _f.classification = "auto-fix"
        report.human_review = [f for f in report.human_review if f not in _to_promote]
        report.auto_fix = list(report.auto_fix) + _to_promote

    # Deduplicate both lists by (element_id, wcag_criterion) to prevent
    # duplicate widget keys if the LLM returns the same finding twice or
    # if reclassification adds a finding already present in auto_fix.
    def _dedup(findings: list) -> list:
        seen: set = set()
        out = []
        for _f in findings:
            _k = (_f.element_id, _f.wcag_criterion)
            if _k not in seen:
                seen.add(_k)
                out.append(_f)
        return out

    report.auto_fix = _dedup(report.auto_fix)
    report.human_review = _dedup(report.human_review)

    st.title(f"Audit Results — {filename}")

    detection_message = st.session_state.get("detection_message")
    if detection_message:
        st.info(detection_message)

    # ── Confidence legend ─────────────────────────────────────────────────
    with st.expander("What do these labels mean?", expanded=False):
        st.markdown(
            "**🟢 High confidence**  \n"
            "The tool is certain this is a real violation and the proposed fix is correct. "
            "Applied automatically in Stage 3 by default.\n\n"
            "**🟡 Medium confidence**  \n"
            "The tool detected an issue but recommends human review before applying. "
            "Unchecked by default in Stage 3.\n\n"
            "**⚪ Requires human input**  \n"
            "Cannot be auto-fixed. The tool explains what needs to be done and asks for "
            "input where possible (e.g. alt text descriptions)."
        )
        st.caption(
            "Findings in the Human Input section are grouped by check type: "
            "**automated** (pass/fail rule check), **manual** (requires human judgment), "
            "**hybrid** (partially automatable with a tool assist)."
        )

    # ── Auto-fixable ──────────────────────────────────────────────────────
    n_auto = len(report.auto_fix)
    with st.expander(f"🔴 Auto-Fixable Issues ({n_auto} found)", expanded=True):
        if not report.auto_fix:
            st.info("No auto-fixable issues found.")
        for f in report.auto_fix:
            label = f"{_page_label(f.page)} — {f.wcag_criterion} — {_trunc(f.current_state)}"
            with st.expander(label):
                st.markdown(f"**Page:** {_page_label(f.page)}")
                st.markdown(f"**Current state:** {f.current_state}")
                st.markdown(f"**Proposed fix:** {f.proposed_fix}")
                st.markdown(
                    f"**WCAG criterion:** [{f.wcag_criterion}](https://www.w3.org/TR/WCAG21/)"
                )
                _cbadge = _confidence_badge(f.confidence)
                if _cbadge:
                    st.markdown(f"**Confidence:** {_cbadge}", unsafe_allow_html=True)
                st.markdown(f"**Reasoning:** {f.reasoning}")

                # Thumbnail for auto-fix elements with bbox (PDF only)
                if st.session_state.get("pdf_path"):
                    _af_thumb_el = _el_lookup.get(f.element_id, {})
                    _af_thumb_page = f.page
                    for _pg_af in st.session_state.extraction.get("pages", []):
                        for _el_af in _pg_af.get("elements", []):
                            if _el_af.get("id") == f.element_id:
                                _af_thumb_el = _el_af
                                _af_thumb_page = _pg_af.get("page_number", f.page)
                                break
                    if _af_thumb_el.get("bbox"):
                        _af_thumb = _get_element_thumbnail(
                            _af_thumb_el, st.session_state.pdf_path, _af_thumb_page
                        )
                        if _af_thumb:
                            _col_c, _col_t = st.columns([2, 1])
                            with _col_t:
                                st.image(_af_thumb, width=250)

                # H1-H4 picker for heading findings on untagged PDFs
                if _is_heading_selector_finding(f, _el_lookup, file_type):
                    _hl = st.session_state.heading_levels
                    _current_level = _hl.get(
                        f.element_id,
                        _infer_level_from_proposed_fix(f.proposed_fix),
                    )
                    st.write("Inferred heading level:")
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        if st.button("H1", key=f"h1_{f.element_id}"):
                            st.session_state.heading_levels[f.element_id] = 1
                            _current_level = 1
                    with col2:
                        if st.button("H2", key=f"h2_{f.element_id}"):
                            st.session_state.heading_levels[f.element_id] = 2
                            _current_level = 2
                    with col3:
                        if st.button("H3", key=f"h3_{f.element_id}"):
                            st.session_state.heading_levels[f.element_id] = 3
                            _current_level = 3
                    with col4:
                        if st.button("H4", key=f"h4_{f.element_id}"):
                            st.session_state.heading_levels[f.element_id] = 4
                            _current_level = 4
                    _level_colors = {1: "#1d4ed8", 2: "#0891b2", 3: "#059669", 4: "#7c3aed"}
                    _lc = _level_colors.get(_current_level, "#6b7280")
                    st.markdown(
                        f'Selected: <span style="background:{_lc};color:#fff;padding:2px 10px;'
                        f'border-radius:4px;font-size:13px;font-weight:700;">H{_current_level}</span>',
                        unsafe_allow_html=True,
                    )

    # ── Human review ──────────────────────────────────────────────────────
    n_human = len(report.human_review)
    with st.expander(f"🟡 Requires Human Input ({n_human} items)", expanded=True):
        if not report.human_review:
            st.info("No items require human input.")

        def _render_human_finding(f: Finding) -> None:
            el_label = f"{_page_label(f.page)} — {f.wcag_criterion} — {_trunc(f.current_state)}"
            with st.expander(el_label):
                st.markdown(f"**Detected:** {f.current_state}")
                st.markdown(f"**Why human input is needed:** {f.reasoning}")
                st.markdown(
                    f"**WCAG criterion:** [{f.wcag_criterion}](https://www.w3.org/TR/WCAG21/)"
                )

                # ── Thumbnail for all element types (PDF only) ───────────
                if st.session_state.get("pdf_path"):
                    _thumb_el = _el_lookup.get(f.element_id, {})
                    _thumb_page = f.page
                    for _pg in st.session_state.extraction.get("pages", []):
                        for _el in _pg.get("elements", []):
                            if _el.get("id") == f.element_id:
                                _thumb_el = _el
                                _thumb_page = _pg.get("page_number", f.page)
                                break
                    if _thumb_el.get("bbox"):
                        _thumb = _get_element_thumbnail(
                            _thumb_el, st.session_state.pdf_path, _thumb_page
                        )
                        if _thumb:
                            st.image(_thumb, width=250)

                if f.wcag_criterion == "1.4.5":
                    st.caption(
                        "WCAG 1.4.5: if this image contains text that conveys information "
                        "(e.g., a chart label, a data value), make sure that same text is also "
                        "available as readable text in your source document near this image. "
                        "If the text in the image is purely decorative or a logo, no action is needed."
                    )

                elif _needs_user_input(f):
                    if f.element_subtype == "equation":
                        st.warning(f.human_prompt or "Describe this equation.")
                        input_label = "Describe this equation:"
                    elif f.human_prompt:
                        st.info(f.human_prompt)
                        input_label = "Provide accessible alternative:"
                    elif "picture" in (f.current_state or "").lower() or f.wcag_criterion == "1.1.1":
                        input_label = "Describe this image:"
                    elif "link" in (f.current_state or "").lower():
                        input_label = "Enter descriptive link text:"
                    else:
                        input_label = "Provide accessible alternative:"

                    input_key = f"input_{f.element_id}_{f.wcag_criterion.replace('.', '_')}"
                    value = st.text_input(
                        input_label,
                        key=input_key,
                        value=st.session_state.user_inputs.get(f.element_id, ""),
                    )
                    if value:
                        st.session_state.user_inputs[f.element_id] = value
                else:
                    # Skip manual Word instruction for PDF heading findings —
                    # those are handled by the H1-H4 selector in the auto-fix section.
                    _skip_word_instr = (
                        file_type == "pdf"
                        and f.wcag_criterion == "1.3.1"
                        and _el_lookup.get(f.element_id, {}).get("type") in ("text", "image")
                    )
                    if not _skip_word_instr:
                        st.caption(_word_instruction(f))

        # Sub-group by check_type
        _automated_findings = [f for f in report.human_review if getattr(f, "check_type", None) == "automated"]
        _manual_findings = [f for f in report.human_review if getattr(f, "check_type", None) == "manual"]
        _hybrid_findings = [f for f in report.human_review if getattr(f, "check_type", None) == "hybrid"]
        _untyped_findings = [
            f for f in report.human_review
            if getattr(f, "check_type", None) not in ("automated", "manual", "hybrid")
        ]

        if _automated_findings:
            st.markdown("**Automated checks (pass/fail)**")
            for f in _automated_findings:
                _render_human_finding(f)

        if _manual_findings:
            st.markdown("**Requires human judgment**")
            for f in _manual_findings:
                _render_human_finding(f)

        if _hybrid_findings:
            st.markdown("**Partially automatable**")
            for f in _hybrid_findings:
                _render_human_finding(f)

        # Fall-through: findings with no check_type set (older LLM responses)
        for f in _untyped_findings:
            _render_human_finding(f)

    # ── Already correct ───────────────────────────────────────────────────
    if report.preserve_findings:
        n_preserve = len(report.preserve_findings)
        with st.expander(f"✅ Already Correct ({n_preserve} items)", expanded=False):
            for f in report.preserve_findings:
                st.markdown(f"- **{f.wcag_criterion}** (page {f.page}): {f.current_state}")

    # ── Exception notice ──────────────────────────────────────────────────
    for f in report.info:
        if f.wcag_criterion == "exception":
            st.info(
                "📋 Exception notice: "
                + (f.current_state or "")
                + "\n\nThis is for your awareness only and does not affect the findings above."
            )

    st.divider()
    if st.button("Continue to Review →", type="primary"):
        st.session_state.stage = 3
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 3 — Review and Approve
# ══════════════════════════════════════════════════════════════════════════════
def stage_3():
    report: AuditReport = st.session_state.audit_report
    user_inputs: dict = st.session_state.user_inputs
    pdf_subtype: str = st.session_state.get("pdf_subtype", "tagged_pdf")

    # Deduplicate findings before rendering to prevent duplicate widget keys
    seen_ids: set = set()
    deduped_auto: list = []
    for _df in report.auto_fix:
        _dk = f"{_df.element_id}_{_df.wcag_criterion}"
        if _dk not in seen_ids:
            seen_ids.add(_dk)
            deduped_auto.append(_df)
    report.auto_fix = deduped_auto

    seen_ids = set()
    deduped_human: list = []
    for _df in report.human_review:
        _dk = f"{_df.element_id}_{_df.wcag_criterion}"
        if _dk not in seen_ids:
            seen_ids.add(_dk)
            deduped_human.append(_df)
    report.human_review = deduped_human

    if st.button("← Back to Audit Report"):
        st.session_state.stage = 2
        st.rerun()

    st.title("Review and Approve Fixes")
    st.caption("Nothing will be written to your file until you click Apply Selected Fixes.")

    # ── Select All / Deselect All ─────────────────────────────────────────
    col1, col2, _ = st.columns([1, 1, 6])
    with col1:
        if st.button("Select All"):
            for _idx, _f in enumerate(report.auto_fix):
                st.session_state[f"chk_af_{_f.element_id}_{_idx}"] = True
            for _idx, _eid in enumerate(user_inputs):
                st.session_state[f"chk_ui_{_eid}_{_idx}"] = True
    with col2:
        if st.button("Deselect All"):
            for _idx, _f in enumerate(report.auto_fix):
                st.session_state[f"chk_af_{_f.element_id}_{_idx}"] = False
            for _idx, _eid in enumerate(user_inputs):
                st.session_state[f"chk_ui_{_eid}_{_idx}"] = False

    st.divider()

    checked_ids: list[str] = []

    # ── Auto-fix checkboxes ───────────────────────────────────────────────
    # Build element lookup for Stage 3 thumbnails
    _s3_el_lookup: dict = {}
    _s3_page_lookup: dict = {}
    for _pg3 in st.session_state.get("extraction", {}).get("pages", []):
        for _el3 in _pg3.get("elements", []):
            _s3_el_lookup[_el3["id"]] = _el3
            _s3_page_lookup[_el3["id"]] = _pg3.get("page_number", 1)

    for idx, f in enumerate(report.auto_fix):
        conf = f.confidence or "medium"
        default = conf == "high"
        label = f"{_page_label(f.page)} — {_trunc(f.current_state)} → {f.proposed_fix}"

        _fix_key = f"chk_af_{f.element_id}_{idx}"

        # Thumbnail for PDF elements with bbox
        _s3_thumb: bytes | None = None
        if st.session_state.get("pdf_path"):
            _s3_el_item = _s3_el_lookup.get(f.element_id, {})
            if _s3_el_item.get("bbox"):
                _s3_thumb = _get_element_thumbnail(
                    _s3_el_item,
                    st.session_state.pdf_path,
                    _s3_page_lookup.get(f.element_id, f.page),
                )

        _note_key = f"note_af_{f.element_id}_{idx}"
        if _s3_thumb is not None:
            col_check, col_thumb, col_note = st.columns([2, 1, 2], gap="small")
            with col_check:
                checked = st.checkbox(
                    label,
                    value=st.session_state.get(_fix_key, default),
                    key=_fix_key,
                    help=f"WCAG {f.wcag_criterion} | Confidence: {conf}",
                )
            with col_thumb:
                st.image(_s3_thumb, width=70)
            with col_note:
                _note_val = st.text_input(
                    "",
                    placeholder="Add a note (saved to CSV)",
                    key=_note_key,
                    label_visibility="collapsed",
                )
                if _note_val:
                    st.session_state.user_notes[f.element_id] = _note_val
        else:
            col_fix, col_note = st.columns([3, 2])
            with col_fix:
                checked = st.checkbox(
                    label,
                    value=st.session_state.get(_fix_key, default),
                    key=_fix_key,
                    help=f"WCAG {f.wcag_criterion} | Confidence: {conf}",
                )
            with col_note:
                _note_val = st.text_input(
                    "",
                    placeholder="Add a note (saved to CSV)",
                    key=_note_key,
                    label_visibility="collapsed",
                )
                if _note_val:
                    st.session_state.user_notes[f.element_id] = _note_val
        if checked:
            checked_ids.append(_fix_key)

        if pdf_subtype == "tagged_pdf" and _is_pdf_structural(f):
            st.markdown(
                '<span style="background:#d97706;color:#fff;padding:2px 6px;'
                'border-radius:4px;font-size:11px;font-weight:600;">'
                "[Manual fix required]</span>"
                ' <span style="color:#6b7280;font-size:12px;">'
                "Cannot be written into this PDF — fix in source document</span>",
                unsafe_allow_html=True,
            )

    # ── User-provided values ──────────────────────────────────────────────
    for idx, (eid, val) in enumerate(user_inputs.items()):
        if not val:
            continue
        # Find the original finding for page context
        finding = next((x for x in report.human_review if x.element_id == eid), None)
        page_str = str(finding.page) if finding else "?"
        el_text = _trunc(finding.current_state if finding else eid)
        label = f"Page {page_str} — {el_text} → User provided: {val}"

        # Attempt to show thumbnail for any element with a bbox (PDF only)
        thumb: bytes | None = None
        if finding and st.session_state.get("pdf_path"):
            _s3_el: dict = {}
            _s3_page = finding.page
            for _pg in st.session_state.extraction.get("pages", []):
                for _el in _pg.get("elements", []):
                    if _el.get("id") == eid:
                        _s3_el = _el
                        _s3_page = _pg.get("page_number", finding.page)
                        break
            if _s3_el.get("bbox"):
                thumb = _get_element_thumbnail(_s3_el, st.session_state.pdf_path, _s3_page)

        _user_note_key = f"note_ui_{eid}_{idx}"
        if thumb is not None:
            col_check, col_thumb, col_note = st.columns([2, 1, 2], gap="small")
            with col_check:
                checked = st.checkbox(
                    label,
                    value=st.session_state.get(f"chk_ui_{eid}_{idx}", True),
                    key=f"chk_ui_{eid}_{idx}",
                )
            with col_thumb:
                st.image(thumb, width=70)
            with col_note:
                _user_note_val = st.text_input(
                    "",
                    placeholder="Add a note (saved to CSV)",
                    key=_user_note_key,
                    label_visibility="collapsed",
                )
                if _user_note_val:
                    st.session_state.user_notes[eid] = _user_note_val
        else:
            col_fix, col_note = st.columns([3, 2])
            with col_fix:
                checked = st.checkbox(
                    label,
                    value=st.session_state.get(f"chk_ui_{eid}_{idx}", True),
                    key=f"chk_ui_{eid}_{idx}",
                )
            with col_note:
                _user_note_val = st.text_input(
                    "",
                    placeholder="Add a note (saved to CSV)",
                    key=_user_note_key,
                    label_visibility="collapsed",
                )
                if _user_note_val:
                    st.session_state.user_notes[eid] = _user_note_val
        if checked:
            checked_ids.append(f"chk_ui_{eid}_{idx}")

    # ── Skipped / no-input items ──────────────────────────────────────────
    # Items where the user typed alt text in Stage 2 but the finding is still
    # in human_review (not promoted to auto_fix) must show as checkable rows.
    # Items with genuinely no input show a descriptive greyed label.
    manual_count = 0
    for f in report.human_review:
        eid = f.element_id
        user_val = (user_inputs.get(eid) or "").strip()

        if user_val:
            # Already counted via user_inputs loop above — skip duplicate render
            pass
        else:
            manual_count += 1
            _el_item = _s3_el_lookup.get(eid, {})
            _el_text = (_el_item.get("text") or "").strip()
            _label_type = (
                "equation" if f.element_subtype == "equation"
                else _el_item.get("type", "element")
            )
            st.markdown(
                f'<span style="color:#6b7280;">— {_page_label(f.page)} — {f.wcag_criterion} '
                f"— {_label_type}"
                + (f": {_el_text[:40]}" if _el_text else " (no text)")
                + " — no fix provided, manual remediation required</span>",
                unsafe_allow_html=True,
            )

    # ── Live summary ──────────────────────────────────────────────────────
    n_selected = len(checked_ids)
    n_skipped = (len(report.auto_fix) + len([v for v in user_inputs.values() if v])) - n_selected
    st.markdown(
        f"**{n_selected} fixes selected · {max(0, n_skipped)} skipped · {manual_count} require manual follow-up**"
    )

    st.divider()

    if st.button("Apply Selected Fixes", type="primary"):
        suffix = Path(st.session_state.uploaded_filename).suffix.lower()
        file_bytes: bytes = st.session_state.uploaded_bytes

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_in:
            tmp_in.write(file_bytes)
            input_path = tmp_in.name

        # Separate approved fixes into writable vs structural-only buckets.
        # For untagged PDFs, all fixes pass through to the rebuilder.
        # For tagged PDFs, structural fixes that require a tag tree go to
        # structural_items (manual follow-up). For docx, all are writable.
        actually_fixable: list[dict] = []
        structural_items: list[dict] = []

        # Build O(1) element lookup so each finding can carry indexing fields.
        element_lookup: dict[str, dict] = {}
        for _pg in st.session_state.extraction.get("pages", []):
            for _el in _pg.get("elements", []):
                element_lookup[_el["id"]] = _el

        for idx, f in enumerate(report.auto_fix):
            key = f"chk_af_{f.element_id}_{idx}"
            if not st.session_state.get(key, False):
                continue

            el = element_lookup.get(f.element_id, {})
            el_type = el.get("type")
            el_label = el.get("docling_label", "")

            if f.wcag_criterion == "3.1.1":
                actually_fixable.append({"fix_type": "set_language", "element_id": f.element_id})

            elif f.wcag_criterion == "2.4.2":
                title_val = next(
                    (m["value"] for m in report.metadata_fixes if m.get("field") == "title"), ""
                )
                actually_fixable.append({
                    "fix_type": "set_title",
                    "element_id": f.element_id,
                    "value": title_val,
                })

            elif "bookmark" in (f.proposed_fix or "").lower() and pdf_subtype in ("tagged_pdf", "untagged_pdf"):
                headings = []
                for page in st.session_state.extraction.get("pages", []):
                    for el_h in page.get("elements", []):
                        if el_h.get("docling_label") in ("section_header", "title"):
                            text = (el_h.get("text") or "").strip()
                            if text:
                                headings.append({"text": text, "page": page["page_number"]})
                actually_fixable.append({
                    "fix_type": "set_bookmarks",
                    "element_id": f.element_id,
                    "headings": headings,
                })

            elif pdf_subtype == "tagged_pdf" and _is_pdf_structural(f):
                # Tagged PDF: structural fixes need tag-tree editing (not yet implemented)
                structural_items.append({
                    "page": f.page,
                    "wcag_criterion": f.wcag_criterion,
                    "current_state": f.current_state,
                    "proposed_fix": f.proposed_fix,
                })

            else:
                # Determine the correct fix_type from element type so remediator
                # and rebuilder recognise it. Falls back to the wcag criterion string
                # (which will be skipped with a reason) only when type is unknown.
                if el_type == "image":
                    fix_type = "set_alt_text"
                elif el_type == "table":
                    fix_type = "set_table_header"
                elif el_type == "text" and el_label in ("section_header", "title"):
                    fix_type = "set_heading_style"
                else:
                    fix_type = f.wcag_criterion  # fallback — remediator will skip with reason

                fix_dict: dict = {
                    "fix_type": fix_type,
                    "element_id": f.element_id,
                    "page": f.page,
                    "value": f.proposed_fix or "",
                    "paragraph_index": el.get("paragraph_index"),
                    "table_index": el.get("table_index"),
                    "text": el.get("text", ""),
                }
                if fix_type == "set_heading_style":
                    # User may have picked a level via H1-H4 selector; fall back
                    # to inferring from proposed_fix string.
                    _level = st.session_state.heading_levels.get(
                        f.element_id,
                        _infer_level_from_proposed_fix(f.proposed_fix),
                    )
                    fix_dict["value"] = str(_level)
                if fix_type == "set_alt_text":
                    fix_dict["user_value"] = user_inputs.get(f.element_id, "")
                actually_fixable.append(fix_dict)

        # ── Collect skipped fixes (checked by default but unchecked by user) ──
        skipped_by_user: list[dict] = []
        for idx, f in enumerate(report.auto_fix):
            _sk = f"chk_af_{f.element_id}_{idx}"
            if not st.session_state.get(_sk, False):
                skipped_by_user.append({
                    "page": f.page,
                    "wcag_criterion": f.wcag_criterion,
                    "description": f.current_state or f.proposed_fix or "",
                })
        for idx, (eid, val) in enumerate(user_inputs.items()):
            if val and not st.session_state.get(f"chk_ui_{eid}_{idx}", True):
                _sk_finding = next((x for x in report.human_review if x.element_id == eid), None)
                if _sk_finding:
                    skipped_by_user.append({
                        "page": _sk_finding.page,
                        "wcag_criterion": _sk_finding.wcag_criterion,
                        "description": _sk_finding.current_state or "",
                    })

        # ── User-entered values (human_review items with input provided) ──────
        # These were entered in Stage 2 but were not in report.auto_fix, so they
        # need their own fix dicts. Only include the ones the user left checked.
        for idx, (eid, val) in enumerate(user_inputs.items()):
            if not val:
                continue
            if not st.session_state.get(f"chk_ui_{eid}_{idx}", True):
                continue  # user unchecked this row in Stage 3
            finding = next((x for x in report.human_review if x.element_id == eid), None)
            if finding is None:
                continue
            el = element_lookup.get(eid, {})
            actually_fixable.append({
                "fix_type": "set_alt_text",
                "element_id": eid,
                "page": finding.page,
                "value": val,
                "user_value": val,
                "paragraph_index": el.get("paragraph_index"),
                "table_index": el.get("table_index"),
                "text": el.get("text", ""),
            })

        with st.spinner("Applying fixes…"):
            if pdf_subtype == "untagged_pdf":
                output_path = remediate_untagged_pdf(
                    input_path,
                    st.session_state.extraction,
                    actually_fixable,
                    source_docx_path=st.session_state.get("source_docx_path"),
                )
            else:
                pipeline = get_pipeline(pdf_subtype)
                output_path = pipeline(input_path, st.session_state.extraction, actually_fixable)
            applied_fixes = get_last_result()

        # ── Ensure user-entered alt text appears in applied list ─────────────
        # For rebuild path, alt text is baked in by rebuild_as_docx() and may
        # not be listed by remediate_docx(). Deduplicate against existing entries.
        _applied_lower = {s.lower() for s in applied_fixes.get("applied", [])}
        _alt_additions = []
        for _fix in actually_fixable:
            if _fix.get("fix_type") == "set_alt_text":
                _val = _fix.get("user_value") or _fix.get("value") or ""
                if _val:
                    _entry = f"Alt text set — \"{_trunc(_val, 50)}\""
                    if _entry.lower() not in _applied_lower:
                        _alt_additions.append(_entry)
                        _applied_lower.add(_entry.lower())
        if _alt_additions:
            applied_fixes["applied"] = list(applied_fixes.get("applied", [])) + _alt_additions

        # ── Post-rebuild reclassification (untagged PDF rebuild path only) ────
        # Heading (1.3.1 / section_header) findings are resolved by the
        # rebuilder writing proper Word heading styles. Move them from
        # human_review to auto_fix and add them to the applied list so
        # Stage 4 counts them as fixed.
        if pdf_subtype == "untagged_pdf" and not st.session_state.get("source_docx_path"):
            _report = st.session_state.audit_report
            _el_label_map: dict[str, str] = {}
            for _pg in st.session_state.extraction.get("pages", []):
                for _el in _pg.get("elements", []):
                    _el_label_map[_el["id"]] = _el.get("docling_label", "")

            _to_reclassify = [
                f for f in _report.human_review
                if f.wcag_criterion == "1.3.1"
                and _el_label_map.get(f.element_id) == "section_header"
            ]
            if _to_reclassify:
                _fix_note = "Resolved during reconstruction — written as Word heading style."
                for _f in _to_reclassify:
                    _f.proposed_fix = _fix_note
                    _f.classification = "auto-fix"
                _report.human_review = [
                    f for f in _report.human_review if f not in _to_reclassify
                ]
                _report.auto_fix = list(_report.auto_fix) + _to_reclassify
                _applied = list(applied_fixes.get("applied", []))
                for _f in _to_reclassify:
                    _heading_text = _trunc(_f.current_state, 60)
                    _applied.append(
                        f"Page {_f.page} — \"{_heading_text}\" written as heading style"
                    )
                applied_fixes["applied"] = _applied

        with st.spinner("Generating report…"):
            try:
                diff_path = generate_diff_report(
                    original_path=input_path,
                    output_path=output_path,
                    audit_report=report,
                    applied_fixes=applied_fixes,
                    user_inputs=user_inputs,
                )
            except Exception:
                # Diff report generation may fail when input and output
                # formats differ (e.g. PDF → docx rebuild path).
                diff_path = None

        # Generate audit CSV
        _user_notes = st.session_state.get("user_notes", {})
        rows = []
        for f in report.findings:
            rows.append({
                "resource": st.session_state.uploaded_filename,
                "page": f.page,
                "wcag_criterion": f.wcag_criterion,
                "severity": f.severity,
                "issue": f.current_state,
                "proposed_fix": f.proposed_fix or "",
                "status": f.classification,
                "confidence": f.confidence or "",
                "verification_path": f.verification_path or "",
                "check_type": getattr(f, "check_type", "") or "",
                "sub_criterion": getattr(f, "sub_criterion", "") or "",
                "user_note": _user_notes.get(f.element_id, ""),
            })
        audit_csv = pd.DataFrame(rows).to_csv(index=False)

        # Read remediated bytes
        try:
            remediated_bytes = Path(output_path).read_bytes()
        except FileNotFoundError:
            remediated_bytes = file_bytes

        # Run post-fix validation
        try:
            validation_result = validate_fixes(output_path, actually_fixable)
        except Exception:
            validation_result = {"passed": [], "failed": [], "skipped": ["Validation could not run"]}

        st.session_state.remediated_path = output_path
        st.session_state.diff_report_path = diff_path
        st.session_state.applied_fixes = applied_fixes
        st.session_state.audit_csv = audit_csv
        st.session_state.approved_fixes = actually_fixable
        st.session_state.structural_items = structural_items
        st.session_state._remediated_bytes = remediated_bytes
        st.session_state.validation_result = validation_result
        st.session_state.skipped_by_user = skipped_by_user
        st.session_state.stage = 4
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 4 — Download
# ══════════════════════════════════════════════════════════════════════════════
def stage_4():
    report: AuditReport = st.session_state.audit_report
    applied_fixes: dict = st.session_state.applied_fixes

    if st.button("← Back to Review"):
        st.session_state.stage = 3
        st.rerun()

    st.title("Remediation Complete")

    # ── Metrics ───────────────────────────────────────────────────────────
    total = len(report.findings)
    n_fixed = len(applied_fixes.get("applied", []))
    n_human = len(report.human_review)
    n_preserve = len(report.preserve_findings)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Issues Found", total)
    c2.metric("Auto-Fixed", n_fixed)
    c3.metric("Human Follow-Up", n_human)
    c4.metric("Already Correct", n_preserve)

    # ── Fix Validation ────────────────────────────────────────────────────
    validation_result: dict = st.session_state.get("validation_result", {})
    if validation_result and (
        validation_result.get("passed")
        or validation_result.get("failed")
        or validation_result.get("skipped")
    ):
        st.subheader("Fix Validation")
        st.caption(
            "Confirms that specific fixes were successfully written to the output file."
        )
        for msg in validation_result.get("passed", []):
            st.success(f"✓ {msg}")
        for msg in validation_result.get("failed", []):
            st.error(f"✗ {msg}")
        for msg in validation_result.get("skipped", []):
            st.warning(f"— {msg}")

    # ── Content check (untagged PDF rebuild only — not when source docx was used) ──
    if (
        st.session_state.get("pdf_subtype") == "untagged_pdf"
        and not st.session_state.get("source_docx_path")
    ):
        cc = applied_fixes.get("content_check")
        if cc:
            st.divider()
            st.subheader("Document Content Check")
            st.caption(
                "Counts structural elements found in the rebuilt document — headings, "
                "images, tables. Confirms content was not lost during reconstruction."
            )
            exp_img = cc["expected_images"]
            act_img = cc["actual_images"]
            exp_tbl = cc["expected_tables"]
            act_tbl = cc["actual_tables"]
            if cc["ok"]:
                st.success(
                    f"Content check: all {exp_img} image(s) and {exp_tbl} table(s) "
                    "from the source were preserved."
                )
            else:
                parts = []
                if act_img < exp_img:
                    parts.append(f"expected {exp_img} image(s) but the rebuilt document has {act_img}")
                if act_tbl < exp_tbl:
                    parts.append(f"expected {exp_tbl} table(s) but found {act_tbl}")
                st.warning(
                    "Content check: " + "; ".join(parts)
                    + ". Some content may not have been reconstructed — "
                    "please verify against the original."
                )

    # ── Downloads ─────────────────────────────────────────────────────────
    filename = st.session_state.uploaded_filename
    stem = Path(filename).stem
    suffix = Path(filename).suffix

    col1, col2, col3 = st.columns(3)

    with col1:
        remediated_bytes = st.session_state.get("_remediated_bytes", b"")
        pdf_subtype = st.session_state.get("pdf_subtype", "tagged_pdf")
        if pdf_subtype == "docx":
            dl_label = "Download Remediated Word Document (.docx)"
            dl_mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            dl_suffix = ".docx"
        elif pdf_subtype == "untagged_pdf":
            if st.session_state.get("source_docx_path"):
                dl_label = "Download Remediated Word Document (.docx)"
            else:
                dl_label = "Download Reconstructed Word Document (.docx)"
            dl_mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            dl_suffix = ".docx"
        else:
            dl_label = "Download Remediated PDF"
            dl_mime = "application/pdf"
            dl_suffix = suffix
        st.download_button(
            dl_label,
            data=remediated_bytes,
            file_name=f"{stem}_remediated{dl_suffix}",
            mime=dl_mime,
        )

    with col2:
        st.download_button(
            "Download Audit Report (CSV)",
            data=st.session_state.audit_csv,
            file_name=f"{stem}_audit_report.csv",
            mime="text/csv",
        )

    with col3:
        diff_path = st.session_state.diff_report_path
        diff_bytes = Path(diff_path).read_bytes() if diff_path and Path(diff_path).exists() else b""
        st.download_button(
            "Download Before/After Report (HTML)",
            data=diff_bytes,
            file_name=f"{stem}_diff_report.html",
            mime="text/html",
        )

    st.divider()

    # ── Fixes applied to file ─────────────────────────────────────────────
    applied_list = applied_fixes.get("applied", [])
    if applied_list:
        st.subheader(f"Fixes applied to file: {len(applied_list)}")
        for desc in applied_list:
            st.markdown(f"- {desc}")

    # ── Structural items (cannot be written into PDF) ─────────────────────
    structural_items = st.session_state.get("structural_items", [])
    if structural_items:
        st.subheader(f"Manual remediation required: {len(structural_items)}")
        st.warning(
            "These were flagged but cannot be written into this PDF because it has no "
            "accessibility tag tree. Fix in the source document and re-export as a tagged PDF."
        )
        for item in structural_items:
            st.markdown(
                f"- Page {item['page']} — WCAG {item['wcag_criterion']}: {item.get('current_state', '')}"
            )

    # ── Unresolved human-review items ─────────────────────────────────────
    user_inputs: dict = st.session_state.user_inputs
    unresolved = [
        f for f in report.human_review
        if f.element_id not in user_inputs or not user_inputs[f.element_id]
    ]
    if unresolved:
        st.subheader("Human Review Required")
        st.warning(
            "The items below could not be fixed automatically and require manual editing "
            "in Word. Use this checklist to track your progress — checking an item here "
            "does not change your file."
        )
        for i, f in enumerate(unresolved):
            col_cb, col_text = st.columns([0.05, 0.95])
            with col_cb:
                st.checkbox("", key=f"manual_done_{i}_{f.element_id}", value=False)
            with col_text:
                st.write(f"**Page {f.page}** — {_trunc(f.current_state, 60)}")
                st.caption(_word_instruction(f))

        with st.expander("All manual instructions"):
            for f in unresolved:
                st.markdown(f"**Page {f.page}** — {f.current_state}  \n→ {_word_instruction(f)}")

    # ── Fixes skipped by user ─────────────────────────────────────────────
    _skipped_by_user = st.session_state.get("skipped_by_user", [])
    if _skipped_by_user:
        st.subheader("Fixes Skipped by You")
        st.caption(
            "These fixes were available but you chose not to apply them. "
            "You can re-run the tool to apply them later."
        )
        for item in _skipped_by_user:
            st.markdown(
                f"— Page {item['page']} — "
                f"{item['wcag_criterion']} — "
                f"{item['description']}"
            )

    # ── Post-download guidance ─────────────────────────────────────────────
    pdf_subtype_s4 = st.session_state.get("pdf_subtype", "tagged_pdf")
    if pdf_subtype_s4 == "untagged_pdf":
        st.divider()
        if st.session_state.get("source_docx_path"):
            st.info(
                "Fixes were applied to your original Word document. This output "
                "preserves all original formatting, images, formulae, and tables."
            )
        else:
            st.info(
                "This PDF had no accessibility tag tree and has been rebuilt as a "
                "structured Word document. To complete full WCAG compliance:\n\n"
                "1. Open the downloaded Word document in Microsoft Word\n"
                "2. Review headings, tables, and image placeholders\n"
                "3. Add alt text to images (right-click image → Edit Alt Text)\n"
                "4. File → Save As → PDF → Options → check "
                "'Document structure tags for accessibility'\n"
                "5. Upload the resulting tagged PDF back to this tool to verify compliance"
            )

    st.divider()
    if st.button("Analyze Another Document"):
        _reset()
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# Router
# ══════════════════════════════════════════════════════════════════════════════

def _run_stage(fn, stage_key: str) -> None:
    """Run a stage function wrapped in user-friendly error handling."""
    try:
        fn()
    except StreamlitDuplicateElementKey as e:
        st.error(
            "A display error occurred. Please click 'Analyze Another Document' to restart."
        )
        st.info(
            "Technical detail (for developers): "
            f"Duplicate widget key: {str(e)}"
        )
        if st.button("Restart", key=f"err_restart_{stage_key}"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    except Exception as e:
        st.error(
            "Something went wrong. Please try again or upload a different document."
        )
        with st.expander("Technical details"):
            st.code(str(e))
        if st.button("Start over", key=f"err_start_{stage_key}"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


stage = st.session_state.stage

if stage == 1:
    _run_stage(stage_1, "s1")
elif stage == 2:
    _run_stage(stage_2, "s2")
elif stage == 3:
    _run_stage(stage_3, "s3")
elif stage == 4:
    _run_stage(stage_4, "s4")
