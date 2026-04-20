---
name: wcag-title-ii-notes
description: Authoritative ADA Title II / WCAG 2.1 AA interpretation notes authored by Noah C. Benson (UW eScience). Use when agents need to reference ADA Title II compliance requirements, exceptions, or WCAG 2.1 AA rules.
---

# ADA Title II Compliance Notes
Author: Noah C. Benson, February 2026

**The author is not a lawyer**; this is a good-faith attempt to read and understand the WCAG 2.1 level AA requirements. This document was written without the assistance of generative AI.

## Resources

* [The WCAG 2.1 requirements](https://www.w3.org/TR/WCAG21/) (AA are what is required)
* [The ADA Fact Sheet](https://www.ada.gov/resources/2024-03-08-web-rule/)
* UW's policy on minimum digital accessibility standards (uwconnect.uw.edu KB0036639)
* [UW's digital accessibility checklist](https://www.washington.edu/accesstech/checklist/)
* [W3's quick-advice on meeting WCAG 2.1](https://www.w3.org/WAI/WCAG22/quickref/)
* [DubBot](https://www.washington.edu/accesstech/dubbot/) is UW's tool for compliance; [AudioEye](https://www.audioeye.com/) also checks for compliance. Not all requirements can be checked programmatically.

## User Profiles

* Someone who is deaf — needs accurate captions; non-speech audio (like a bird call) must be explained in text.
* Someone blind from birth — needs screen-reader-friendly pages, useful alt-text, and audio descriptions of purely visual video content.
* Someone with severe color vision deficiencies — needs cues other than color alone to convey information, including in scientific plots.
* Someone paralyzed from the neck down — uses assistive tech or a keyboard, needs sites easy to navigate with a few buttons.
* Someone with cognitive disabilities like attention disorder — needs straightforward, well-organized, non-distracting sites.

## Exceptions [L28-L68]

In all cases **we must still provide any noncompliant content in an accessible format if anyone requests it**. There are also general exceptions when compliance is unduly burdensome; this exception is likely narrow and may require a lawyer or court to interpret.

### Archived Content

Exception for archived content [ADA Fact Sheet: Archived Content]. Content must meet **all four** criteria:

1. Created before April 24, 2026.
2. Only exists in areas of the website explicitly labeled as archival.
3. Used only for "reference, research, or recordkeeping" — not required as part of a course or to understand/use the site.
4. Not changed since it was archived.

### Preexisting Documents

A document is exempt if **both**:

1. It is a word processing, presentation, PDF, or spreadsheet file, AND
2. It was available on the state or local government's website/app before April 24, 2026.

**If a document is currently in use, this exception does not apply.** Whether a document is "currently in use" requires human verification — the date alone is not sufficient to determine exemption. We must still provide an accessible version if requested.

### Preexisting Social Media Post

Social media posts made before April 24, 2026 are typically exempt.

### Password-Protected

Exempt if **all three**:

1. Word processing, presentation, PDF, or spreadsheet file, AND
2. About a specific person, property, or account, AND
3. Password-protected or otherwise secured.

**This does not cover internal documents behind a firewall** — only public password-protected documents for specific individuals.

### Third-Party Content

Applies to third-party content posted on our websites (e.g., user comments), not to material we link to on third-party sites. User-posted content is partially exempt, but the page itself must conform and a notice of partial conformance must be provided [WCAG 5.4].

**All embedded content must conform.** If we link to an external website such as GitHub, we are required to ensure that the linked content conforms — regardless of whether we can control it. (GitHub mostly conforms to WCAG 2.1 AA.)

## A/V Requirements [L70-L91]

* These requirements apply even to videos embedded in or linked from the site.
* Audio-only or video-only media must provide an alternative method of obtaining equivalent information [WCAG 1.2.1].
* Video needs captions [WCAG 1.2.2, 1.2.4]. AI/algorithmic captions are acceptable for **live** captioning [WCAG 1.2.4], but prerecorded videos must have human-checked captions [WCAG 1.2.2].
* Non-speech audio (like a sound effect) must be described in the captions.
* Audio descriptions must be provided for all prerecorded video [WCAG 1.2.5].
* AA compliance does not require audio descriptions for live talks [WCAG 1.2.9].
* Audio descriptions of prerecorded video need only fill pauses in existing dialog; if all pauses are filled, adding more is not required [WCAG 2.1 Technique F113].

### Live vs. Prerecorded

| Requirement | Live | Prerecorded |
| --- | --- | --- |
| Captions [WCAG 1.2.2, 1.2.4] | Required; AI/algorithmic acceptable | Required; **must be human-checked** |
| Audio descriptions [WCAG 1.2.5, 1.2.9] | Not required at AA | Required (fill dialog pauses) |
| Alternative for audio/video-only [WCAG 1.2.1] | — | Must provide equivalent text alternative |
| Non-speech audio (sound effects, etc.) | Described in captions | Described in captions |

### Conforming Alternate Versions (CAVs)

"Conforming alternate versions" (CAVs) are allowed — separate conforming content on a conformance page. Strict requirements about labeling and access apply — see [WCAG 2.1 CAV documentation](https://www.w3.org/TR/WCAG21/#dfn-conforming-alternate-versions).

## Website Requirements [L93-L116]

* All non-text content should have a text alternative [WCAG 1.1.1]. Images need alt-text; icons/animations should use [aria attributes](https://www.w3.org/TR/html-aria/).
* Page organization must be programmatically determinable [WCAG 1.3.1]. Use `<h1>` tags, not large bold `<p>`. Don't use whitespace to convey meaning — use lists [WCAG 1.3.2].
* Applies to linked Google Docs and Word documents — use "Title", "Heading 1", "Heading 2" styles instead of bold large text.
* Content shouldn't depend on landscape vs. portrait orientation [WCAG 1.3.4].
* Input widgets (radio buttons, text boxes) should be programmatically understandable and correctly HTML-labeled [WCAG 1.3.5]. Label-in-name [WCAG 2.5.3]. Instructions or a label indicating what is required should be provided [WCAG 3.3.2].
* Pages should have titles that describe their contents [WCAG 2.4.2] and descriptive headings and labels [WCAG 2.4.6].
* Link purpose should be determinable from link text alone or its programmatically determinable context [WCAG 2.4.4].
* Navigation elements consistent across pages [WCAG 3.2.3]. Similar components identified consistently [WCAG 3.2.4].
* Information required to operate or navigate must not rely on sensory information alone (color, sound) [WCAG 1.3.3]. No information conveyed using color alone [WCAG 1.4.1].
* If audio auto-plays, you must be able to stop it [WCAG 1.4.2].
* Contrast ratio must be at least 4.5:1 [WCAG 1.4.3].
* Text must be resizable up to 200% without loss of content [WCAG 1.4.4].
* Don't use images of text [WCAG 1.4.5]. Logos excluded; other exclusions must be "essential".
* Must be able to use a keyboard to navigate all content [WCAG 2.1.1], in an orderly way [WCAG 2.4.3], no keyboard trap [WCAG 2.1.2], visible keyboard focus [WCAG 2.4.7].
* A bypass block must exist for content repeated across multiple pages (e.g., nav bars) [WCAG 2.4.1]. These usually appear as a "skip to main content" link when the user presses tab.
* Must be able to pause auto-playing/scrolling content [WCAG 2.2].
* Don't use content that flashes [WCAG 2.3].
* Non-process web pages must be findable in more than one way [WCAG 2.4.5] (sitemap, navigation menu, search).
* Creative pointer input (gestures, zooming) has additional requirements [WCAG 2.5].
* Page language and part-language must be programmatically determinable [WCAG 3.1.1, 3.1.2] — typically via metadata.
* Don't programmatically change context [WCAG 3.2.1, 3.2.2].
* Forms that generate errors have additional requirements [WCAG 3.3.1, 3.3.3].

## Document Requirements [L118-L126]

* Internal Google/Word documents, slides, and spreadsheets must be compliant. (Required by ADA Title I, not Title II — and not new. Any document an external user can find in their browser is covered by Title II.)
* Use built-in styles rather than bold/large normal text.
* Images in documents should have alt text.
* Rules that apply to websites also apply to documents.
* PDFs are complicated. A PDF rendered from a compliant Google doc is likely compliant, but this is hard to test. PDFs are required to be compliant.
* Source code rendered on a webpage via a language-tagged code block is considered compliant.
* Files that cannot be rendered in a browser and must be downloaded and viewed externally are likely not required to be compliant (WCAG 2.1 covers web content). But "conventional documents" — word processing files, spreadsheets, slides — are considered web content even when downloaded.
