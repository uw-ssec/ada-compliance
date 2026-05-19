# ADA PDF Tool — Project Context

## What this project is

A standalone Streamlit web application that audits PDFs and Word 
documents for ADA Title II / WCAG 2.1 AA accessibility violations, 
presents findings in a structured reviewable UI, applies auto-fixable 
changes only after explicit user approval, and returns a remediated 
file with a downloadable audit report.

This is NOT a Claude Code plugin. It is a browser-based tool targeting 
non-technical users like communications staff and accessibility 
coordinators who work directly with documents.

## Background

### The Plugin (separate, already built)
There is an existing Claude Code plugin (`plugins/ada-compliance/`) 
in the same repository. It audits code repositories via slash commands 
(/ada-audit, /ada-check etc.) for developers. It is complete, pushed, 
and must not be touched. This tool is a completely separate product 
that shares WCAG knowledge conceptually but has no code dependency 
on the plugin.

### Why this tool exists
The primary users are UW professors, research assistants, and academic 
staff who have existing research materials — lab writeups, reports, 
papers, lecture documents — that need to meet ADA Title II / WCAG 2.1 
AA accessibility standards. These documents are the primary sample 
inputs and the primary use case the tool is designed around.

A secondary beneficiary is communications staff like accessibility 
coordinators who handle institutional documents, but the tool is 
scoped and prioritized around research document workflows first.

User research on PDF pain points (heading hierarchy, link tagging, 
table markup, bookmarks) informed the tool design. The key lesson: 
a naive broad Claude prompt acts without auditing first, removes 
manually-added content, and makes accessibility scores worse. 
This tool's design principle is the opposite: audit first, explain 
everything, let the user decide, then act.

### Primary document type: research lab documents
Sample document confirmed: a physical chemistry lab writeup 
(Experiment I-B, Surface Tension Measurement). Characteristics 
of this document type the tool must handle:

- Multi-level heading hierarchy inferred from numbering conventions 
  (I., II., A., B.) not just font size
- Mathematical equations rendered as images — require descriptive 
  alt text, not auto-generated
- Scientific figures and diagrams — require human-authored alt text 
  explaining what the diagram conveys
- Data tables with header rows
- Footnotes and reference sections affecting reading order
- Mix of body text and indented procedural steps

