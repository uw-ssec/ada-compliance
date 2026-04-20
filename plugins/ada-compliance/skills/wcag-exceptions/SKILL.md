---
name: wcag-exceptions
description: Reference for the exceptions to ADA Title II / WCAG 2.1 AA compliance — archived content, preexisting documents, preexisting social media posts, password-protected personal documents, and third-party content. Use when the user asks "is X exempt", "do we have to make the old archive compliant", "what about legacy PDFs", "is third-party content exempt", or generally about the compliance exceptions. Grounded in the UW eScience ADA Title II compliance notes.
---

# Exceptions to ADA Title II / WCAG 2.1 AA Compliance

The ADA Title II rule includes several narrow exceptions. This skill explains each one and how to judge whether it applies. Grounded in the `wcag-title-ii-notes` skill.

## The universal caveat

> In all cases, we are still required to provide any noncompliant content in an accessible format if anyone requests it.

No exception removes this obligation. An exception means you do not have to proactively make every piece of content compliant — but if someone asks for an accessible version, you must produce one.

## General burden exception

There is a general exception when compliance would be "unduly burdensome". From the notes: this is likely very narrow and may require a lawyer or court to interpret. **Do not rely on this without legal advice.**

## 1. Archived Content Exception

Content qualifies only if it meets **all four** of these criteria:

1. Created **before** the compliance deadline (April 24, 2026).
2. Exists only in areas of the website **labeled as explicitly archival**.
3. Used only for **reference, research, or recordkeeping** — cannot be required for a course or for using the site.
4. **Has not been changed** since it was archived.

All four must be true. If a course syllabus points to an archived file as required reading, criterion 3 fails. If someone made a small edit to fix a typo, criterion 4 fails.

**Applying it:** move old content into an `/archive/` area on the site, label that area clearly as archival, never link to archived content from active course pages, and never edit archived files.

## 2. Preexisting Documents Exception

A document is exempt if **both**:

1. It is a **word processing, presentation, PDF, or spreadsheet file**, AND
2. It was available on the state or local government's website or app **before** the compliance date.

**Scope:** `.docx`, `.pdf`, `.pptx`, `.xlsx`, and equivalent formats from Google Workspace — only these four categories.

**Critical limit:** "If a document is currently in use, this exception does not apply." A 2024 syllabus still being used in an active 2026 class is not covered. The exception is for dormant historical documents.

## 3. Preexisting Social Media Post Exception

Social media posts made **before April 24, 2026** are typically exempt. New posts from that date onward must be compliant.

## 4. Password-Protected Personal Document Exception

A document is exempt if **all three**:

1. It is a word processing, presentation, PDF, or spreadsheet file, AND
2. It is about a **specific person, property, or account**, AND
3. It is **password-protected** or otherwise secured.

**This does not cover internal intranet documents.** It is for public-facing personal records (e.g., a student grade report behind a login that is specific to that student).

## 5. Third-Party Content Exception

This is the most confusing exception. From the compliance notes:

> It applies to third-party content posted on our websites, not material that we link on third-party websites like GitHub or Google Docs. For example, if we allowed comments on a page, the comments posted by users are partially exempt; however, the page itself must conform with the exception of the posts, and a notice of partial conformance must be provided [WCAG 5.4].

Two important consequences:

- **User-generated content on our site (e.g., blog comments) is partially exempt.** The surrounding page must still conform, and we must provide a notice of partial conformance.
- **Content we link on third-party sites is NOT exempt.** If we link to a GitHub repo, a Google Doc, or a YouTube video, we are responsible for ensuring the linked content conforms. From the notes: "if we link to an external website such as GitHub, we are required to ensure that the linked content conforms as well, regardless of whether we can control the content."

GitHub mostly conforms to WCAG 2.1 AA already. YouTube depends on the individual video.

## Decision flow

When evaluating whether a piece of content is exempt, walk through these questions:

1. **Is it audio/video, a conventional document, a social media post, or a web page?** The exceptions apply differently to each.
2. **When was it created or last modified?** Before April 24, 2026?
3. **Is it currently in use?** If yes, the preexisting-documents exception is unavailable.
4. **Is it in a labeled archive area?** Required for the archived-content exception.
5. **Is it used for reference only?** Required for the archived-content exception.
6. **Is it a personal record behind a password?** Only then does the password-protected exception apply.
7. **Is it user-generated content we're hosting, or content we're linking?** Only the former has partial exemption.

If any required condition fails, the exception does not apply.

## Important reminders

- **"Currently in use" kills the preexisting-documents exception.** This is the most common pitfall.
- **Internal-only is not the same as password-protected.** An intranet document is not covered by the password-protected exception.
- **Linking is not third-party content.** If we link to it, we are responsible for it.
- **Accessible versions must always be provided on request** — no exception removes this.
- **Consult a lawyer** for edge cases, and **consult UW policy** (uwconnect.uw.edu KB0036639) for UW-specific guidance.

## Partial conformance notice [WCAG 5.4]

When third-party user content on your page is exempt, you must post a notice that the page is partially conforming. A short statement like "User-submitted comments below may not meet accessibility standards" placed near the content is the standard approach.
