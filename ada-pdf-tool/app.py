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

# Allow running from ada-pdf-tool/ without installing as a package
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from core.analyzer import analyze
from core.backends.hyak_backend import HyakBackend
from core.diff_reporter import generate_diff_report
from core.extractor import extract
from core.models import AuditReport, Finding
from core.remediator import remediate

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
    "diff_report_path", "applied_fixes", "audit_csv",
]

if "stage" not in st.session_state:
    st.session_state.stage = 1
if "user_inputs" not in st.session_state:
    st.session_state.user_inputs = {}
if "approved_fixes" not in st.session_state:
    st.session_state.approved_fixes = []


def _reset():
    for key in _KEYS:
        if key in st.session_state:
            del st.session_state[key]
    st.session_state.stage = 1
    st.session_state.user_inputs = {}
    st.session_state.approved_fixes = []


def _trunc(text: str | None, n: int = 60) -> str:
    s = str(text or "")
    return s[:n] + "…" if len(s) > n else s


def _badge(label: str, color: str) -> str:
    return f'<span style="background:{color};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;margin-left:6px;">{label}</span>'


def _severity_color(sev: str) -> str:
    return {"critical": "#dc2626", "serious": "#ea580c", "moderate": "#d97706", "minor": "#6b7280"}.get(sev, "#6b7280")


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

    if st.button("Analyze Document", type="primary"):
        file_bytes = uploaded.read()
        suffix = Path(uploaded.name).suffix.lower()

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            with st.spinner("Extracting document structure…"):
                extraction = extract(tmp_path)

            # Scanned PDF guard
            total_elements = sum(len(p.get("elements", [])) for p in extraction.get("pages", []))
            if total_elements == 0:
                st.error(
                    "This appears to be a scanned PDF. This tool requires a programmatic PDF "
                    "with embedded text. Scanned documents are not supported."
                )
                return

            with st.spinner("Analyzing for accessibility issues…"):
                backend = HyakBackend()
                audit_report = analyze(extraction, backend)

        except ValueError as exc:
            st.error(str(exc))
            return
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        st.session_state.extraction = extraction
        st.session_state.audit_report = audit_report
        st.session_state.uploaded_filename = uploaded.name
        st.session_state.uploaded_bytes = file_bytes
        st.session_state.stage = 2
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 2 — Audit Results
# ══════════════════════════════════════════════════════════════════════════════
def stage_2():
    report: AuditReport = st.session_state.audit_report
    filename: str = st.session_state.uploaded_filename

    st.title(f"Audit Results — {filename}")

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
        badge_color = "#16a34a" if conf == "high" else "#d97706"
        label = f"Page {f.page} — {_trunc(f.current_state)} → {f.proposed_fix}"

        checked = st.checkbox(
            label,
            value=st.session_state.get(f"fix_{f.element_id}", default),
            key=f"fix_{f.element_id}",
            help=f"WCAG {f.wcag_criterion} | Confidence: {conf}",
        )
        if checked:
            checked_ids.append(f"fix_{f.element_id}")

    # ── User-provided values ──────────────────────────────────────────────
    for eid, val in user_inputs.items():
        if not val:
            continue
        # Find the original finding for page context
        finding = next((x for x in report.human_review if x.element_id == eid), None)
        page_str = str(finding.page) if finding else "?"
        el_text = _trunc(finding.current_state if finding else eid)
        label = f"Page {page_str} — {el_text} → User provided: {val}"

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

        output_path = input_path.replace(suffix, f"_remediated{suffix}")

        # Build approved_fixes list for remediator
        approved_fixes: list[dict] = []

        # Metadata fixes from auto_fix findings
        for f in report.auto_fix:
            key = f"fix_{f.element_id}"
            if not st.session_state.get(key, False):
                continue
            if f.wcag_criterion == "3.1.1":
                approved_fixes.append({"fix_type": "set_language", "element_id": f.element_id})
            elif f.wcag_criterion == "2.4.2":
                # Find title value from metadata_fixes
                title_val = next(
                    (m["value"] for m in report.metadata_fixes if m.get("field") == "title"), ""
                )
                approved_fixes.append({"fix_type": "set_title", "element_id": f.element_id, "value": title_val})
            elif "bookmark" in (f.proposed_fix or "").lower():
                # Collect headings from extraction
                headings = []
                for page in st.session_state.extraction.get("pages", []):
                    for el in page.get("elements", []):
                        if el.get("docling_label") in ("section_header", "title"):
                            text = (el.get("text") or "").strip()
                            if text:
                                headings.append({"text": text, "page": page["page_number"]})
                approved_fixes.append({"fix_type": "set_bookmarks", "element_id": f.element_id, "headings": headings})
            else:
                # Structural fix — will be skipped with explanation
                approved_fixes.append({"fix_type": f.wcag_criterion, "element_id": f.element_id})

        with st.spinner("Applying fixes…"):
            applied_fixes = remediate(input_path, output_path, approved_fixes)

        with st.spinner("Generating report…"):
            diff_path = generate_diff_report(
                original_path=input_path,
                output_path=output_path,
                audit_report=report,
                applied_fixes=applied_fixes,
                user_inputs=user_inputs,
            )

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
        st.session_state.approved_fixes = approved_fixes
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

    # ── Human follow-up ───────────────────────────────────────────────────
    user_inputs: dict = st.session_state.user_inputs
    unresolved = [f for f in report.human_review if f.element_id not in user_inputs or not user_inputs[f.element_id]]
    if unresolved:
        st.subheader("Manual Remediation Required")
        for f in unresolved:
            st.markdown(
                f"- **WCAG {f.wcag_criterion}** (page {f.page}): {f.current_state}"
                + (f"\n  - _{f.human_prompt}_" if f.human_prompt else "")
            )
        st.info(
            "To fix these items: open your source document in Microsoft Word or Google Docs, "
            "apply proper Heading styles to headings, add alt text to images, then re-export "
            "with 'accessibility' or 'tagged PDF' settings enabled."
        )

    st.divider()

    # ── Downloads ─────────────────────────────────────────────────────────
    filename = st.session_state.uploaded_filename
    stem = Path(filename).stem
    suffix = Path(filename).suffix

    col1, col2, col3 = st.columns(3)

    with col1:
        remediated_bytes = st.session_state.get("_remediated_bytes", b"")
        st.download_button(
            "Download Remediated PDF",
            data=remediated_bytes,
            file_name=f"{stem}_remediated{suffix}",
            mime="application/pdf",
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
