"""
LLM analysis layer.

Calls the backend to audit an extraction dict and classifies findings
into four buckets: auto_fix, human_review, preserve_findings, info.
"""

from __future__ import annotations

import logging

from core.backends.base import LLMBackend
from core.models import AuditReport, Finding

logger = logging.getLogger(__name__)


def _total_elements(extraction: dict) -> int:
    count = 0
    for page in extraction.get("pages", []):
        count += len(page.get("elements", []))
    return count


def _filter_elements_for_llm(extraction: dict) -> dict:
    """
    Returns a copy of the extraction dict with elements that do not
    require LLM judgment removed. Deterministic outcomes are handled
    by static checks instead.

    Removed element types:
    - page_header, page_footer: skipped by remediator, no WCAG criterion applies
    - footnote: no applicable WCAG criterion for document footnotes
    - caption: alt text association is captured by the picture finding;
      caption text itself requires no LLM classification
    - code: no applicable WCAG criterion for code blocks in documents

    Kept element types (LLM judgment needed):
    - picture: alt text presence and quality
    - formula: equation alt text
    - section_header, title: heading structure
    - table: header row detection
    - text, paragraph, list_item: generic link text, reading order,
      language of parts
    """
    EXCLUDE_LABELS = {
        "page_header",
        "page_footer",
        "footnote",
        "caption",
        "code",
    }

    filtered = {
        "file_type": extraction.get("file_type"),
        "metadata": extraction.get("metadata"),
        "pages": [],
    }

    total_before = 0
    total_after = 0

    for page in extraction.get("pages", []):
        kept_elements = [
            el for el in page.get("elements", [])
            if el.get("docling_label") not in EXCLUDE_LABELS
        ]
        total_before += len(page.get("elements", []))
        total_after += len(kept_elements)

        filtered["pages"].append({
            "page_number": page.get("page_number"),
            "elements": kept_elements,
        })

    logger.info(
        "LLM pre-filter: %d elements → %d sent to LLM (%d excluded)",
        total_before,
        total_after,
        total_before - total_after,
    )

    return filtered


def _static_metadata_checks(extraction: dict) -> list:
    """
    Returns Finding objects for metadata issues that are deterministically
    checkable without LLM reasoning. These are always added to the report
    regardless of LLM output.
    """
    findings = []
    metadata = extraction.get("metadata", {})

    # 3.1.1 Language
    if not metadata.get("language"):
        findings.append(Finding(
            element_id="meta_language",
            page=0,
            wcag_criterion="3.1.1",
            severity="serious",
            classification="auto-fix",
            confidence="high",
            current_state="Document language metadata is not set",
            proposed_fix="Set language to en-US",
            reasoning=(
                "Language metadata is absent from document properties. "
                "Screen readers require this to determine pronunciation."
            ),
            verification_path=None,
            element_subtype=None,
            human_prompt=None,
            check_type="automated",
            sub_criterion="language_declaration",
        ))

    # 2.4.2 Title
    if not metadata.get("title"):
        findings.append(Finding(
            element_id="meta_title",
            page=0,
            wcag_criterion="2.4.2",
            severity="serious",
            classification="auto-fix",
            confidence="high",
            current_state="Document title metadata is not set",
            proposed_fix="Set title from document content",
            reasoning=(
                "Title metadata is absent. Screen readers announce the "
                "document title when a file opens."
            ),
            verification_path=None,
            element_subtype=None,
            human_prompt=None,
            check_type="automated",
            sub_criterion="title_presence",
        ))

    return findings


def analyze(extraction: dict, backend: LLMBackend) -> AuditReport:
    """
    Run an accessibility audit on an extraction dict.

    Parameters
    ----------
    extraction:
        JSON-serialisable dict returned by core.extractor.extract().
    backend:
        An LLMBackend instance (e.g. HyakBackend).

    Returns
    -------
    AuditReport
        Populated with findings split into four classification buckets.
    """
    if _total_elements(extraction) == 0:
        info_finding = Finding(
            element_id="info_000",
            page=0,
            wcag_criterion="general",
            severity="minor",
            classification="info",
            confidence=None,
            current_state="No extractable elements found in this document.",
            proposed_fix=None,
            reasoning="The extraction returned zero elements. The document may be empty or unsupported.",
            verification_path=None,
        )
        return AuditReport(
            findings=[info_finding],
            preserve=[],
            metadata_fixes=[],
            auto_fix=[],
            human_review=[],
            preserve_findings=[],
            info=[info_finding],
        )

    llm_extraction = _filter_elements_for_llm(extraction)
    report = backend.audit(llm_extraction)

    static_findings = _static_metadata_checks(extraction)

    # Remove any LLM findings for meta_language or meta_title to avoid duplicates
    report.findings = [
        f for f in report.findings
        if f.element_id not in ("meta_language", "meta_title")
    ] + static_findings

    # Classify findings into buckets
    auto_fix: list[Finding] = []
    human_review: list[Finding] = []
    preserve_findings: list[Finding] = []
    info: list[Finding] = []

    for finding in report.findings:
        cls = finding.classification
        if cls == "auto-fix":
            auto_fix.append(finding)
        elif cls == "human-review":
            human_review.append(finding)
        elif cls == "preserve":
            preserve_findings.append(finding)
        elif cls == "info":
            info.append(finding)

    report.auto_fix = auto_fix
    report.human_review = human_review
    report.preserve_findings = preserve_findings
    report.info = info

    # Post-process 1.3.1 heading findings: ensure element text is in current_state
    _el_lookup_a: dict = {}
    for _pg in extraction.get("pages", []):
        for _el in _pg.get("elements", []):
            _el_lookup_a[_el["id"]] = _el

    file_type_a = extraction.get("file_type", "pdf")
    for _finding in report.findings:
        if _finding.wcag_criterion != "1.3.1":
            continue
        _el_a = _el_lookup_a.get(_finding.element_id, {})
        _el_type_a = _el_a.get("docling_label", "") or _el_a.get("type", "")
        if _el_type_a not in ("section_header", "title", "text"):
            continue
        _el_text_a = (_el_a.get("text") or "").strip()
        if _el_text_a and _finding.current_state and _el_text_a[:40] not in _finding.current_state:
            _finding.current_state = f"'{_el_text_a[:80]}' — " + _finding.current_state
        # Ensure proposed_fix is never None for auto-fix / heading-selector findings
        if not _finding.proposed_fix:
            if file_type_a == "pdf":
                _finding.proposed_fix = "Assign heading level in rebuilt Word document (select H1–H4 below)"
            else:
                _finding.proposed_fix = "Apply correct heading style (Heading 1–4) in document"

    return report
