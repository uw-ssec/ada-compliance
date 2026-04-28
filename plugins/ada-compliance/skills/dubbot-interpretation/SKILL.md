---
name: dubbot-interpretation
description: Map DubBot and AudioEye scan output to WCAG 2.1 AA rule citations and to the appropriate in-plugin reviewer agent. Use when starting remediation from a DubBot or AudioEye report.
---

**Contents:** [DubBot Checks L8-L35] · [AudioEye Checks L37-L50] · [Tool Limitations L52-L65] · [Triage Workflow L67-L77] · [Worked Example L79-L83]

## DubBot Checks

| DubBot Check | WCAG Rule(s) | Severity | Agent |
| --- | --- | --- | --- |
| Missing alt text on image | 1.1.1 | Critical | compliance-reviewer |
| Empty alt text on non-decorative image | 1.1.1 | Critical | compliance-reviewer |
| Missing form label | 1.3.5, 2.5.3, 3.3.2 | Critical | compliance-reviewer |
| Placeholder used as only label | 1.3.5, 3.3.2 | Major | compliance-reviewer |
| Missing page title | 2.4.2 | Critical | compliance-reviewer |
| Heading hierarchy skip (h1 to h3) | 1.3.1, 2.4.6 | Major | compliance-reviewer |
| Multiple h1 on page | 1.3.1, 2.4.2 | Major | compliance-reviewer |
| Color contrast below 4.5:1 | 1.4.3 | Major | visual-design-reviewer |
| Link text non-descriptive ("click here") | 2.4.4 | Major | compliance-reviewer |
| Icon-only link without aria-label | 2.4.4 | Critical | compliance-reviewer |
| Unvisited/visited link colors insufficient contrast | 1.4.3 | Major | visual-design-reviewer |
| Missing language attribute on html | 3.1.1 | Minor | compliance-reviewer |
| Focus outline removed (outline:none) | 2.4.7 | Critical | visual-design-reviewer |
| Non-interactive element has onclick | 2.1.1 | Critical | compliance-reviewer |
| Video without captions | 1.2.2, 1.2.4 | Critical | av-compliance-reviewer |
| Audio without transcript | 1.2.1 | Critical | av-compliance-reviewer |
| Automated captions (not human-checked) | 1.2.2 | Major | av-compliance-reviewer |
| Missing audio description on prerecorded video | 1.2.5 | Critical | av-compliance-reviewer |
| Bypass block (skip link) missing | 2.4.1 | Major | compliance-reviewer |
| List created with manual bullets | 1.3.2 | Major | compliance-reviewer |
| Image of text without real text alternative | 1.4.5 | Major | visual-design-reviewer |
| Input without type attribute | 1.3.5 | Major | compliance-reviewer |
| Button or link with empty text | 2.4.4 | Critical | compliance-reviewer |

## AudioEye Checks

| AudioEye Check | WCAG Rule(s) | Severity | Agent |
| --- | --- | --- | --- |
| Missing image alt text | 1.1.1 | Critical | compliance-reviewer |
| Form input missing label association | 1.3.5, 2.5.3 | Critical | compliance-reviewer |
| Page missing title | 2.4.2 | Critical | compliance-reviewer |
| Insufficient color contrast | 1.4.3 | Major | visual-design-reviewer |
| Heading structure invalid | 1.3.1 | Major | compliance-reviewer |
| Keyboard trap detected | 2.1.2 | Critical | compliance-reviewer |
| Required field indicator missing | 3.3.2 | Major | compliance-reviewer |
| Meta language attribute absent | 3.1.1 | Minor | compliance-reviewer |
| Video missing captions | 1.2.2, 1.2.4 | Critical | av-compliance-reviewer |
| Focus indicator not visible | 2.4.7 | Critical | visual-design-reviewer |

## Tool Limitations

| What | Follow-up |
| --- | --- |
| Caption accuracy and human review | human-caption-review via av-compliance-reviewer |
| Audio description quality | human review via av-compliance-reviewer |
| Keyboard trap with assistive technology | manual test with NVDA or VoiceOver via compliance-reviewer |
| Cognitive accessibility (plain language, structure) | human review via compliance-reviewer |
| Reading order in PDF documents | document-tool via document-reviewer |
| Focus order correctness in complex widgets | rendered-page testing via axe or Lighthouse |
| Color-only information in scientific plots | human review via visual-design-reviewer |
| Preexisting documents exception eligibility | human-review via exceptions-analyst |

## Triage Workflow

1. Export from DubBot as CSV (preferred) or PDF.
2. Group rows by WCAG rule using the DubBot/AudioEye tables above.
3. Deduplicate: same rule + same file = one finding; same rule + different files = separate rows.
4. Sort by severity: Critical → Major → Minor.
5. Route each finding to the agent in the Agent column.
6. Items flagged but requiring human verification (contrast ratios, caption accuracy, focus order) become "Needs human verification" rows in the final report.

## Worked Example

| File | DubBot Check | WCAG Rule | Severity | Agent |
| --- | --- | --- | --- | --- |
| src/pages/index.html | Missing alt text on image | 1.1.1 | Critical | compliance-reviewer |
| src/pages/index.html | Color contrast below 4.5:1 | 1.4.3 | Major | visual-design-reviewer |
| src/components/Form.tsx | Form input missing label | 1.3.5, 3.3.2 | Critical | compliance-reviewer |
| src/videos/intro.mp4 | Video missing captions | 1.2.2 | Critical | av-compliance-reviewer |
