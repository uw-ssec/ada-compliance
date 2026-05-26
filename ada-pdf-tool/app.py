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

load_dotenv()

from core.analyzer import analyze
from core.backends.hyak_backend import HyakBackend, HyakGatewayError
from core.diff_reporter import generate_diff_report
from core.dispatch import get_last_result, get_pipeline, remediate_untagged_pdf
from core.extractor import extract, extract_docx, is_tagged_pdf, render_element_thumbnail
from core.models import AuditReport, Finding

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
    "pdf_path", "thumbnails",
]

if "stage" not in st.session_state:
    st.session_state.stage = 1
if "user_inputs" not in st.session_state:
    st.session_state.user_inputs = {}
if "approved_fixes" not in st.session_state:
    st.session_state.approved_fixes = []
if "thumbnails" not in st.session_state:
    st.session_state.thumbnails = {}


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


def _trunc(text: str | None, n: int = 60) -> str:
    s = str(text or "")
    return s[:n] + "…" if len(s) > n else s


def _badge(label: str, color: str) -> str:
    return f'<span style="background:{color};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;margin-left:6px;">{label}</span>'


def _severity_color(sev: str) -> str:
    return {"critical": "#dc2626", "serious": "#ea580c", "moderate": "#d97706", "minor": "#6b7280"}.get(sev, "#6b7280")


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
    """Return a plain-language manual-remediation instruction for a finding."""
    return (
        f.proposed_fix
        or f.human_prompt
        or f"Manual fix required for WCAG {f.wcag_criterion}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 1 — Upload
# ══════════════════════════════════════════════════════════════════════════════
def stage_1():
    st.title("ADA Document Accessibility Auditor")
    st.markdown("Upload a PDF or Word document to audit for WCAG 2.1 AA compliance.")

    uploaded = st.file_uploader(
        "Choose a file",
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
            st.info(
                "No tag tree detected — this document will be reconstructed "
                "as Word for remediation."
            )
            source_docx = st.file_uploader(
                "Do you have the original Word document for this PDF? "
                "Upload it for the most faithful output.",
                type=["docx"],
                key="source_docx_upload",
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
                    if extraction.get("pages"):
                        for el in extraction["pages"][0]["elements"]:
                            print(f"[ELEM] label={el.get('docling_label')} text={str(el.get('text',''))[:50]!r} "
                                  f"size={el.get('font_size')} bold={el.get('font_bold')}", flush=True)
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

    st.title(f"Audit Results — {filename}")

    detection_message = st.session_state.get("detection_message")
    if detection_message:
        st.info(detection_message)

    # ── Auto-fixable ──────────────────────────────────────────────────────
    n_auto = len(report.auto_fix)
    with st.expander(f"🔴 Auto-Fixable Issues ({n_auto} found)", expanded=True):
        if not report.auto_fix:
            st.info("No auto-fixable issues found.")
        for f in report.auto_fix:
            conf_color = "#16a34a" if f.confidence == "high" else "#d97706"
            label = f"Page {f.page} — {f.wcag_criterion} — {_trunc(f.current_state)}"
            with st.expander(label):
                st.markdown(f"**Page:** {f.page}")
                st.markdown(f"**Current state:** {f.current_state}")
                st.markdown(f"**Proposed fix:** {f.proposed_fix}")
                st.markdown(
                    f"**WCAG criterion:** [{f.wcag_criterion}](https://www.w3.org/TR/WCAG21/)"
                )
                st.markdown(
                    f"**Confidence:** "
                    + f'<span style="background:{conf_color};color:#fff;padding:2px 8px;border-radius:4px;font-size:12px;">{f.confidence or "—"}</span>',
                    unsafe_allow_html=True,
                )
                st.markdown(f"**Reasoning:** {f.reasoning}")

    # ── Human review ──────────────────────────────────────────────────────
    n_human = len(report.human_review)
    with st.expander(f"🟡 Requires Human Input ({n_human} items)", expanded=True):
        if not report.human_review:
            st.info("No items require human input.")
        for f in report.human_review:
            el_label = f"Page {f.page} — {f.wcag_criterion} — {_trunc(f.current_state)}"
            with st.expander(el_label):
                st.markdown(f"**Detected:** {f.current_state}")
                st.markdown(f"**Why human input is needed:** {f.reasoning}")
                st.markdown(
                    f"**WCAG criterion:** [{f.wcag_criterion}](https://www.w3.org/TR/WCAG21/)"
                )

                # ── Thumbnail for missing-alt-text findings (PDF only) ────────
                if f.wcag_criterion == "1.1.1" and st.session_state.get("pdf_path"):
                    _thumb_bbox = None
                    _thumb_page = f.page
                    for _pg in st.session_state.extraction.get("pages", []):
                        for _el in _pg.get("elements", []):
                            if _el.get("id") == f.element_id and _el.get("type") == "image":
                                _thumb_bbox = _el.get("bbox")
                                _thumb_page = _pg.get("page_number", f.page)
                                break
                    if _thumb_bbox:
                        try:
                            if f.element_id not in st.session_state.thumbnails:
                                st.session_state.thumbnails[f.element_id] = (
                                    render_element_thumbnail(
                                        st.session_state.pdf_path,
                                        _thumb_page,
                                        _thumb_bbox,
                                    )
                                )
                            st.image(st.session_state.thumbnails[f.element_id], width=200)
                        except Exception:
                            pass  # skip thumbnail silently on any render failure

                if _needs_user_input(f):
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
                    st.caption(_word_instruction(f))

    # ── Already correct ───────────────────────────────────────────────────
    n_preserve = len(report.preserve_findings)
    with st.expander(f"✅ Already Correct ({n_preserve} items)", expanded=False):
        for f in report.preserve_findings:
            st.markdown(f"- **{f.wcag_criterion}** (page {f.page}): {f.current_state}")

    # ── Exception notice ──────────────────────────────────────────────────
    for f in report.info:
        if f.wcag_criterion == "exception":
            st.info(f.current_state)

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

    st.title("Review and Approve Fixes")
    st.caption("Nothing will be written to your file until you click Apply Selected Fixes.")

    # ── Select All / Deselect All ─────────────────────────────────────────
    col1, col2, _ = st.columns([1, 1, 6])
    with col1:
        if st.button("Select All"):
            for f in report.auto_fix:
                st.session_state[f"fix_{f.element_id}"] = True
            for eid in user_inputs:
                st.session_state[f"user_{eid}"] = True
    with col2:
        if st.button("Deselect All"):
            for f in report.auto_fix:
                st.session_state[f"fix_{f.element_id}"] = False
            for eid in user_inputs:
                st.session_state[f"user_{eid}"] = False

    st.divider()

    checked_ids: list[str] = []

    # ── Auto-fix checkboxes ───────────────────────────────────────────────
    for f in report.auto_fix:
        conf = f.confidence or "medium"
        default = conf == "high"
        label = f"Page {f.page} — {_trunc(f.current_state)} → {f.proposed_fix}"

        checked = st.checkbox(
            label,
            value=st.session_state.get(f"fix_{f.element_id}", default),
            key=f"fix_{f.element_id}",
            help=f"WCAG {f.wcag_criterion} | Confidence: {conf}",
        )
        if checked:
            checked_ids.append(f"fix_{f.element_id}")

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
    for eid, val in user_inputs.items():
        if not val:
            continue
        # Find the original finding for page context
        finding = next((x for x in report.human_review if x.element_id == eid), None)
        page_str = str(finding.page) if finding else "?"
        el_text = _trunc(finding.current_state if finding else eid)
        label = f"Page {page_str} — {el_text} → User provided: {val}"

        # Attempt to show thumbnail for alt-text rows (PDF only)
        thumb: bytes | None = None
        if (
            finding
            and finding.wcag_criterion == "1.1.1"
            and st.session_state.get("pdf_path")
        ):
            if eid not in st.session_state.thumbnails:
                # Not yet cached — find bbox and render
                for _pg in st.session_state.extraction.get("pages", []):
                    for _el in _pg.get("elements", []):
                        if _el.get("id") == eid and _el.get("type") == "image":
                            _bbox = _el.get("bbox")
                            _pn = _pg.get("page_number", finding.page)
                            if _bbox:
                                try:
                                    st.session_state.thumbnails[eid] = (
                                        render_element_thumbnail(
                                            st.session_state.pdf_path, _pn, _bbox
                                        )
                                    )
                                except Exception:
                                    pass
                            break
            thumb = st.session_state.thumbnails.get(eid)

        if thumb is not None:
            col_img, col_check = st.columns([1, 4])
            with col_img:
                st.image(thumb, width=80)
            with col_check:
                checked = st.checkbox(
                    label,
                    value=st.session_state.get(f"user_{eid}", True),
                    key=f"user_{eid}",
                )
        else:
            checked = st.checkbox(
                label,
                value=st.session_state.get(f"user_{eid}", True),
                key=f"user_{eid}",
            )
        if checked:
            checked_ids.append(f"user_{eid}")

    # ── Skipped items (no user input provided) ────────────────────────────
    manual_count = 0
    for f in report.human_review:
        if f.element_id not in user_inputs or not user_inputs[f.element_id]:
            manual_count += 1
            st.markdown(
                f'<span style="color:#6b7280;">— Page {f.page} — {f.wcag_criterion} — '
                f"No fix available, manual remediation required</span>",
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

        for f in report.auto_fix:
            key = f"fix_{f.element_id}"
            if not st.session_state.get(key, False):
                continue
            if f.wcag_criterion == "3.1.1":
                actually_fixable.append({"fix_type": "set_language", "element_id": f.element_id})
            elif f.wcag_criterion == "2.4.2":
                title_val = next(
                    (m["value"] for m in report.metadata_fixes if m.get("field") == "title"), ""
                )
                actually_fixable.append({"fix_type": "set_title", "element_id": f.element_id, "value": title_val})
            elif "bookmark" in (f.proposed_fix or "").lower() and pdf_subtype in ("tagged_pdf", "untagged_pdf"):
                headings = []
                for page in st.session_state.extraction.get("pages", []):
                    for el in page.get("elements", []):
                        if el.get("docling_label") in ("section_header", "title"):
                            text = (el.get("text") or "").strip()
                            if text:
                                headings.append({"text": text, "page": page["page_number"]})
                actually_fixable.append({"fix_type": "set_bookmarks", "element_id": f.element_id, "headings": headings})
            elif pdf_subtype == "tagged_pdf" and _is_pdf_structural(f):
                # Tagged PDF: structural fixes need tag-tree editing (not yet implemented)
                structural_items.append({
                    "page": f.page,
                    "wcag_criterion": f.wcag_criterion,
                    "current_state": f.current_state,
                    "proposed_fix": f.proposed_fix,
                })
            else:
                # Untagged PDF (rebuilder handles all), docx (all writable)
                actually_fixable.append({"fix_type": f.wcag_criterion, "element_id": f.element_id})

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
                    _applied.append(
                        f"Page {_f.page} — WCAG {_f.wcag_criterion}: {_fix_note}"
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
            })
        audit_csv = pd.DataFrame(rows).to_csv(index=False)

        # Read remediated bytes
        try:
            remediated_bytes = Path(output_path).read_bytes()
        except FileNotFoundError:
            remediated_bytes = file_bytes

        st.session_state.remediated_path = output_path
        st.session_state.diff_report_path = diff_path
        st.session_state.applied_fixes = applied_fixes
        st.session_state.audit_csv = audit_csv
        st.session_state.approved_fixes = actually_fixable
        st.session_state.structural_items = structural_items
        st.session_state._remediated_bytes = remediated_bytes
        st.session_state.stage = 4
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 4 — Download
# ══════════════════════════════════════════════════════════════════════════════
def stage_4():
    report: AuditReport = st.session_state.audit_report
    applied_fixes: dict = st.session_state.applied_fixes

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

    # ── Content check (untagged PDF rebuild only — not when source docx was used) ──
    if (
        st.session_state.get("pdf_subtype") == "untagged_pdf"
        and not st.session_state.get("source_docx_path")
    ):
        cc = applied_fixes.get("content_check")
        if cc:
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
    unresolved = [f for f in report.human_review if f.element_id not in user_inputs or not user_inputs[f.element_id]]
    if unresolved:
        st.subheader("Human Review Required")
        st.warning(
            "The items below could not be fixed automatically and require manual editing "
            "in Word. Use this checklist to track your progress — checking an item here "
            "does not change your file."
        )
        for i, f in enumerate(unresolved):
            action = f.human_prompt or f.current_state or f"WCAG {f.wcag_criterion}"
            label = f"Page {f.page} — {_trunc(f.current_state, 50)}: {action}"
            st.checkbox(label, key=f"manual_done_{i}_{f.element_id}", value=False)

    st.divider()

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
stage = st.session_state.stage

if stage == 1:
    stage_1()
elif stage == 2:
    stage_2()
elif stage == 3:
    stage_3()
elif stage == 4:
    stage_4()
