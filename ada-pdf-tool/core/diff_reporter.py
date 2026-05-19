"""
HTML before/after diff report generator.
"""

from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path

import pikepdf

from core.models import AuditReport


_OUTPUT_DIR = Path(__file__).parent.parent / "tests" / "eval" / "sample_pdfs"

_COLORS = {
    "red": "#dc2626",
    "yellow": "#d97706",
    "green": "#16a34a",
    "blue": "#2563eb",
    "grey": "#6b7280",
    "purple": "#7c3aed",
    "bg": "#f9fafb",
    "card": "#ffffff",
    "border": "#e5e7eb",
}

_STATUS_STYLES = {
    "Fixed": f"background:{_COLORS['green']};color:#fff;padding:2px 6px;border-radius:3px;font-size:12px;",
    "Human Review": f"background:{_COLORS['yellow']};color:#fff;padding:2px 6px;border-radius:3px;font-size:12px;",
    "Skipped": f"background:{_COLORS['grey']};color:#fff;padding:2px 6px;border-radius:3px;font-size:12px;font-style:italic;",
    "Pass": f"background:#dbeafe;color:{_COLORS['blue']};padding:2px 6px;border-radius:3px;font-size:12px;",
    "Info": f"background:#ede9fe;color:{_COLORS['purple']};padding:2px 6px;border-radius:3px;font-size:12px;",
}


def _e(text: str | None) -> str:
    return html.escape(str(text or ""))


def _trunc(text: str | None, n: int = 60) -> str:
    s = str(text or "")
    return s[:n] + "…" if len(s) > n else s


