# ADA PDF Tool

A Streamlit web application that audits PDFs and Word documents for WCAG 2.1 AA accessibility violations, presents findings for human review, and writes fixes only after explicit approval.

## What it does

The tool runs a four-stage workflow:

1. **Upload** — drag and drop a PDF or docx file
2. **Audit** — an LLM analyzes the extracted document content against nine WCAG 2.1 AA criteria and classifies each finding as auto-fixable or requiring human input
3. **Approve** — a checklist shows every proposed fix before anything is written; the user selects which fixes to apply and supplies any required inputs (alt text, heading corrections)
4. **Download** — the remediated file, an audit CSV, and an HTML diff report

Three input types are supported: tagged PDFs (have an existing accessibility tag tree), untagged PDFs (no tag tree), and Word documents (docx). Each routes through a different remediation path. The original file is never modified.

## WCAG criteria covered

| Criterion | What it checks | Auto-fixable? |
|---|---|---|
| 1.1.1 Non-text content | Alt text for images and figures | Human input required (all paths) |
| 1.3.1 Info and relationships | Heading tags, table headers, list markup | Yes (docx); No for structural tags on untagged PDF (rebuilt as Word) |
| 1.3.2 Meaningful sequence | Reading order of extracted content | Human review |
| 2.4.1 Bypass blocks | Bookmark/outline navigation | Yes (tagged PDF, docx) |
| 2.4.2 Page titled | Document title metadata | Yes (all paths) |
| 2.4.3 Focus order | Logical tab order for links | Human review |
| 2.4.6 Headings and labels | Heading hierarchy consistency | Yes (docx); No for tag writes on untagged PDF |
| 3.1.1 Language of page | Document language metadata | Yes (all paths) |
| 3.3.2 Labels or instructions | Form field labels | Human review |

## Requirements

- Python 3.11+
- [pixi](https://pixi.sh) (SSEC standard package manager)
- API key: Anthropic direct or Hyak gateway endpoint

## Setup

1. Clone the repo
2. `cd ada-pdf-tool`
3. Install pixi if not already installed: [pixi.sh/docs/installation](https://pixi.sh/docs/installation)
4. `cp .env.example .env`
5. Edit `.env`:
   - `HYAK_ENDPOINT_URL` — set to `https://api.anthropic.com/v1` for direct Anthropic access, or your Hyak gateway URL if using SSEC infrastructure
   - `HYAK_API_KEY` — your API key
   - `HYAK_MODEL` — model string, e.g. `claude-sonnet-4-6` (default)
6. `pixi run app`

## Running

| Command | What it does |
|---|---|
| `pixi run app` | Start the Streamlit app |
| `pixi run test` | Run unit tests |
| `pixi run eval` | Run evaluation pipeline |
| `pixi run extract` | Run extraction smoke test (`dev/test_extraction.py`) |
| `pixi run bookmarks` | Run bookmark write smoke test (`dev/test_bookmarks.py`) |
| `pixi run smoke` | Import check for docling and pikepdf |
| `pixi run rebuild` | Import check for rebuilder module |

## Architecture

Five layers:

- **Extraction** — docling reads programmatic PDFs and extracts text, font metadata, bounding boxes, table structure, and reading order; python-docx reads Word files
- **LLM analysis** — extracted content is sent to the Hyak gateway (an OpenAI-compatible endpoint covering Claude and open-source models on SSEC GPU infrastructure); the model returns structured JSON findings against the WCAG ruleset
- **Human approval gate** — Streamlit Stage 3 shows every proposed fix as a checklist; nothing is written until the user clicks Apply
- **Remediation** — pikepdf writes metadata and bookmarks to tagged PDFs; a rebuilder module reconstructs untagged PDFs as structured Word documents; python-docx applies structural fixes to docx files
- **Output** — remediated file, audit CSV (compatible with plugin compliance matrix schema), HTML diff report

### Three input routing paths

- **Tagged PDF** — pikepdf writes document language, title metadata, and bookmarks directly to the existing PDF. Structural tag writes (heading tags, alt text in the tag tree) are not yet implemented; those findings are reported but not auto-applied.
- **Untagged PDF** — docling and pymupdf extract content; the rebuilder assembles it into a structured Word document with correct heading styles, table headers, and alt text placeholders. The user re-exports the Word document as a tagged PDF using Word or Acrobat.
- **docx** — python-docx applies all structural fixes in-place: heading levels, table headers, language, title, alt text, bookmarks.

## Input types

| Input | Has tag tree | Remediation approach | Best for |
|---|---|---|---|
| Tagged PDF | Yes | pikepdf writes metadata and bookmarks; structural tag writes not yet implemented | Institutional PDFs from Acrobat or InDesign |
| Untagged PDF | No | Rebuilt as a structured Word document via docling + pymupdf + rebuilder | Research documents, lab reports |
| docx | N/A | python-docx applies all fixes in-place | Word-authored documents |

## Known limitations

- Scanned PDFs with no embedded text are not supported (docling requires programmatic text)
- Tagged PDF structural remediation — writing heading tags and alt text directly into the PDF tag tree — is not yet implemented; these findings are reported but require manual remediation in Acrobat
- Alt text for images, figures, and mathematical equations requires human input; auto-generated alt text is unreliable for scientific figures and equations
- Batch processing is not supported (one file per session)
- No password-protected PDFs
- No visual or aesthetic fixes (color contrast, font size)
- HTML, Markdown, PowerPoint, and Excel are not supported in v1

## Directory structure

```
ada-pdf-tool/
  app.py                  Streamlit entry point; four-stage UI
  config.py               Environment variable loading and LLM backend config
  core/
    extractor.py          docling PDF extraction and python-docx extraction
    analyzer.py           LLM audit logic via Hyak backend
    remediator.py         pikepdf and python-docx fix writing
    rebuilder.py          Untagged PDF → structured Word document rebuilder
    dispatch.py           Routes each input type to the correct pipeline
    diff_reporter.py      Generates HTML before/after diff report
    models.py             Shared data models (AuditReport, Finding)
    _image_helpers.py     Image extraction utilities
    _validation.py        Fix validation helpers
    backends/
      hyak_backend.py     OpenAI-compatible Hyak gateway client
  prompts/
    audit_system.md       System prompt: WCAG ruleset, classification rules, JSON schema
    audit_user.md         User prompt template with extraction data
  dev/                    Local smoke test scripts (not run in CI)
    test_extraction.py    Extraction smoke test (pixi run extract)
    test_bookmarks.py     Bookmark write smoke test (pixi run bookmarks)
    test_roundtrip.py     PDF read/write roundtrip smoke test
    test_tags.py          Tag structure smoke test
    README.md             Manual smoke test checklist
  tests/
    eval/                 Evaluation pipeline (precision/recall per criterion)
    unit/                 Unit tests
  pixi.toml               Dependency manifest (source of truth — never use requirements.txt)
  pixi.lock               Committed lockfile for reproducibility
  .env.example            Environment variable template
```

## Dependencies

`pixi.toml` is the source of truth for all dependencies. Never use `requirements.txt`. Add dependencies with:

```sh
pixi add --pypi <package>
```

Key dependencies: `docling` (PDF extraction), `pikepdf` (PDF tag writing), `python-docx` (Word file handling), `streamlit` (UI), `openai` (Hyak gateway client), `pymupdf` (image extraction for rebuilder), `streamlit-pdf-viewer` (persistent PDF sidebar in the UI).

## Evaluation pipeline

`tests/eval/` contains the evaluation framework for measuring precision and recall per WCAG criterion against ground-truth labeled documents. Currently in progress.
