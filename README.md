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
short_description: WCAG 2.1 AA audit and remediation for PDFs and Word docs
---

# ADA Compliance Tools

Two separate tools for auditing and remediating ADA Title II / WCAG 2.1 AA accessibility issues — one for documents (PDFs, Word files) and one for code repositories.

## What's in this repo

| Product | What it does | Who it's for | Location |
|---|---|---|---|
| ADA PDF Tool | Streamlit web app that audits PDFs and Word documents for WCAG 2.1 AA compliance and applies approved fixes | Researchers, academics, comms staff | `ada-pdf-tool/` |
| ADA Compliance Plugin | Claude Code plugin that audits code repositories via slash commands | Developers | `plugins/ada-compliance/` |

These are independent products. They share the same WCAG knowledge base and compatible CSV output schemas but have no runtime code dependency on each other.

For a technical deep-dive into both products, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Live deployment

The ADA PDF Tool is deployed as a HuggingFace Space at:

https://huggingface.co/spaces/ishijo/uw-ssec-ada-pdf-tool

This deployment updates only when commits are pushed to the `huggingface` remote (not `origin`). See [Deployment](#deployment-huggingface-spaces) below.

## Quick start — ADA PDF Tool (local)

```sh
cd ada-pdf-tool
cp .env.example .env
# Edit .env and set:
#   HYAK_ENDPOINT_URL — https://api.anthropic.com/v1 for direct Anthropic, or your Hyak gateway URL
#   HYAK_API_KEY      — your API key
#   HYAK_MODEL        — model string, e.g. claude-sonnet-4-6
pixi run app
```

Opens at http://localhost:8501. Requires [pixi](https://pixi.sh) and an API key for the Hyak gateway or Anthropic direct.

## Quick start — Plugin

Install [Claude Code](https://claude.ai/code), then point it at `plugins/ada-compliance/` as the plugin root. See [plugins/ada-compliance/README.md](plugins/ada-compliance/README.md) for full setup.

## Repository structure

```
ada-pdf-tool/          Streamlit document accessibility auditor (HuggingFace deploys this)
  app.py               Streamlit entry point
  core/                Extraction, analysis, remediation, dispatch layers
  prompts/             LLM system and user prompt templates
  dev/                 Local smoke test scripts
  tests/               Unit and evaluation tests
  pixi.toml            Dependency manifest — source of truth for local development
  requirements.txt     PyPI pin list — mirrors pixi.toml, used by HuggingFace only
  packages.txt         apt package list — used by HuggingFace only
  .streamlit/          Streamlit theme and server config

plugins/
  ada-compliance/      Claude Code plugin
    agents/            Compliance reviewer agents
    commands/          Slash command definitions
    skills/            WCAG knowledge base (shared reference)

samples/               Sample documents for testing (gitignored — not committed)

requirements.txt       Root-level PyPI pin list — for HuggingFace only, mirrors ada-pdf-tool/requirements.txt
packages.txt           Root-level apt package list — for HuggingFace only, mirrors ada-pdf-tool/packages.txt
```

> **Note:** `requirements.txt` and `packages.txt` at the repository root exist solely for HuggingFace Spaces deployment. They are not the source of truth for dependencies. For local development, use `pixi` from inside `ada-pdf-tool/`.

## Deployment (HuggingFace Spaces)

The Space is backed by two git remotes:

| Remote | URL | Purpose |
|---|---|---|
| `origin` | GitHub | Source of truth, PRs, CI |
| `huggingface` | `https://huggingface.co/spaces/ishijo/uw-ssec-ada-pdf-tool` | HuggingFace Spaces deployment |

Push to both remotes to keep them in sync:

```sh
git push origin main
git push huggingface main
```

**How HuggingFace reads this repo:**

- `app_file` in the YAML front matter above → HF runs `streamlit run ada-pdf-tool/app.py`
- `requirements.txt` at the **repository root** → HF installs Python dependencies
- `packages.txt` at the **repository root** → HF installs apt system packages (libgl1, poppler-utils, etc.)
- `sdk_version` in the YAML front matter → HF selects the Streamlit version

**Binary file history:** HuggingFace rejects repositories with large binary files in git history. Before pushing to the `huggingface` remote, purge binary files (PDFs, images, lock files) from history using `git-filter-repo`. This is a one-time step per developer.

**Secrets:** The three environment variables are set in HuggingFace Space settings under *Repository secrets* — do not commit them. For local development they go in `ada-pdf-tool/.env`.

| Secret | Value |
|---|---|
| `HYAK_ENDPOINT_URL` | Hyak gateway URL or `https://api.anthropic.com/v1` |
| `HYAK_API_KEY` | Your API key |
| `HYAK_MODEL` | Model string, e.g. `claude-sonnet-4-6` |

## Context

ADA Title II was amended in 2024 to require public entities — including universities and government agencies — to make their digital content meet WCAG 2.1 Level AA by April 24, 2026. See the [ADA Fact Sheet at ada.gov](https://www.ada.gov/resources/2024-03-08-web-accessibility-rule-fact-sheet/) for the official summary.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for branching, commit conventions, and deployment workflow.

See [ARCHITECTURE.md](ARCHITECTURE.md) for technical design documentation.
