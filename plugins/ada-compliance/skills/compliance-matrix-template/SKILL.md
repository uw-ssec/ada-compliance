---
name: compliance-matrix-template
description: Canonical output format for ADA Title II compliance audits. Defines the compliance matrix (file x WCAG rule x status), severity taxonomy, and emission formats. Use when generating audit reports.
---

**Contents:** [Severity Taxonomy L8-L13] · [Matrix Columns L15-L27] · [Verification-Path Vocabulary L29-L38] · [Emission Formats L40-L82] · [CAV Tracking L84-L95]

## Severity Taxonomy

- **Critical** — violation that blocks access entirely for a disabled user (e.g., image with no alt, prerecorded video with no captions).
- **Major** — significant barrier that degrades the experience but does not fully block access (e.g., low contrast, non-descriptive link text).
- **Minor** — deviation from WCAG with low accessibility impact (e.g., redundant alt text, inconsistent nav label).
- **Needs human verification** — cannot be confirmed from source alone; requires rendered-page inspection, assistive-tech testing, caption review, or human judgment.

## Matrix Columns

| Column | Type | Description |
| --- | --- | --- |
| `file` | string | Relative path to the reviewed file. |
| `line` | int\|null | Line number of the finding; null if not line-determinable. |
| `wcag_rule` | string | WCAG criterion, e.g. `1.1.1` or `2.4.4`. |
| `description` | string | One-sentence description of the violation or item requiring verification. |
| `severity` | enum | One of: Critical, Major, Minor, Needs human verification. |
| `exception_applies` | bool | Whether a Title II exception applies to this item. |
| `exception_type` | string\|null | One of: archived, preexisting-doc, social-media, password-protected, third-party — or null. |
| `verification_path` | enum | How the finding must be verified. See Verification-Path Vocabulary. |
| `fix_reference` | string\|null | Skill name, URL, or file path pointing to a suggested fix. |

## Verification-Path Vocabulary

| Value | When to use |
| --- | --- |
| `rendered-page` | Must be checked in a browser — contrast ratios, focus order, visible focus indicator. |
| `assistive-tech` | Must be tested with a screen reader (NVDA, VoiceOver) or other assistive technology. |
| `automated-tool` | Can be caught by axe, Lighthouse, DubBot, or WAVE. |
| `document-tool` | Requires Adobe Acrobat Accessibility Checker, PAC, or the Google Docs / Word accessibility checker. |
| `human-caption-review` | A human must watch the video and verify captions are accurate and human-checked, not auto-generated; required for all prerecorded video [WCAG 1.2.2]. |
| `human-review` | Requires human judgment to determine compliance (e.g., whether a document is "currently in use" for the preexisting-documents exception). |

## Emission Formats

### Markdown Report

```markdown
# ADA/WCAG Compliance Report — <scope>

**Date:** <ISO date>
**Reviewer:** compliance-lead
**Source:** wcag-title-ii-notes skill

## Critical

| File | Line | Rule | Description | Fix |
| --- | --- | --- | --- | --- |
| path/to/file | 42 | 1.1.1 | `<img>` missing alt | Add descriptive alt attribute |

## Major
...

## Minor
...

## Needs Human Verification
...

## Exception Summary
<items where a Title II exception may apply — note that accessible versions must still be provided on request>

## Compliance Matrix
<paste CSV block here or attach as separate file>
```

### CSV Schema

Header row:
```
file,line,wcag_rule,description,severity,exception_applies,exception_type,verification_path,fix_reference
```

- Null fields: emit as empty string (not `null` or `N/A`).
- `description`: quote with double quotes if it contains commas.
- One row per finding; multiple rules for the same finding get separate rows.

## CAV Tracking

When a conforming alternate version (CAV) exists for a finding, append these columns to the matrix row:

| Column | Type | Description |
| --- | --- | --- |
| `cav_exists` | bool | Whether a conforming alternate version exists. |
| `cav_url` | string\|null | URL or path to the CAV; null if none. |
| `cav_label` | string\|null | Text used to link to the CAV from the non-conforming page. |

CAVs must meet strict labeling and access requirements — see the `wcag-title-ii-notes` skill, A/V Requirements § Conforming Alternate Versions.
