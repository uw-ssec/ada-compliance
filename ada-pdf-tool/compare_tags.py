#!/usr/bin/env python3
"""
Generate an HTML before/after report comparing an untagged PDF to its
tagged counterpart.

Usage:
    python compare_tags.py [original.pdf] [tagged.pdf]

Defaults to the sample pair produced by test_tags.py.
Opens the report in your default browser.
"""

from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pikepdf

DEFAULT_ORIGINAL = Path(__file__).parent.parent / "samples" / "IV-A 2024.pdf"
DEFAULT_TAGGED   = (
    Path(__file__).parent
    / "tests" / "eval" / "sample_pdfs" / "output_tagged.pdf"
)
REPORT = Path(__file__).parent / "tag_comparison.html"

STRUCT_COLORS = {
    "H1":      ("#1a3a5c", "#d0e8ff"),
    "H2":      ("#1a3a5c", "#e8f4ff"),
    "P":       ("#2d2d2d", "#f9f9f9"),
    "LI":      ("#2d4a1a", "#edfade"),
    "Caption": ("#5a3a00", "#fff8e0"),
    "Note":    ("#5a0000", "#fff0f0"),
    "Document":("#444",    "#ececec"),
}


def pdf_info(path: Path) -> dict:
    with pikepdf.open(path) as pdf:
        marked = bool(
            pdf.Root.get("/MarkInfo", pikepdf.Dictionary()).get("/Marked", False)
        )
        has_tree = "/StructTreeRoot" in pdf.Root
        pages = len(pdf.pages)

        elements = []
        wired = 0
        if has_tree:
            try:
                doc_kids = pdf.Root["/StructTreeRoot"].K[0].K
                for kid in doc_kids:
                    s = str(kid.get("/S", "?")).lstrip("/")
                    alt = str(kid.get("/Alt", "")).strip()
                    pg_ref = kid.get("/Pg")
                    pg_no = "?"
                    if pg_ref is not None:
                        try:
                            pg_no = pdf.pages.index(pg_ref) + 1
                        except Exception:
                            pass
                    linked = "/K" in kid
                    if linked:
                        wired += 1
                    elements.append(
                        {"type": s, "text": alt[:80], "page": pg_no, "linked": linked}
                    )
            except Exception:
                pass

    return {
        "path": path,
        "marked": marked,
        "has_tree": has_tree,
        "pages": pages,
        "elements": elements,
        "wired": wired,
    }


def badge(ok: bool, yes: str = "YES", no: str = "NO") -> str:
    color = "#2a7a2a" if ok else "#c0392b"
    label = yes if ok else no
    return f'<span style="background:{color};color:#fff;padding:2px 8px;border-radius:3px;font-size:0.85em">{label}</span>'


def elem_row(el: dict) -> str:
    fg, bg = STRUCT_COLORS.get(el["type"], ("#333", "#f5f5f5"))
    link_icon = "⛓" if el["linked"] else "◌"
    link_title = "MCID-wired to content stream" if el["linked"] else "Alt text only — no content link"
    return (
        f'<tr style="background:{bg}">'
        f'<td style="color:{fg};font-weight:600;padding:4px 8px;white-space:nowrap">'
        f'  &lt;{el["type"]}&gt;</td>'
        f'<td style="padding:4px 8px;color:#555">p{el["page"]}</td>'
        f'<td style="padding:4px 8px" title="{link_title}">{link_icon}</td>'
        f'<td style="padding:4px 8px;font-size:0.9em">{el["text"]}</td>'
        f'</tr>'
    )


