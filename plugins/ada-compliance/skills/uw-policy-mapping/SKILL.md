---
name: uw-policy-mapping
description: Map WCAG 2.1 AA rules to UW digital accessibility policy language (KB0036639, UW accesstech checklist). Use when writing remediation tickets that need to cite UW policy alongside WCAG.
---

**Contents:** [Institutional Context L8-L10] · [WCAG-to-UW Mapping L12-L51] · [Remediation Ticket Template L53-L73] · [Resources L75-L80]

## Institutional Context

ADA Title II applies to state and local government web content; WCAG 2.1 Level AA is the adopted compliance standard. UW KB0036639 operationalizes this standard as UW minimum digital accessibility requirements. Remediation tickets should cite all three.

## WCAG Rule → UW Policy Mapping

| WCAG Rule | UW KB0036639 Language | UW Accesstech Checklist |
| --- | --- | --- |
| 1.1.1 | Non-text content must have text alternatives | Images: "Do images have alt text?" |
| 1.2.1 | Prerecorded audio/video-only needs text alternative | Transcripts: "Written versions of recorded audio" |
| 1.2.2 | Prerecorded video must have captions | Captions: "Does recorded video have captions?" |
| 1.2.4 | Live video must have captions | Live captions: "Real-time captioning available" |
| 1.2.5 | Prerecorded video must have audio description | Audio description: "Visual content narration when needed" |
| 1.3.1 | Page structure must be programmatically determinable | Headings: "Do headings form an outline?" |
| 1.3.2 | Meaningful sequence must be determinable | Lists: "Are lists used to identify content?" |
| 1.3.3 | Instructions must not rely on sensory characteristics alone | Visual characteristics: "Avoid color as sole communication" |
| 1.3.4 | Content must not restrict orientation | See KB0036639 |
| 1.3.5 | Input purposes must be programmatically determinable | Forms: "Coded labels, prompts, error messages" |
| 1.4.1 | Color must not convey information alone | Visual characteristics: "Avoid color as sole communication" |
| 1.4.2 | Auto-playing audio must be stoppable | See KB0036639 |
| 1.4.3 | Text contrast must be at least 4.5:1 | Contrast: "Sufficient contrast between text and background?" |
| 1.4.4 | Text must be resizable to 200% | Enlarged text: "Proper scaling support" |
| 1.4.5 | Real text instead of images of text | See KB0036639 |
| 2.1.1 | All functionality must be keyboard operable | Keyboard: "All controls operable without a mouse" |
| 2.1.2 | Keyboard focus must not trap | See KB0036639 |
| 2.4.1 | Bypass blocks must exist for repeated content | Navigation: "Content bypass mechanisms available" |
| 2.4.2 | Pages must have descriptive titles | Titles: "Does page have title describing topic?" |
| 2.4.3 | Focus order must be logical | Tab and read order: "Logical navigation sequence" |
| 2.4.4 | Link purpose must be determinable from text | Links: "Ensure proper use and meaningful labels" |
| 2.4.5 | Multiple ways to locate content must exist | Finding content: "Consistent navigation, multiple ways" |
| 2.4.6 | Headings and labels must describe topic/purpose | Headings and Links items |
| 2.4.7 | Keyboard focus indicator must be visible | See KB0036639 |
| 2.5.3 | Accessible name must match visible label | Forms: "Coded labels" |
| 3.1.1 | Page language must be programmatically determinable | Language: "Has language of page been defined?" |
| 3.1.2 | Language changes must be programmatically determinable | See KB0036639 |
| 3.2.1 | Focus alone must not cause context change | Predictability: "No unexpected context changes" |
| 3.2.2 | Input alone must not cause context change | See KB0036639 |
| 3.2.3 | Navigation must be consistent across pages | Navigation: "Consistent identification" |
| 3.2.4 | Components must be identified consistently | Navigation consistency |
| 3.3.1 | Errors must be identified in text | Forms: "Accessible error messages" |
| 3.3.2 | Labels or instructions must be provided for input | Forms: "Coded labels, prompts" |
| 3.3.3 | Error suggestions must be provided | Forms: "Accessible error messages" |
| 4.1.1 | Valid parsing required | Code validation: "Valid HTML coding" |
| 4.1.2 | Name, role, value must be programmatically determinable | ARIA: "Proper markup for dynamic interfaces" |

## UW Remediation Ticket Template

```
Title: [WCAG X.Y.Z] Brief description of violation

Description: What was found and where (file, line, URL if known).

WCAG Citation: [WCAG X.Y.Z] — Rule name and requirement

UW Policy Citation: KB0036639 — UW minimum digital accessibility standards

ADA Citation: ADA Title II, 28 CFR Part 35

Severity: Critical | Major | Minor

Estimated Effort: X hours or X days

Assignee Hints: Frontend | QA | Content author | Accessibility specialist

Verification Path: rendered-page | assistive-tech | automated-tool | document-tool | human-review
```

## Resources

- UW digital accessibility checklist: https://www.washington.edu/accesstech/checklist/
- UW IT accessibility KB: uwconnect.uw.edu KB0036639
- WCAG 2.1: https://www.w3.org/TR/WCAG21/
- ADA Title II web rule fact sheet: https://www.ada.gov/resources/2024-03-08-web-rule/
