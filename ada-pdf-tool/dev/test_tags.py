#!/usr/bin/env python3
"""
Smoke test: add a fully-wired tagged PDF structure tree.

What this produces
------------------
- /MarkInfo /Marked true
- /StructTreeRoot  →  Document > [H1 | H2 | P | LI | Caption | Note]
- BDC … EMC markers injected into every page content stream, keyed by MCID
- /StructParents on each modified page
- ParentTree in StructTreeRoot linking MCIDs → struct elements

Each struct element carries:
  /S   — structure type (H1, H2, P, …)
  /Pg  — page reference
  /Alt — extracted text (≤ 500 chars), read by AT when element has no glyph content
  /K   — MCR dict {/Type /MCR, /Pg, /MCID} for elements that were matched in the stream

Usage
-----
    python test_tags.py [path-to-pdf]

Output: tests/eval/sample_pdfs/output_tagged.pdf
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pikepdf
from core.extractor import extract

LABEL_TO_STRUCT = {
    "title": "H1",
    "section_header": "H2",
    "text": "P",
    "paragraph": "P",
    "list_item": "LI",
    "caption": "Caption",
    "footnote": "Note",
}

DEFAULT_PDF = Path(__file__).parent.parent / "samples" / "IV-A 2024.pdf"
OUTPUT_PDF = (
    Path(__file__).parent
    / "tests"
    / "eval"
    / "sample_pdfs"
    / "output_tagged.pdf"
)


# ── extraction ────────────────────────────────────────────────────────────────

def collect_elements(extraction: dict) -> list[dict]:
    elements = []
    for page in extraction["pages"]:
        for el in page["elements"]:
            label = el.get("docling_label", "")
            if label in LABEL_TO_STRUCT:
                elements.append(
                    {
                        "text": (el.get("text") or "").strip(),
                        "label": label,
                        "struct_type": LABEL_TO_STRUCT[label],
                        "page_no": page["page_number"],
                    }
                )
    return elements


# ── content-stream helpers ────────────────────────────────────────────────────

def _stream_chars(instructions: list) -> list[tuple[str, int]]:
    """
    Return [(char, instruction_index), …] for every character shown by
    Tj / TJ operators in the instruction list.
    """
    result = []
    for idx, (operands, operator) in enumerate(instructions):
        op = str(operator)
        if op == "Tj" and operands:
            try:
                for ch in str(operands[0]):
                    result.append((ch, idx))
            except Exception:
                pass
        elif op == "TJ" and operands:
            try:
                for item in operands[0]:
                    if isinstance(item, pikepdf.String):
                        for ch in str(item):
                            result.append((ch, idx))
            except Exception:
                pass
    return result


def _find_in_stream(
    el_text: str,
    page_text: str,
    char_positions: list[tuple[str, int]],
    used_ranges: list[tuple[int, int]],
) -> tuple[int, int] | None:
    """
    Find el_text in page_text (starting from after already-used ranges).
    Returns (start_instruction_idx, end_instruction_idx) or None.

    Tries progressively shorter prefixes to handle truncated / wrapped text.
    """
    search_len = min(len(el_text), 40)
    while search_len >= 8:
        needle = el_text[:search_len].strip()
        start = 0
        while True:
            pos = page_text.find(needle, start)
            if pos < 0:
                break
            end_pos = min(pos + len(el_text) - 1, len(char_positions) - 1)
            si = char_positions[pos][1]
            ei = char_positions[end_pos][1]
            # Reject if overlapping a used range
            if not any(si <= er and ei >= sr for sr, er in used_ranges):
                return si, ei
            start = pos + 1
        search_len -= 8
    return None


# ── main pipeline ─────────────────────────────────────────────────────────────

def tag_pdf(pdf: pikepdf.Pdf, elements: list[dict]) -> dict[int, list[tuple[int, dict]]]:
    """
    1. Inject BDC/EMC markers into page content streams.
    2. Return page_mcid_map: {page_no: [(mcid, element), …]}
    """
    by_page: dict[int, list[dict]] = {}
    for el in elements:
        by_page.setdefault(el["page_no"], []).append(el)

    page_mcid_map: dict[int, list[tuple[int, dict]]] = {}

    for page_no in sorted(by_page):
        page_els = by_page[page_no]
        page = pdf.pages[page_no - 1]

        try:
            instructions = list(pikepdf.parse_content_stream(page))
        except Exception as exc:
            print(f"  Warning: cannot parse content stream p{page_no}: {exc}")
            continue

        char_positions = _stream_chars(instructions)
        if not char_positions:
            continue
        page_text = "".join(ch for ch, _ in char_positions)

        # ── match elements to instruction ranges ──────────────────────────
        mcid = 0
        opens: dict[int, list[tuple[int, dict]]] = {}   # instr_idx → [(mcid, el)]
        closes: dict[int, list[tuple[int, dict]]] = {}
        tagged_on_page: list[tuple[int, dict]] = []
        used_ranges: list[tuple[int, int]] = []

        for el in page_els:
            match = _find_in_stream(el["text"], page_text, char_positions, used_ranges)
            if match is None:
                continue
            si, ei = match
            used_ranges.append((si, ei))
            opens.setdefault(si, []).append((mcid, el))
            closes.setdefault(ei, []).append((mcid, el))
            tagged_on_page.append((mcid, el))
            mcid += 1

        if not tagged_on_page:
            continue

        # ── rebuild instruction list with BDC/EMC ─────────────────────────
        new_instructions: list = []
        for idx, (operands, operator) in enumerate(instructions):
            # BDC(s) before this instruction
            for m, el in opens.get(idx, []):
                new_instructions.append(
                    (
                        [
                            pikepdf.Name("/" + el["struct_type"]),
                            pikepdf.Dictionary(MCID=m),
                        ],
                        pikepdf.Operator("BDC"),
                    )
                )
            new_instructions.append((operands, operator))
            # EMC(s) after this instruction
            for m, el in closes.get(idx, []):
                new_instructions.append(([], pikepdf.Operator("EMC")))

        new_content = pikepdf.unparse_content_stream(new_instructions)
        page.Contents = pdf.make_stream(new_content)
        page["/StructParents"] = page_no - 1
        page_mcid_map[page_no] = tagged_on_page

    return page_mcid_map


def build_struct_tree(
    pdf: pikepdf.Pdf,
    elements: list[dict],
    page_mcid_map: dict[int, list[tuple[int, dict]]],
) -> None:
    """Attach /MarkInfo and a fully-wired /StructTreeRoot to the PDF root."""

    struct_root = pdf.make_indirect(
        pikepdf.Dictionary(
            Type=pikepdf.Name("/StructTreeRoot"),
            K=pikepdf.Array(),
        )
    )

    doc_elem = pdf.make_indirect(
        pikepdf.Dictionary(
            Type=pikepdf.Name("/StructElem"),
            S=pikepdf.Name("/Document"),
            P=struct_root,
            K=pikepdf.Array(),
        )
    )
    struct_root.K.append(doc_elem)

    # page_idx → {mcid: struct_elem}  (for ParentTree)
    parent_tree_data: dict[int, dict[int, object]] = {}

    # Build a lookup: (page_no, mcid) → element identity check
    mcid_lookup: dict[int, dict[int, dict]] = {}
    for page_no, tagged in page_mcid_map.items():
        mcid_lookup[page_no] = {m: el for m, el in tagged}

    for el in elements:
        page_no = el["page_no"]
        page_idx = page_no - 1
        page_ref = pdf.pages[page_idx].obj if page_idx < len(pdf.pages) else None

        # Check if this element was successfully MCID-tagged
        mcid: int | None = None
        for m, tagged_el in page_mcid_map.get(page_no, []):
            if tagged_el is el:
                mcid = m
                break

        d = pikepdf.Dictionary(
            Type=pikepdf.Name("/StructElem"),
            S=pikepdf.Name("/" + el["struct_type"]),
            P=doc_elem,
            Alt=pikepdf.String(el["text"][:500]),
        )
        if page_ref is not None:
            d["/Pg"] = page_ref

        if mcid is not None and page_ref is not None:
            d["/K"] = pikepdf.Dictionary(
                Type=pikepdf.Name("/MCR"),
                Pg=page_ref,
                MCID=mcid,
            )

        struct_elem = pdf.make_indirect(d)
        doc_elem.K.append(struct_elem)

        if mcid is not None:
            parent_tree_data.setdefault(page_idx, {})[mcid] = struct_elem

    # ParentTree number tree: page_idx → array[mcid] = parent struct elem
    nums = pikepdf.Array()
    for page_idx in sorted(parent_tree_data):
        mcid_map = parent_tree_data[page_idx]
        if not mcid_map:
            continue
        max_mcid = max(mcid_map)
        arr = pikepdf.Array()
        for m in range(max_mcid + 1):
            if m in mcid_map:
                arr.append(mcid_map[m])
            else:
                arr.append(pdf.make_indirect(pikepdf.Dictionary()))  # placeholder
        nums.append(page_idx)
        nums.append(arr)

    struct_root["/ParentTree"] = pdf.make_indirect(
        pikepdf.Dictionary(Nums=nums)
    )
    pdf.Root["/StructTreeRoot"] = struct_root
    pdf.Root["/MarkInfo"] = pdf.make_indirect(
        pikepdf.Dictionary(Marked=True)
    )


# ── verification ──────────────────────────────────────────────────────────────

def verify(path: Path) -> None:
    with pikepdf.open(path) as pdf:
        marked = bool(
            pdf.Root.get("/MarkInfo", pikepdf.Dictionary()).get("/Marked", False)
        )
        has_tree = "/StructTreeRoot" in pdf.Root
        n_elems = 0
        n_wired = 0
        if has_tree:
            doc_kids = pdf.Root["/StructTreeRoot"].K[0].K
            n_elems = len(doc_kids)
            for kid in doc_kids:
                if "/K" in kid:
                    n_wired += 1

    print(f"\nVerification ({path.name}):")
    print(f"  /MarkInfo /Marked  : {marked}")
    print(f"  /StructTreeRoot    : {has_tree}")
    print(f"  struct elements    : {n_elems}")
    print(f"  MCID-wired elems   : {n_wired}  ← linked to actual content stream")
    print(f"  Alt-text only      : {n_elems - n_wired}  ← struct elem present, no content link")


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    pdf_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PDF
    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Extracting: {pdf_path} ...")
    extraction = extract(pdf_path)
    elements = collect_elements(extraction)
    print(f"Found {len(elements)} taggable elements\n")

    OUTPUT_PDF.parent.mkdir(parents=True, exist_ok=True)

    with pikepdf.open(pdf_path) as pdf:
        print("Injecting BDC/EMC markers into content streams ...")
        page_mcid_map = tag_pdf(pdf, elements)

        total_wired = sum(len(v) for v in page_mcid_map.values())
        print(f"  Wired {total_wired}/{len(elements)} elements across {len(page_mcid_map)} pages")

        print("Building structure tree ...")
        build_struct_tree(pdf, elements, page_mcid_map)

        pdf.save(OUTPUT_PDF)

    counts = {}
    for el in elements:
        counts[el["struct_type"]] = counts.get(el["struct_type"], 0) + 1
    print(f"\nWritten → {OUTPUT_PDF.resolve()}")
    print("  " + "  ".join(f"{k}×{v}" for k, v in sorted(counts.items())))

    verify(OUTPUT_PDF)


if __name__ == "__main__":
    main()
