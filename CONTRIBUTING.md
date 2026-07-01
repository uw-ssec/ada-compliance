# Contributing

## Repository structure

| Directory | Contents |
|---|---|
| `ada-pdf-tool/` | Streamlit document accessibility tool (Python, pixi) |
| `plugins/ada-compliance/` | Claude Code plugin (agent and skill definitions) |
| `samples/` | Sample documents for manual testing |

Shared configuration: `pixi.toml` and `pixi.lock` live in `ada-pdf-tool/` (the plugin has no runtime dependencies).

## Development setup

See each product's README for setup:

- [ada-pdf-tool/README.md](ada-pdf-tool/README.md)
- [plugins/ada-compliance/README.md](plugins/ada-compliance/README.md)

## HuggingFace Spaces deployment

The ADA PDF Tool is deployed as a HuggingFace Space. The repository has two git remotes:

| Remote | URL | Purpose |
|---|---|---|
| `origin` | `https://github.com/uw-ssec/rse-plugins` | GitHub — source of truth, PRs, CI |
| `huggingface` | `https://huggingface.co/spaces/ishijo/uw-ssec-ada-pdf-tool` | HuggingFace Spaces deployment |

Push to both remotes to keep GitHub and HF in sync:

```sh
git push origin main
git push huggingface main
```

A new developer must add the `huggingface` remote manually:

```sh
git remote add huggingface https://huggingface.co/spaces/ishijo/uw-ssec-ada-pdf-tool
```

### Files HuggingFace reads from the repository root

| File | Purpose |
|---|---|
| `requirements.txt` | Python dependencies installed by HF at deploy time |
| `packages.txt` | System apt packages installed by HF at deploy time |
| `README.md` | YAML front matter — `app_file`, `sdk`, `sdk_version` |

These files at the root mirror their counterparts in `ada-pdf-tool/`. If you add a dependency to `ada-pdf-tool/pixi.toml`, also add it to both `ada-pdf-tool/requirements.txt` and the root `requirements.txt`. If you add a system package to `ada-pdf-tool/packages.txt`, also add it to the root `packages.txt`.

### Binary file history

HuggingFace rejects repositories with large binary files in git history. Before pushing to the `huggingface` remote for the first time (or after committing binary files), purge them with `git-filter-repo`:

```sh
git filter-repo --strip-blobs-bigger-than 10M
git push huggingface main --force
```

`git-filter-repo` is a separate install: `pip install git-filter-repo` or `brew install git-filter-repo`.

### Secrets

The three environment variables are configured in HuggingFace Space settings under *Repository secrets*. Do not commit them. For local development they live in `ada-pdf-tool/.env` (gitignored).

| Secret | Description |
|---|---|
| `HYAK_ENDPOINT_URL` | Hyak gateway URL or `https://api.anthropic.com/v1` |
| `HYAK_API_KEY` | API key |
| `HYAK_MODEL` | Model string, e.g. `claude-sonnet-4-6` |

---

## Branching and commits

Active branches:

| Branch | Purpose |
|---|---|
| `main` | Stable |
| `feat/ada-pdf-streamlit` | Streamlit tool — active development |
| `chore/adopt-zizmor` | CI: zizmor security linting (unmerged) |

Commit convention: [Conventional Commits v1.0](https://www.conventionalcommits.org/en/v1.0.0/)

Format: `type(scope): description`

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`

Examples:

```
feat(extraction): add equation image detection
fix(rebuilder): hoist document title to output
docs(readme): update setup instructions
test(eval): add heading detection ground truth
chore(deps): add pikepdf to pixi.toml
```

## Open work

| Item | Status |
|---|---|
| Eval pipeline (precision/recall per WCAG criterion) | In progress — `tests/eval/` |
| Tagged PDF structural remediation via pikepdf | Not started |
| Full-fidelity rebuild: images, formulas, tables | In progress — `feat/faithful-document-rebuild` |
| Batch processing | Not started — v2 |

## Code standards

- 400-line hard cap per file
- No AI writing tells in comments or docs
- Table of contents with line ranges on files over 100 lines
- No speculative comments in code

## Adding a new WCAG criterion

1. Add the criterion to `prompts/audit_system.md` in the WCAG ruleset section
2. Define `sub_criterion` and `check_type` entries following the existing pattern
3. Add the criterion to the classification rules section (auto-fix vs. human-review vs. not-applicable, per input type)
4. Add a row to the WCAG criteria table in `ada-pdf-tool/README.md`

## Adding a new file type

1. Add an `extract_<filetype>()` function to `core/extractor.py` following the pattern of `extract_pdf()` and `extract_docx()`
2. Add routing in `app.py` Stage 1 to detect the file type and call the new extractor
3. Add a corresponding remediation path in `core/remediator.py` or `core/dispatch.py`
4. Add the file type to the input types table in `ada-pdf-tool/README.md`
