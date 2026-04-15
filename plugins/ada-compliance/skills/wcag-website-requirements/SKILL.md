---
name: wcag-website-requirements
description: Reference for WCAG 2.1 Level AA website requirements under ADA Title II. Use when the user asks about alt text, heading structure, link text, keyboard navigation, focus indicators, color contrast, color-only information, form labels, page titles, bypass blocks, language attributes, or generally "what does WCAG require for websites". Grounded in the UW eScience ADA Title II compliance notes.
---

# WCAG 2.1 AA Website Requirements

Apply these rules when reviewing or authoring web content (HTML, markdown, MDX, JSX/TSX, notebooks). Every rule cites a WCAG section from the UW eScience compliance notes at `plugins/ada-compliance/references/ada-title-ii-notes.md`.

## Text alternatives [WCAG 1.1.1]

Every non-text element must have a text alternative.

- `<img>` requires `alt`. Use `alt=""` **only** for purely decorative images.
- Icons and SVGs need `aria-label`, `aria-labelledby`, or `<title>` inside the SVG.
- Animations and complex media need ARIA attributes that describe purpose.

## Structure and semantics

Use real HTML semantics — assistive tech relies on them.

- **Headings [1.3.1, 2.4.6]:** use `<h1>`–`<h6>` in hierarchical order. Never simulate a heading with bold/large `<p>`. The same applies to Google Docs / Word documents: use "Title", "Heading 1", "Heading 2" styles, not bold normal text.
- **Lists [1.3.2]:** use `<ul>`/`<ol>`. Don't convey structure through whitespace.
- **Meaningful sequence [1.3.2]:** the DOM order must match the visual reading order.
- **Page title [2.4.2]:** every page needs a `<title>` that describes its content.
- **Orientation [1.3.4]:** don't lock content to portrait or landscape.
- **Language [3.1.1, 3.1.2]:** `<html lang="en">` is required. Parts of the page in other languages need `lang` attributes too.

## Links and navigation

- **Link purpose [2.4.4]:** the link's purpose must be clear from its text alone or its immediate programmatic context. Reject "click here", "read more", "here", bare URLs.
- **Consistent navigation [3.2.3]:** nav bars and menus must appear in the same place and order across pages.
- **Consistent identification [3.2.4]:** components with the same function must be labeled the same way everywhere.
- **Multiple ways [2.4.5]:** non-process pages must be findable more than one way (sitemap, navigation menu, search).
- **Bypass blocks [2.4.1]:** provide a "skip to main content" link (usually hidden until the tab key is pressed) to skip repeated content.

## Keyboard and focus

- **Keyboard operable [2.1.1]:** all functionality must work with a keyboard alone.
- **No keyboard trap [2.1.2]:** users must be able to tab into and out of every region.
- **Focus order [2.4.3]:** tab order must be logical.
- **Focus visible [2.4.7]:** never remove focus outlines without replacing them. `outline: none` by itself is a violation.

## Color and contrast

- **Use of color [1.4.1]:** never rely on color alone to convey information. Pair color with text, icons, or patterns. This applies to scientific plots as well.
- **Sensory characteristics [1.3.3]:** don't rely on shape, size, or sound to convey instructions.
- **Contrast minimum [1.4.3]:** text contrast must be at least 4.5:1. Verify with a rendering tool — source code alone cannot tell you the exact ratio, but combinations like light gray on white should be flagged.
- **Resize text [1.4.4]:** text must scale up to 200% without loss of content.
- **Images of text [1.4.5]:** don't use images of text where real text works. Logos are exempt; other exceptions must be "essential".

## Forms and input

- **Labels [1.3.5, 3.3.2]:** every input needs a programmatic label. Placeholders are not labels. Required fields must indicate that they are required.
- **Label in name [2.5.3]:** a widget's accessible name must include the visible label text.
- **Standard widgets [1.3.5]:** use native HTML elements (`<input type="radio">`, etc.) rather than rolling your own with JavaScript.
- **Error identification and suggestions [3.3.1, 3.3.3]:** form errors must be identified in text and suggestions offered where possible.

## Motion, audio, flashing

- **Audio control [1.4.2]:** if audio auto-plays, users must be able to stop it.
- **Pause, stop, hide [2.2]:** any auto-playing, auto-scrolling, or animated content must have a pause control.
- **Seizures [2.3]:** no flashing content.

## Context changes

- **On focus [3.2.1]:** focus alone must not trigger a context change.
- **On input [3.2.2]:** changing a form value must not trigger a context change unless the user was warned.

## Pointer input

Gestures and pointer-heavy interactions have additional requirements [WCAG 2.5] — keep interactions simple or provide keyboard alternatives.

## Testing tools

Not every rule can be checked programmatically. UW recommends:

- **DubBot** — UW's tool for compliance
- **AudioEye** — commercial scanner
- **axe**, **Lighthouse**, **WAVE** — browser extensions / Lighthouse audits

Use these for rendered-page verification of contrast, focus order, and keyboard traps — things source review cannot catch.

## Exceptions

Some content may qualify for an exception (archived content, preexisting documents, password-protected personal documents, third-party embeds). See the `wcag-exceptions` skill. Even when an exception applies, an accessible version must be provided on request.