def panel(info: dict, label: str) -> str:
    rows = "".join(elem_row(e) for e in info["elements"])
    tree_section = (
        f"""
        <h3 style="margin-top:20px">Structure tree
          <span style="font-weight:normal;font-size:0.85em;color:#666">
            ({len(info["elements"])} elements,
             {info["wired"]} MCID-wired ⛓,
             {len(info["elements"]) - info["wired"]} alt-text only ◌)
          </span>
        </h3>
        <div style="overflow-y:auto;max-height:600px;border:1px solid #ddd;border-radius:4px">
          <table style="width:100%;border-collapse:collapse;font-family:monospace;font-size:0.88em">
            <thead style="background:#e8e8e8;position:sticky;top:0">
              <tr>
                <th style="padding:4px 8px;text-align:left">Type</th>
                <th style="padding:4px 8px;text-align:left">Page</th>
                <th style="padding:4px 8px" title="⛓ = wired to content stream">⛓</th>
                <th style="padding:4px 8px;text-align:left">Alt text (first 80 chars)</th>
              </tr>
            </thead>
            <tbody>{rows}</tbody>
          </table>
        </div>
        """ if info["elements"] else
        '<p style="color:#999;font-style:italic">No structure tree present.</p>'
    )

    return f"""
    <div style="flex:1;min-width:0;padding:20px;border:1px solid #ccc;border-radius:6px">
      <h2 style="margin-top:0">{label}</h2>
      <p style="font-family:monospace;color:#555;font-size:0.85em">{info["path"].name}</p>
      <table style="border-collapse:collapse;font-size:0.9em;margin-bottom:8px">
        <tr>
          <td style="padding:3px 10px 3px 0;color:#666">Pages</td>
          <td>{info["pages"]}</td>
        </tr>
        <tr>
          <td style="padding:3px 10px 3px 0;color:#666">/MarkInfo /Marked</td>
          <td>{badge(info["marked"])}</td>
        </tr>
        <tr>
          <td style="padding:3px 10px 3px 0;color:#666">/StructTreeRoot</td>
          <td>{badge(info["has_tree"])}</td>
        </tr>
        <tr>
          <td style="padding:3px 10px 3px 0;color:#666">Tagged elements</td>
          <td>{len(info["elements"])}</td>
        </tr>
        <tr>
          <td style="padding:3px 10px 3px 0;color:#666">MCID-wired</td>
          <td>{info["wired"]}</td>
        </tr>
      </table>
      {tree_section}
    </div>
    """


def main() -> None:
    original = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_ORIGINAL
    tagged   = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_TAGGED

    for p in (original, tagged):
        if not p.exists():
            print(f"Error: not found: {p}", file=sys.stderr)
            sys.exit(1)

    print(f"Reading {original.name} ...")
    before = pdf_info(original)
    print(f"Reading {tagged.name} ...")
    after  = pdf_info(tagged)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>PDF Tag Structure: Before / After</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         margin: 0; padding: 20px; background: #f4f4f4; color: #222; }}
  h1   {{ margin-bottom: 4px; }}
  .sub {{ color: #666; margin-top:0; margin-bottom:24px; }}
  .panels {{ display:flex; gap:20px; align-items:flex-start; }}
  .legend {{ margin-top:24px; font-size:0.85em; color:#666;
             border-top:1px solid #ddd; padding-top:12px; }}
</style>
</head>
<body>
<h1>PDF Accessibility — Tag Structure Comparison</h1>
<p class="sub">
  ADA/WCAG 2.1 §1.3.1 Info and Relationships ·
  PDF/UA-1 (ISO 14289-1) structure tree requirement
</p>
<div class="panels">
  {panel(before, "BEFORE (original)")}
  {panel(after,  "AFTER  (tagged)")}
</div>
<div class="legend">
  <strong>⛓ MCID-wired</strong> — struct element is linked to its exact glyph run in the
  page content stream via a Marked Content ID. A screen reader can navigate directly
  to the content. &nbsp;|&nbsp;
  <strong>◌ Alt text only</strong> — struct element exists in the tree with /Alt text,
  but has no content-stream link; AT can announce the element but cannot locate it on
  the page. &nbsp;|&nbsp;
  <strong>Empty left panel</strong> — flat PDF: a screen reader sees an undifferentiated
  stream of characters with no headings, lists, or reading order.
</div>
</body>
</html>"""

    REPORT.write_text(html, encoding="utf-8")
    print(f"\nReport written → {REPORT.resolve()}")
    webbrowser.open(REPORT.resolve().as_uri())


if __name__ == "__main__":
    main()
