---
name: wcag-document-requirements
description: Reference for WCAG 2.1 AA requirements as applied to non-HTML documents — Google Docs, Word, PowerPoint, Google Slides, PDFs, spreadsheets, and source code blocks. Use when the user asks about making a Google Doc accessible, document heading styles, PDF compliance, slide decks, spreadsheets, alt text in documents, or "are Google Docs covered by ADA Title II". Grounded in the UW eScience ADA Title II compliance notes.
---

# WCAG 2.1 AA Document Requirements

Documents linked from public web pages are covered by ADA Title II. Internal documents (Google Docs, Word files on intranet) are covered by Title I — an existing requirement, just less new. This skill applies to both. Grounded in the `wcag-title-ii-notes` skill.

## Core principle: use built-in styles

The most important rule for documents: **use the built-in heading and list styles rather than manually formatting normal text.**

In Google Docs and Word:

- Title of the document: `Title` style (not bold 24pt normal text).
- Section headings: `Heading 1`, `Heading 2`, `Heading 3`, etc.
- Lists: the bullet/numbered list buttons, not "- " typed manually.
- Emphasis: bold/italic is fine, but it must not replace semantic structure.

This single change does most of the work for [WCAG 1.3.1] (info and relationships programmatically determinable) and [WCAG 2.4.6] (headings and labels).

## Why it matters

Screen readers navigate documents by heading. A blind user can jump directly to "Methods" if it is an `Heading 2`, but they cannot if it is just bold text. A document with no real headings becomes a single undifferentiated wall of text to assistive tech.

## Alt text in documents

- **Google Docs:** right-click an image → "Alt text" → add a description.
- **Word:** right-click an image → "Edit Alt Text".
- **Google Slides / PowerPoint:** same as Docs / Word.
- **Decorative images:** mark as decorative (Word) or use empty alt (Docs).

## Spreadsheets

- Use **header rows** and mark them via the built-in header feature.
- Name sheets meaningfully ("Grades" not "Sheet1").
- Avoid merging cells — merged cells confuse screen readers.
- Don't convey meaning with color alone (red for "overdue"). Add a text column.

## Slide decks (Google Slides / PowerPoint)

- Every slide needs a unique **slide title** (the title placeholder), even if visually hidden.
- Use the built-in **outline / layout** features — screen readers use these.
- Set a **reading order** explicitly in PowerPoint (Arrange → Selection Pane).
- Alt text on every non-decorative image.
- Avoid text inside images when real text would work.
- Ensure sufficient contrast.

## PDFs

PDFs are the hardest case. From the compliance notes:

> PDF documents are complicated and will require work for compliance. It's likely that a PDF rendered from a compliant Google document will be compliant, but I do not know how to test this, and I am not comfortable enough with the PDF format to make any claims about how to make them compliant.

Practical guidance:

- **Prefer HTML to PDF whenever possible.** HTML is easier to make accessible.
- If you must use PDF, author the source in Google Docs or Word with proper styles, then export. Do not scan paper documents into PDFs — scanned PDFs are image-only and fail [WCAG 1.1.1].
- Tagged PDFs (structure tree embedded) are required for assistive tech. Google Docs and modern Word exports produce tagged PDFs by default.
- **Compliance is required for PDFs.** The preexisting-documents exception may cover older PDFs (see the `wcag-exceptions` skill).
- Verification tools: Adobe Acrobat Pro's accessibility checker, PAC (PDF Accessibility Checker).

## Source code

From the compliance notes:

> Source code can be rendered on a webpage using a code block with the language tagged. My understanding is that this use of source code is considered compliant.

Practical guidance:

- Use fenced code blocks with language tags (```` ```python ````) in markdown and HTML.
- Code inside a proper `<pre><code class="language-...">` block is considered accessible content.
- Code snippets as screenshots are **not** compliant ([WCAG 1.4.5] images of text).

## Downloadable files

From the notes: files that cannot be rendered in a browser and can only be downloaded and viewed in an external tool are probably not required to be compliant under WCAG 2.1 (which covers web content). **But**: "conventional documents" — word processing files, spreadsheets, slides — are considered web content even when downloaded. So a `.docx`, `.xlsx`, or `.pptx` behind a download link still has to be compliant.

## Checklist for a document under review

1. Does it use real heading/title styles throughout?
2. Do all meaningful images have alt text?
3. Are lists made with list styles, not manual bullets?
4. Do spreadsheet tables use real headers?
5. Do slides have titles and a reading order set?
6. If PDF: is it tagged? Was it exported from a compliant source, not scanned?
7. Is the document currently in use (preexisting exception does not apply) or is it a true legacy file?
8. Does color alone carry any meaning? Fix if so.
9. Contrast on any colored text sufficient?

## Exceptions

Documents have several applicable exceptions — archived content, preexisting documents, password-protected personal documents. See the `wcag-exceptions` skill. Note that "currently in use" removes the preexisting-documents exception, and an accessible version must always be provided on request.
