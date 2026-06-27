---
title: UW SSEC ADA PDF Tool
emoji: ♿
colorFrom: purple
colorTo: blue
sdk: streamlit
sdk_version: "1.57.0"
app_file: ada-pdf-tool/app.py
pinned: false
license: mit
short_description: Audit and remediate PDFs and Word docs for WCAG 2.1 AA compliance
---

# ADA Compliance Tools

This repository contains two separate tools for auditing and remediating ADA Title II / WCAG 2.1 AA accessibility issues — one for documents (PDFs, Word files) and one for code repositories.

## What's in this repo

| Product | What it does | Who it's for | Location |
|---|---|---|---|
| ADA PDF Tool | Streamlit web app that audits PDFs and Word documents for WCAG 2.1 AA compliance and applies approved fixes | Researchers, academics, comms staff | `ada-pdf-tool/` |
| ADA Compliance Plugin | Claude Code plugin that audits code repositories via slash commands | Developers | `plugins/ada-compliance/` |

For a technical deep-dive into how both products work, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Quick start

### ADA PDF Tool (Streamlit)

```sh
cd ada-pdf-tool
cp .env.example .env
# add your API key to .env
pixi run app
```

Opens at http://localhost:8501

### ADA Compliance Plugin

Install Claude Code, then:

```sh
cd plugins/ada-compliance
```

See [plugins/ada-compliance/README.md](plugins/ada-compliance/README.md) for setup.

## Repository structure

```
ada-pdf-tool/          Streamlit document accessibility auditor
  app.py               Streamlit entry point
  core/                Extraction, analysis, remediation, dispatch layers
  prompts/             LLM system and user prompt templates
  tests/               Unit and evaluation tests
  pixi.toml            Dependency manifest (source of truth)

plugins/
  ada-compliance/      Claude Code plugin
    agents/            Compliance reviewer agents
    commands/          Slash command definitions
    skills/            WCAG knowledge base (shared reference)

samples/               Sample documents for testing
```

## Context

ADA Title II was amended in 2024 to require public entities — including universities and government agencies — to make their digital content meet WCAG 2.1 Level AA by April 24, 2026. WCAG 2.1 AA is the Web Content Accessibility Guidelines standard covering perceivability, operability, understandability, and robustness for web and document content. See the [ADA Fact Sheet at ada.gov](https://www.ada.gov/resources/2024-03-08-web-accessibility-rule-fact-sheet/) for the official summary.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