def generate_diff_report(
    original_path: str,
    output_path: str,
    audit_report: AuditReport,
    applied_fixes: dict,
    user_inputs: dict,
) -> str:
    """
    Generate a self-contained HTML before/after report.

    Returns the path to the generated HTML file.
    """
    original_path = Path(original_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filename = f"diff_report_{original_path.stem}_{timestamp}.html"

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = _OUTPUT_DIR / report_filename

    # ── Compute summary counts ─────────────────────────────────────────────
    total = len(audit_report.findings)
    n_fixed = len(applied_fixes.get("applied", []))
    n_human = len(audit_report.human_review)
    n_preserve = len(audit_report.preserve_findings)

    # ── Before/After metadata ──────────────────────────────────────────────
    # Read actual metadata from the original PDF
    meta_before: dict[str, str] = {
        "Document Title": "Not set",
        "Document Language": "Not set",
        "Bookmarks Present": "Not present",
    }
    try:
        with pikepdf.open(str(original_path)) as _pdf:
            raw_title = _pdf.docinfo.get("/Title", None)
            meta_before["Document Title"] = str(raw_title) if raw_title else "Not set"
            raw_lang = _pdf.Root.get("Lang", None)
            meta_before["Document Language"] = str(raw_lang) if raw_lang else "Not set"
            meta_before["Bookmarks Present"] = (
                "Present" if "/Outlines" in _pdf.Root else "Not present"
            )
    except Exception:
        pass  # fall back to "Not set" silently

    meta_after: dict[str, str] = dict(meta_before)

    for fix in audit_report.metadata_fixes:
        field = fix.get("field", "")
        value = fix.get("value", "")
        if field == "title":
            meta_after["Document Title"] = value or "—"
        elif field == "language":
            meta_after["Document Language"] = value or "—"

    applied_list = applied_fixes.get("applied", [])
    for a in applied_list:
        if "bookmark" in a.lower():
            meta_after["Bookmarks Present"] = "Present"
        if "language" in a.lower():
            meta_after["Document Language"] = "en-US"

    # ── Build findings table rows ──────────────────────────────────────────
    rows_html = ""
    for f in audit_report.findings:
        cls = f.classification
        if cls == "auto-fix":
            status_label = "Fixed"
        elif cls == "human-review":
            status_label = "Human Review"
        elif cls == "preserve":
            status_label = "Pass"
        else:
            status_label = "Info"

        style = _STATUS_STYLES.get(status_label, "")
        details = _e(f.reasoning)

        if cls == "human-review" and f.element_subtype == "equation":
            eq_prompt = _e(f.human_prompt or "")
            details += f'<div style="background:#fef3c7;border:1px solid #d97706;border-radius:4px;padding:6px;margin-top:6px;font-size:12px;">{eq_prompt}</div>'

        if cls == "human-review" and f.element_id in user_inputs:
            val = _e(user_inputs[f.element_id])
            details += f'<div style="color:{_COLORS["green"]};margin-top:4px;font-size:12px;">User provided: {val}</div>'

        element_text = _trunc(f.current_state)
        rows_html += f"""
        <tr>
          <td style="padding:8px;border-bottom:1px solid {_COLORS['border']};">{_e(str(f.page))}</td>
          <td style="padding:8px;border-bottom:1px solid {_COLORS['border']};font-size:13px;">{_e(element_text)}</td>
          <td style="padding:8px;border-bottom:1px solid {_COLORS['border']};">{_e(f.wcag_criterion)}</td>
          <td style="padding:8px;border-bottom:1px solid {_COLORS['border']};">{_e(f.severity)}</td>
          <td style="padding:8px;border-bottom:1px solid {_COLORS['border']};"><span style="{style}">{status_label}</span></td>
          <td style="padding:8px;border-bottom:1px solid {_COLORS['border']};font-size:12px;">{details}</td>
        </tr>"""

    # ── Before/After metadata table rows ──────────────────────────────────
    meta_rows = ""
    for key in ["Document Title", "Document Language", "Bookmarks Present"]:
        before_val = _e(meta_before[key])
        after_val = _e(meta_after[key])
        changed = meta_before[key] != meta_after[key]
        after_style = f"background:#dcfce7;" if changed else ""
        meta_rows += f"""
        <tr>
          <td style="padding:8px;border-bottom:1px solid {_COLORS['border']};font-weight:600;">{_e(key)}</td>
          <td style="padding:8px;border-bottom:1px solid {_COLORS['border']};">{before_val}</td>
          <td style="padding:8px;border-bottom:1px solid {_COLORS['border']};{after_style}">{after_val}</td>
        </tr>"""

    # ── Human follow-up items ──────────────────────────────────────────────
    unresolved = [f for f in audit_report.human_review if f.element_id not in user_inputs]
    followup_html = ""
    if unresolved:
        items = ""
        for f in unresolved:
            items += f"""
            <div style="border:1px solid {_COLORS['border']};border-radius:6px;padding:12px;margin-bottom:10px;background:{_COLORS['card']};">
              <div style="font-weight:600;margin-bottom:4px;">WCAG {_e(f.wcag_criterion)}</div>
              <div style="margin-bottom:4px;">{_e(f.current_state)}</div>
              {f'<div style="color:{_COLORS["grey"]};font-size:12px;">{_e(f.human_prompt)}</div>' if f.human_prompt else ""}
            </div>"""
        followup_html = f"""
        <div style="margin-bottom:32px;">
          <h2 style="color:{_COLORS['red']};margin-bottom:12px;">Manual Remediation Required</h2>
          {items}
          <div style="background:#dbeafe;border-radius:6px;padding:14px;color:{_COLORS['blue']};font-size:14px;">
            These items require fixing in the source document. Open in Microsoft Word or Google Docs,
            apply proper heading styles, add alt text to images, then re-export with accessibility
            settings enabled.
          </div>
        </div>"""

    # ── Exception notice ───────────────────────────────────────────────────
    exception_html = ""
    for f in audit_report.info:
        if f.wcag_criterion == "exception":
            exception_html = f"""
            <div style="background:#dbeafe;border:1px solid {_COLORS['blue']};border-radius:6px;padding:14px;margin-bottom:24px;color:{_COLORS['blue']};">
              <strong>ADA Title II Exception Notice</strong><br>
              {_e(f.current_state)}
            </div>"""
            break

    # ── Full HTML ──────────────────────────────────────────────────────────
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ADA Accessibility Audit Report — {_e(original_path.name)}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: {_COLORS['bg']}; color: #111827; margin: 0; padding: 24px; }}
  .container {{ max-width: 1100px; margin: 0 auto; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th {{ background: {_COLORS['bg']}; padding: 10px 8px; text-align: left;
        border-bottom: 2px solid {_COLORS['border']}; font-size: 13px; }}
</style>
</head>
<body>
<div class="container">

  <!-- Header -->
  <div style="background:{_COLORS['card']};border-radius:8px;padding:24px;margin-bottom:24px;border:1px solid {_COLORS['border']};">
    <h1 style="margin:0 0 4px;font-size:22px;">ADA Accessibility Audit Report</h1>
    <div style="color:{_COLORS['grey']};font-size:14px;">{_e(original_path.name)} &nbsp;|&nbsp; {datetime.now().strftime('%Y-%m-%d %H:%M')} &nbsp;|&nbsp; Generated by ADA PDF Tool</div>
  </div>

  <!-- Summary bar -->
  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px;">
    <div style="background:{_COLORS['card']};border-radius:8px;padding:20px;border-top:4px solid {_COLORS['red']};border:1px solid {_COLORS['border']};">
      <div style="font-size:28px;font-weight:700;color:{_COLORS['red']};">{total}</div>
      <div style="color:{_COLORS['grey']};font-size:13px;">Total Issues Found</div>
    </div>
    <div style="background:{_COLORS['card']};border-radius:8px;padding:20px;border-top:4px solid {_COLORS['green']};border:1px solid {_COLORS['border']};">
      <div style="font-size:28px;font-weight:700;color:{_COLORS['green']};">{n_fixed}</div>
      <div style="color:{_COLORS['grey']};font-size:13px;">Auto-Fixed</div>
    </div>
    <div style="background:{_COLORS['card']};border-radius:8px;padding:20px;border-top:4px solid {_COLORS['yellow']};border:1px solid {_COLORS['border']};">
      <div style="font-size:28px;font-weight:700;color:{_COLORS['yellow']};">{n_human}</div>
      <div style="color:{_COLORS['grey']};font-size:13px;">Require Human Follow-Up</div>
    </div>
    <div style="background:{_COLORS['card']};border-radius:8px;padding:20px;border-top:4px solid {_COLORS['grey']};border:1px solid {_COLORS['border']};">
      <div style="font-size:28px;font-weight:700;color:{_COLORS['grey']};">{n_preserve}</div>
      <div style="color:{_COLORS['grey']};font-size:13px;">Already Correct</div>
    </div>
  </div>

  <!-- Before/After metadata -->
  <div style="background:{_COLORS['card']};border-radius:8px;padding:20px;margin-bottom:24px;border:1px solid {_COLORS['border']};">
    <h2 style="margin:0 0 14px;font-size:16px;">Metadata: Before / After</h2>
    <table>
      <thead><tr>
        <th>Field</th><th>Before</th><th>After</th>
      </tr></thead>
      <tbody>{meta_rows}</tbody>
    </table>
  </div>

  <!-- Findings table -->
  <div style="background:{_COLORS['card']};border-radius:8px;padding:20px;margin-bottom:24px;border:1px solid {_COLORS['border']};">
    <h2 style="margin:0 0 14px;font-size:16px;">All Findings</h2>
    <table>
      <thead><tr>
        <th>Page</th><th>Element</th><th>WCAG</th><th>Severity</th><th>Status</th><th>Details</th>
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>

  {followup_html}
  {exception_html}

  <!-- Footer -->
  <div style="color:{_COLORS['grey']};font-size:12px;border-top:1px solid {_COLORS['border']};padding-top:16px;margin-top:8px;">
    Original file was not modified. All fixes were applied to the remediated copy only.
    Run the remediated file through DubBot to verify compliance.
  </div>

</div>
</body>
</html>"""

    report_path.write_text(html_content, encoding="utf-8")
    return str(report_path)
