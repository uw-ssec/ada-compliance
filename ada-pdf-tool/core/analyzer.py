"""
LLM analysis layer.

Calls the backend to audit an extraction dict and classifies findings
into four buckets: auto_fix, human_review, preserve_findings, info.
"""

from __future__ import annotations

from core.backends.base import LLMBackend
from core.models import AuditReport, Finding


def _total_elements(extraction: dict) -> int:
    count = 0
    for page in extraction.get("pages", []):
        count += len(page.get("elements", []))
    return count


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

    report = backend.audit(extraction)

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

    return report
