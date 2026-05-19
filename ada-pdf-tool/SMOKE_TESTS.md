# PDF Remediation Smoke Tests

Three end-to-end scripts that demonstrate the before/after pipeline for
ADA-compliant PDF remediation. Each operates on a real PDF using only
the libraries already in the pixi environment (docling + pikepdf) — no
LLMs, no API calls, no placeholder backends.

---

## 1. Extraction — `test_extraction.py`

### Run
```
pixi run extract samples/IV-A\ 2024.pdf
```

### Input
- Any programmatic PDF (embedded text required; scanned PDFs are rejected)
- Sample used: `samples/IV-A 2024.pdf`

### Output
- `extraction_output.json` — structured JSON with one entry per page,
  each containing a list of elements:

```json
{
  "file_type": "pdf",
  "metadata": { "title": "...", "language": null, "page_count": 9 },
  "pages": [
    {
      "page_number": 1,
      "elements": [
        {
          "id": "el_001",
          "type": "text",
          "docling_label": "section_header",
          "text": "I. Background",
          "font_size": null,
          "font_bold": null,
          "bbox": [36.0, 540.0, 180.0, 554.0],
          "current_tag": null
        }
      ]
    }
  ]
}
```

### WCAG criteria enabled (prerequisite)
This test does not itself remediate the PDF. It produces the structured
data that the two remediation tests below consume.

### How it works
docling's `DocumentConverter` runs its PDF pipeline (OCR disabled) and
classifies every content item with a semantic label: `section_header`,
`title`, `text`, `paragraph`, `list_item`, `caption`, `picture`,
`table`, etc. The extractor maps these into a flat, page-keyed JSON
schema that downstream tools can query without touching the original PDF.

---

## 2. Bookmarks — `test_bookmarks.py`

### Run
```
pixi run bookmarks
```

### Input
- `samples/IV-A 2024.pdf` (original, never modified)
- Extraction JSON produced by running `extract()` on that PDF at runtime

### Output
- `tests/eval/sample_pdfs/output_bookmarks.pdf`
- Terminal summary:

```
Added 7 bookmarks: ['I. Background',
  'OBSERVATION OF THE MARANGONI EFFECT USING SCHLIEREN OPTICS',
  'II. Objective', 'III. Experimental Procedure',
  'IV. Treatment of Data', 'V. Questions for Discussion',
  'VI. References']
```

- The output PDF opens with the bookmarks panel visible
  (`/PageMode /UseOutlines` is set in the PDF root).

### WCAG criteria addressed

| Criterion | Level | How |
|-----------|-------|-----|
| **2.4.1** Bypass Blocks | A | Users can jump directly to any section without reading sequentially through all prior content |
| **2.4.5** Multiple Ways | AA | Bookmarks provide an additional navigation mechanism beyond linear page scrolling |

### How it works
The extractor labels every element with a docling semantic type. Elements
labelled `section_header` or `title` are collected in page order and
written as a flat `/Outlines` tree using `pikepdf.open_outline()`. Each
`OutlineItem` stores the heading text as its label and targets the
corresponding page (0-indexed). `/PageMode /UseOutlines` is injected
into the PDF root so viewers open the bookmarks sidebar automatically.

---

## 3. Tagged Structure Tree — `test_tags.py`

### Run
```
pixi run tags
```

### Input
- `samples/IV-A 2024.pdf` (original, never modified)
- Extraction JSON produced at runtime (67 taggable elements found)

### Output
- `tests/eval/sample_pdfs/output_tagged.pdf`
- `tag_comparison.html` (run `python compare_tags.py` to regenerate and open)
- Terminal summary:

```
Wired 66/67 elements across 9 pages

Verification (output_tagged.pdf):
  /MarkInfo /Marked  : True
  /StructTreeRoot    : True
  struct elements    : 67
  MCID-wired elems   : 66  ← linked to actual content stream
  Alt-text only      : 1   ← struct elem present, no content link
```

### Before / After (machine-verifiable)

| Property | Before | After |
|----------|--------|-------|
| `/MarkInfo /Marked` | `False` | `True` |
| `/StructTreeRoot` | absent | present |
| Structure elements | 0 | 67 |
| MCID-wired to content | 0 | 66 |

### WCAG criteria addressed

| Criterion | Level | How |
|-----------|-------|-----|
| **1.3.1** Info and Relationships | A | `<H2>`, `<P>`, `<LI>`, `<Caption>` tags make semantic structure programmatically determinable — not just visually implied by font size or indentation |
| **1.3.2** Meaningful Sequence | A | The struct tree defines reading order so assistive technology traverses content correctly, not in raw glyph-stream order |
| **2.4.6** Headings and Labels | AA | H1/H2 tags allow screen readers to announce heading level and let users jump between headings by keyboard |

### How it works
Three layers are written in a single pikepdf pass:

1. **Content stream marking** — every page's drawing commands are parsed
   into a list of PDF operators. The extracted text corpus for each page
   is searched for each element's text string; when found, a `BDC` (Begin
   Marked Content Dictionary) operator carrying `{/MCID N}` is injected
   immediately before the matching text operators and an `EMC` (End Marked
   Content) after them. 66 of 67 elements were matched this way.

2. **Structure tree** — a `/StructTreeRoot` is built with a `Document`
   container element whose children are one struct element per extracted
   item (`/S /H2`, `/S /P`, `/S /LI`, etc.). Each struct element carries
   `/Pg` (page reference), `/Alt` (extracted text for AT fallback), and
   `/K` (an MCR dict linking it to its MCID).

3. **ParentTree** — a number tree in the StructTreeRoot maps each page's
   MCID back to its parent struct element, closing the PDF/UA round-trip
   so viewers can resolve "which struct element owns this glyph run?"

### Remaining gaps (not yet addressed)

| WCAG | What is still missing |
|------|-----------------------|
| **1.1.1** Non-text Content | Images need verified `/Alt` text |
| **1.3.1** (partial) | Tables need `<TH>`/`<TD>` struct elements with scope |
| **2.4.2** Page Titled | `/Title` entry in document metadata |
| **3.1.1** Language of Page | `/Lang` in the PDF root |

---

## Environment

| Tool | Version | Purpose |
|------|---------|---------|
| docling | ≥ 2.93 | PDF text extraction and semantic labelling |
| pikepdf | ≥ 9.0 (conda-forge) | PDF read/write, content stream parsing |
| Python | 3.14 | Runtime |
| pixi | — | Environment and task runner |

All tasks run offline with no network calls after the initial pixi install.
