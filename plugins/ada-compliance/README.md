# ADA Compliance Plugin for Claude Code

A Claude Code plugin that audits code repositories for WCAG 2.1 AA / ADA Title II accessibility issues via slash commands, using a hierarchy of specialist reviewer agents and a shared WCAG knowledge base.

## What it does

| Command | What it does |
|---|---|
| `/ada-audit` | Full WCAG 2.1 AA audit of the repository — scopes content, dispatches domain reviewers, produces compliance matrix |
| `/ada-check` | Quick single-file accessibility review routed to the appropriate specialist |
| `/ada-exception-check` | Evaluates whether a specific resource qualifies for an ADA Title II compliance exception |
| `/ada-report` | Emits the compliance matrix from the most recent audit as Markdown and CSV |

Output: compliance matrix CSV, per-criterion WCAG findings, exception eligibility report.

## Requirements

- [Claude Code](https://claude.ai/code) installed
- Access to a compatible Claude model (Sonnet or Opus)

## Setup

The plugin is a Claude Code plugin directory. To use it:

1. Clone this repository
2. In Claude Code, add the plugin directory to your project or workspace:
   - Point Claude Code to `plugins/ada-compliance/` as the plugin root
   - Alternatively, symlink or copy the directory into your target project's `.claude/plugins/` location
3. The slash commands (`/ada-audit`, `/ada-check`, `/ada-exception-check`, `/ada-report`) will become available in your Claude Code session

No additional dependencies or API keys are required beyond Claude Code itself.

## Architecture

### Agent hierarchy

- **compliance-lead** (orchestrator) — handles `/ada-audit`, `/ada-check`, `/ada-report`. Scopes the audit, classifies content by type, dispatches domain reviewer agents, and consolidates findings into a single prioritized compliance matrix.
- **Four domain reviewer agents** — each handles a content category:
  - `web-content-reviewer` — HTML, Markdown, text content (WCAG perceivability, operability)
  - `visual-design-reviewer` — color contrast, layout, non-text content
  - `document-reviewer` — `.ipynb`, `.md`, and other document-format files
  - `av-compliance-reviewer` — audio and video content (captions, audio descriptions)
- **exceptions-analyst** (specialist) — handles `/ada-exception-check`. Evaluates all five ADA Title II exception categories: archived content, preexisting documents, password-protected files, preexisting social media, and third-party content.

### Skills (knowledge base)

Six shared reference skills, readable by all agents:

| Skill | Contents |
|---|---|
| `wcag-title-ii-notes` | Authoritative WCAG 2.1 AA interpretation for ADA Title II (Noah C. Benson, UW eScience) |
| `wcag-website-requirements` | Per-criterion requirements for web content |
| `wcag-document-requirements` | Per-criterion requirements for non-HTML documents |
| `wcag-av-requirements` | Caption and audio description requirements |
| `wcag-exceptions` | Exception categories and eligibility criteria |
| `compliance-matrix-template` | Canonical output format — compliance matrix schema, CSV columns, status values |

Additional skills: `wcag-remediation-patterns`, `uw-policy-mapping`, `notebook-accessibility`, `dubbot-interpretation`.

## What it audits

File types: `.md`, `.ipynb`, `.html`, `.py`, and other text files in the repository.

The plugin does not audit binary files or PDFs. Use the [ADA PDF Tool](../../ada-pdf-tool/README.md) for document files.

## Output

The compliance matrix CSV has the following columns:

```
resource, page, wcag_criterion, severity, issue, proposed_fix, status, confidence, verification_path
```

`status` values: `pass`, `fail`, `manual-review`, `exception`, `not-applicable`

The findings report groups violations by WCAG criterion, lists affected files, and provides remediation guidance. The `/ada-report` command re-emits the matrix from the most recent audit without re-running the full analysis.

## Relationship to the ADA PDF Tool

The plugin and the PDF Tool are two separate products in this repository. The plugin is for code repositories and developer-facing content (`.md`, `.ipynb`, `.html`). The PDF Tool is for binary document files (PDF, docx). They share the same WCAG knowledge base through the skills directory, and the compliance matrix CSV schema is identical across both tools, so findings from a repository audit and a document audit can be merged into a single report.
