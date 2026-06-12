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

## Branching and commits

Active branches:

| Branch | Purpose |
|---|---|
| `main` | Stable |
| `feat/ada-pdf-streamlit` | Streamlit tool base |
| `feat/ada-docx-support` | docx support and fixes |
| `feat/faithful-document-rebuild` | PDF rebuild fidelity improvements (current active branch) |

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