The tool must treat equation images as a distinct subtype in the 
human review bucket with a specific prompt:
"This appears to be a mathematical equation. Provide a text 
description (e.g. 'W equals 2 pi r sigma where W is drop weight, 
r is radius, and sigma is surface tension')."

A secondary smoke test document is an 81-page institutional report 
PDF (aesthetically complex, known accessibility issues, Adobe 
Acrobat fails on it) — represents the hardest real-world case.

## Repository and branch

Repository: uw-ssec/rse-plugins (same repo as the plugin)
Branch: feat/ada-pdf-streamlit
Directory: ada-pdf-tool/ (top-level, completely separate from 
plugins/)

The plugin lives in plugins/ada-compliance/ and must never be 
touched.

## Directory structure

ada-pdf-tool/
  app.py                  ← Streamlit entry point
  config.py               ← LLM backend config, env var loading
  core/
    extractor.py          ← docling + python-docx extraction ✓ DONE
    analyzer.py           ← LLM audit logic, abstracted backend
    remediator.py         ← pikepdf + python-docx fix writing
    models.py             ← shared data models ✓ DONE
    backends/
      base.py             ← LLMBackend abstract interface
      hyak_backend.py     ← Hyak gateway backend (OpenAI-compatible)
  prompts/
    audit_system.md       ← system prompt for LLM
    audit_user.md         ← user prompt template
  tests/
    eval/
      sample_pdfs/
      expected_outputs/
      test_audit_eval.py
    unit/
  pixi.toml               ← SSEC standard dependency manifest
  pixi.lock               ← committed lockfile
  .env.example
  README.md
  test_extraction.py      ← extraction smoke test ✓ DONE

Note: requirements.txt has been removed. pixi is the package 
manager per SSEC standards.

## Tech stack — what each tool does and why

### docling (MIT, free, local)
IBM Research open-source library. Extracts text at char/word/line 
level with precise bounding box coordinates, font size and bold 
metadata, table structure recognition, and reading order from 
programmatic PDFs. This geometric data is what makes heading 
hierarchy inference possible — we can infer that bold 18pt text 
at the top of a column is probably H1 even with no tag assigned. 
Runs entirely locally, no API calls. Replaces pdfplumber (which 
was dropped because docling does everything pdfplumber does and 
more, keeping the dependency list clean).

### pikepdf (MIT, free, local)
The only open-source Python tool that can read and write the PDF 
internal tag tree (/StructTreeRoot). This is what accessibility 
actually depends on — not the visual appearance but the semantic 
tags. Handles: heading tags, link annotations, document metadata 
(title, language), bookmarks (/Outlines). Without pikepdf you can 
audit but not remediate.

### python-docx (MIT, free, local)
For Word document support. docx is XML under the hood so heading 
levels are stored explicitly (Heading 1, Heading 2) making 
remediation more tractable than PDF.

### Streamlit (Apache 2.0, free, local)
Python-native UI. No frontend build step. Can be run locally by 
each team or hosted on SSEC servers. Chosen because a research 
org should not be maintaining a React frontend.

### openai SDK (MIT, free)
Used as the HTTP client for the Hyak gateway — not OpenAI the 
company. The gateway is OpenAI-compatible so this SDK works 
regardless of which underlying model is selected.

### ChromaDB (Apache 2.0, free, local)
In-process vector store. Not used in v1 but included in 
architecture for potential v2 RAG use case. Runs with no server 
required.

## Environment management (SSEC standard)

SSEC uses pixi, not pip or conda directly. 

pixi.toml    ← dependency manifest (replaces requirements.txt)
pixi.lock    ← lockfile, committed to repo for reproducibility

Adding dependencies:
  pixi add --pypi <package>

Running the tool:
  pixi run app        ← streamlit run app.py
  pixi run extract    ← python test_extraction.py
  pixi run test       ← pytest tests/
  pixi run eval       ← pytest tests/eval/
  pixi run smoke      ← python -c "import docling; import pikepdf; print('OK')"

Never create requirements.txt. Never use bare pip install.

## LLM layer — Hyak gateway

Don has set up an OpenAI-compatible API gateway (Hyak) that sits 
in front of multiple models under a single endpoint and API key. 
No separate credentials per provider.

Models available:
- Claude Sonnet 4.6, Opus 4.6, Haiku (via Anthropic)
- Gemma, Olmo, Devstral (running on SSEC's Hyak GPU cluster)
- GPT models (via Microsoft/OpenAI credits)

v1 — use Claude via the Hyak gateway
v2 — switch to Gemma or Olmo via the same endpoint, zero cost, 
     data stays on SSEC infrastructure

Because the gateway is OpenAI-compatible, the backend uses the 
openai Python SDK regardless of which model is selected. Switching 
models requires changing one environment variable only.

The LLMBackend abstraction is a single HyakBackend class — no 
separate Anthropic/Ollama backends needed.

Config (.env):
  HYAK_ENDPOINT_URL=<get from Don>
  HYAK_API_KEY=<get from Don>
  HYAK_MODEL=claude-sonnet-4-6   # or: gemma, olmo, devstral

## LLM backend interface

class LLMBackend:
    def audit(self, extraction: dict) -> AuditReport:
        raise NotImplementedError

class HyakBackend(LLMBackend):
    # openai SDK with custom base_url=HYAK_ENDPOINT_URL
    # model name from HYAK_MODEL env var

## The four stages of the UI

### Stage 1 — Upload
Single screen. PDF or docx drag-and-drop. One Analyze button. 
If scanned PDF detected: clear error message, no silent failure.

### Stage 2 — Audit Report
Three sections:

🔴 Auto-Fixable — high-confidence fixes. Each is a collapsed 
expandable tile showing: page reference, element, current state, 
proposed fix, WCAG criterion, confidence level.

🟡 Human Review Required — issues needing judgment. Each tile 
shows what was detected, why it needs human input, WCAG criterion, 
and an optional text input field (e.g. for alt text). If filled, 
item moves to fix queue. Equation images get a specific prompt:
"This appears to be a mathematical equation. Provide a text 
description (e.g. 'W equals 2 pi r sigma where W is drop weight, 
r is radius, and sigma is surface tension')."

✅ Already Correct — passing elements. Collapsed list, expandable. 
Shows what was checked and why it passes. Exists so the user knows 
exactly what will not be touched.

### Stage 3 — Review and Approve
Checklist of every proposed fix before anything is written:

[ ✓ ] Page 2 — "Executive Summary" → tag as H1    [High]
[ ✓ ] Page 5 — hyperlink → add Link tag            [High]
[ ✓ ] Metadata — Language → set to en-US           [High]
[ ✓ ] Bookmarks — missing → generate from headings [High]
[ □ ] Page 9 — Table headers ambiguous             [Medium]
[ - ] Page 4 — Image alt text → SKIPPED            [No fix]
[ ✓ ] Page 4 — Image alt text → "aerial view"     [User-entered]

Rules:
- High confidence: checked by default
- Medium confidence: unchecked by default, caution note shown
- Skipped items: greyed out with reason
- User-entered values: appear as checked rows
- Select All / Deselect All controls at top
- Live summary: "14 fixes selected, 2 skipped, 1 needs follow-up"
- Single button: Apply Selected Fixes

### Stage 4 — Download
Summary card with counts. Two downloads:
- Remediated file (never the original)
- Audit report CSV (schema below)
Run another file button resets to Stage 1.

## Audit report CSV schema

resource, page, wcag_criterion, severity, issue, proposed_fix, 
status, confidence, verification_path

Compatible with the plugin's compliance matrix output schema so 
findings from both tools can be merged if needed.

## What the LLM receives

System prompt (from prompts/audit_system.md): full WCAG 2.1 AA 
ruleset for documents, UW policy mapping, classification logic, 
confidence scoring rules, required JSON output schema. No prose 
output — structured JSON only.

User prompt (from prompts/audit_user.md): docling extraction JSON 
interpolated in.

Expected response schema:
{
  "findings": [
    {
      "element_id": "el_001",
      "page": 1,
      "wcag_criterion": "1.3.1",
      "severity": "critical",
      "classification": "auto-fix",
      "confidence": "high",
      "current_state": "Bold 18pt text, no heading tag",
      "proposed_fix": "Tag as H1",
      "reasoning": "Largest font on page",
      "verification_path": null
    }
  ],
  "preserve": ["el_005"],
  "metadata_fixes": [
    { "field": "language", "value": "en-US" },
    { "field": "title", "value": "Experiment I-B" }
  ]
}

## What the tool will NOT do in v1

- No scanned PDF support (docling requires programmatic PDFs)
- No alt text generation (human judgment call, deliberate)
- No batch processing (one file at a time)
- No visual PDF page rendering (v2)
- No DubBot integration (post-fix verification is manual)
- No modification of the uploaded original (always new file)
- No cloud storage or server-side persistence (session only)
- No password-protected PDFs
- No visual/aesthetic fixes (color contrast etc.)
- No HTML, Markdown, pptx, xlsx (v2 file types)

## SSEC development standards

### Commit messages
All commits follow conventional commits v1.0:
  feat(extraction): add equation image detection
  fix(analyzer): handle null font_size from docling
  docs(readme): add pixi installation instructions
  test(eval): add heading detection ground truth
  chore(deps): add pikepdf to pixi.toml

Types: feat, fix, docs, style, refactor, perf, test, build, 
ci, chore, revert

### Git workflow
Fork → branch on fork → PR to upstream.
Current working branch: feat/ada-pdf-streamlit

### rse-plugins skills to reference during development

Before starting each layer, read the relevant skill from the 
rse-plugins repo. In Claude Code, tell CC:
"Before implementing, read the skill at 
plugins/scientific-python-development/skills/<skill>/SKILL.md"

| When working on... | Read this skill first |
|---|---|
| pixi.toml, adding deps | pixi-package-manager |
| Any test or eval code | python-testing |
| README, CONTRIBUTING | community-health-files + scientific-documentation |
| pyproject.toml (if needed) | python-packaging |

Skill paths:
- plugins/scientific-python-development/skills/pixi-package-manager/
- plugins/scientific-python-development/skills/python-testing/
- plugins/scientific-python-development/skills/scientific-documentation/
- plugins/scientific-python-development/skills/python-packaging/
- plugins/project-management/skills/community-health-files/

## Cost summary

docling         free, MIT, local
pikepdf         free, MIT, local
python-docx     free, MIT, local
Streamlit       free, Apache 2.0, local
openai SDK      free, MIT (client only)
ChromaDB        free, Apache 2.0, local (v2)
pytest          free, MIT
Hyak gateway    free to use (SSEC infrastructure)
  └─ Claude models    via Anthropic (cost absorbed by SSEC/Hyak)
  └─ Gemma/Olmo       free, runs on SSEC GPU cluster

## SSEC justification

"The extraction, remediation, UI, and evaluation layers are 
entirely open source with zero ongoing cost. The LLM layer routes 
through SSEC's Hyak gateway — a unified OpenAI-compatible endpoint 
covering both commercial models (Claude) and open-source models 
(Gemma, Olmo) running on existing SSEC GPU infrastructure. 
Switching from Claude to a local model requires changing one 
environment variable with zero code changes. The tool runs locally 
so any UW team can self-serve without central infrastructure."

## Current state

Branch: feat/ada-pdf-streamlit
Directory: ada-pdf-tool/ scaffolded and partially implemented.

Completed:
- core/extractor.py — docling PDF extraction implemented and 
  smoke-tested on one PDF. Docling labels applied to extracted 
  elements (text, image, table etc.)
- core/models.py — data models implemented
- test_extraction.py — runs extraction on a sample PDF
- pixi.toml + pixi.lock — SSEC-compliant dependency management 
  (migrated from requirements.txt)

Not started:
- core/analyzer.py — LLM analysis layer (next)
- core/remediator.py
- core/backends/hyak_backend.py
- prompts/audit_system.md
- prompts/audit_user.md
- app.py (Streamlit UI)
- tests/eval/

Primary smoke test documents:
1. Physical chemistry lab writeup (Experiment I-B) — primary 
   target document type, research lab format
2. 81-page institutional report PDF — hardest real-world case

## Build order (remaining work)

Issue 1 (retro): core/extractor.py — DONE, close on creation
Issue 2: feat(extraction) — add docx support to extractor.py
Issue 3: feat(llm) — implement Hyak gateway analyzer
Issue 4: feat(remediation) — implement pikepdf remediator
Issue 5: feat(ui) — Streamlit stages 1 and 2
Issue 6: feat(ui) — Streamlit stages 3 and 4
Issue 7: test(eval) — evaluation pipeline
Issue 8: docs — README and community health files