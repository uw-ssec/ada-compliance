---
name: wcag-av-requirements
description: Reference for WCAG 2.1 AA audio/video requirements under ADA Title II. Use when the user asks about captions, audio descriptions, video accessibility, live vs prerecorded video rules, sound effects in captions, audio-only or video-only content, embedded YouTube/Vimeo/Panopto videos, or "how do I make a video ADA compliant". Grounded in the UW eScience ADA Title II compliance notes.
---

# WCAG 2.1 AA Audio/Video Requirements

Apply these rules when reviewing or authoring content that embeds, links, or references audio or video media. The most important distinction is **live vs. prerecorded**. Grounded in the `wcag-title-ii-notes` skill.

## Key principle: embedded and linked both count

From the compliance notes: **these requirements apply even to videos embedded in the site or linked from the site.** A YouTube link is no different from a `<video>` tag for compliance purposes.

## The live vs. prerecorded table

| Requirement | Live | Prerecorded |
| --- | --- | --- |
| Captions [1.2.2, 1.2.4] | Required — AI/algorithmic OK | Required — **must be human-checked** |
| Audio description [1.2.5, 1.2.9] | Not required at AA | Required |
| Text alternative for audio-only or video-only [1.2.1] | — | Required |
| Non-speech audio described in captions | Yes | Yes |

**AI captions are acceptable for live video, not for prerecorded.** This is the single most common mistake — uploading a Zoom recording with auto-generated captions is not compliant. A human must review them.

## Captions [WCAG 1.2.2, 1.2.4]

- All video content requires captions.
- Non-speech audio must be described: `[bird call]`, `[door slams]`, `[applause]`.
- For prerecorded videos, captions must be human-reviewed even if they started as auto-generated.
- Captions in a `<track kind="captions" srclang="en">` element are the standard HTML approach. For embedded YouTube/Vimeo, verify captions exist inside the source platform.

## Audio descriptions [WCAG 1.2.5]

Audio descriptions are spoken narration of visually important content that is not conveyed through dialog. Required for **prerecorded video**.

- For recorded talks: visual information (slides, graphs, demonstrations) must be described out loud. If the speaker already describes them in dialog, that counts.
- The practical rule from the notes: **fill existing pauses in dialog with description of relevant visuals**. If every pause is already filled, adding more is not required [WCAG 2.1 Technique F113].
- Audio descriptions can be added via dubbing after the fact.
- **Live talks do not require audio descriptions** at AA level [WCAG 1.2.9].

## Audio-only and video-only content [WCAG 1.2.1]

- **Audio-only** (podcasts, recorded interviews): provide an equivalent text transcript.
- **Video-only** (silent demos, animated diagrams): provide an equivalent text description or audio description.

## Sound effects and non-speech audio

Sound that carries meaning — a bird call played in a lecture, a warning chime, applause — must be described in the captions. This is part of [WCAG 1.2.2], not a separate rule.

## Conforming alternate versions (CAVs)

If you cannot make the primary version compliant, you may provide a separate conforming version and link to it prominently. This is allowed by WCAG 2.1 but has strict labeling and access requirements. See [the WCAG 2.1 CAV documentation](https://www.w3.org/TR/WCAG21/#dfn-conforming-alternate-versions). In practice: it is usually simpler to fix the original than to maintain a CAV.

## Applicable exceptions

Some A/V content may qualify for an exception (see the `wcag-exceptions` skill):

- **Archived content** — if all four archive criteria are met.
- **Preexisting social media posts** — posts before the compliance date (April 24, 2026) are typically exempt.

**Even when exempt, an accessible version must be provided on request.**

## Review checklist

When reviewing A/V content, answer:

1. Is it live or prerecorded? (Recorded lectures = prerecorded.)
2. Does it have captions? Are they human-reviewed (for prerecorded)?
3. Does it have audio descriptions, or does the dialog already cover the visuals? (Prerecorded only.)
4. Are non-speech sounds that carry meaning described in captions?
5. For audio-only or video-only: is there a text alternative?
6. Does any exception clearly apply?

## What cannot be checked from source code

- Whether captions are accurate or human-reviewed.
- Whether audio descriptions are present inside the video.
- Whether the video platform exposes captions to the embedded player.

These require a human to watch the video or ask the content owner. The `av-compliance-reviewer` agent will flag these explicitly rather than give a false pass.
