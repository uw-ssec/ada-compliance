---
name: wcag-remediation-patterns
description: Concrete remediation snippets for WCAG 2.1 AA violations, keyed by WCAG rule number. Use when a reviewer agent needs to populate the Fix field in a finding. Reference only — do not modify files.
---

**Contents:** [WCAG 1.1.1 L8-L35] · [WCAG 1.2.2/1.2.4/1.2.5 L37-L43] · [WCAG 1.3.1 L45-L72] · [WCAG 1.4.3 L74-L80] · [WCAG 1.4.5 L82-L90] · [WCAG 2.1.1 L92-L110] · [WCAG 2.4.2 L112-L120] · [WCAG 2.4.4 L122-L138] · [WCAG 2.4.7 L140-L150] · [WCAG 3.1.1 L152-L158] · [WCAG 3.3.2 L160-L173]

## [WCAG 1.1.1] Text Alternatives

**Informative image (HTML):**
```html
<!-- Before -->
<img src="chart.png" />

<!-- After -->
<img src="chart.png" alt="Sales growth increased 25% year-over-year" />
```

**Decorative image (HTML):**
```html
<!-- Before -->
<img src="divider.png" />

<!-- After -->
<img src="divider.png" alt="" role="presentation" />
```

**SVG icon in button (JSX):**
```jsx
<!-- Before -->
<button><svg>...</svg></button>

<!-- After -->
<button aria-label="Close menu"><svg aria-hidden="true">...</svg></button>
```

**Matplotlib figure in Jupyter:**
```python
# Before
fig, ax = plt.subplots()
ax.plot([1, 2, 3])
plt.show()

# After
fig, ax = plt.subplots()
ax.plot([1, 2, 3])
fig.set_label("Line plot showing trend from 1 to 3")
plt.show()
# Then in following Markdown cell: *Figure: Line plot showing trend*
```

## [WCAG 1.2.2, 1.2.4, 1.2.5] Captions and Audio Descriptions

**Cannot be fixed in source:**
- **YouTube:** Upload captions via YouTube Studio → Subtitles & CC (must be human-checked, not auto-generated)
- **Panopto:** Upload transcript via Media Details → Transcript section; add captions to media
- **HTML `<video>`:** Add `<track kind="captions" src="captions.vtt" srclang="en" label="English" />` and provide .vtt file with human-reviewed captions
- **Audio elements:** Provide full text transcript below the player

Defer to `av-compliance-reviewer`.

## [WCAG 1.3.1] Structure and Semantics

**Heading hierarchy skip (HTML):**
```html
<!-- Before -->
<h1>Page Title</h1>
<h3>Section</h3> <!-- skips h2 -->

<!-- After -->
<h1>Page Title</h1>
<h2>Section</h2>
```

**Bold text as heading (Markdown):**
```markdown
<!-- Before -->
**Important Section**

content here

<!-- After -->
## Important Section

content here
```

**Manual bullets instead of list (HTML):**
```html
<!-- Before -->
• Item 1<br/>
• Item 2<br/>

<!-- After -->
<ul>
  <li>Item 1</li>
  <li>Item 2</li>
</ul>
```

**Google Docs / Word:** Use "Title", "Heading 1", "Heading 2" styles — not bold/large text.

## [WCAG 1.4.3] Contrast Ratio

**Cannot compute from source.** Provide actionable Fix:
- Run through **DubBot** (uw.edu/accesstech/dubbot), **axe DevTools**, or **Lighthouse** to measure exact ratios
- Flag suspects: `text-gray-300`, `text-gray-400` on white; light placeholder text
- Threshold: body text 4.5:1, large text 3:1 minimum

## [WCAG 1.4.5] Images of Text

**Screenshot of code (HTML):**
```html
<!-- Before -->
<img src="code-screenshot.png" alt="code" />

<!-- After -->
<pre><code class="language-python">
def hello():
    return "world"
</code></pre>
```

**Table as image (Markdown):**
```markdown
<!-- Before -->
![Table](table-screenshot.png)

<!-- After -->
| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |
```

Logo exemption applies. Other exceptions require "essential" justification.

## [WCAG 2.1.1] Keyboard Accessible

**`<div>` with click handler (HTML):**
```html
<!-- Before -->
<div onClick={handleClick}>Open menu</div>

<!-- After -->
<button onClick={handleClick}>Open menu</button>
```

**Custom widget without keyboard (JSX):**
```jsx
<!-- Before -->
<div role="button" onClick={openMenu}>Menu</div>

<!-- After -->
<button onClick={openMenu} onKeyDown={(e) => {
  if (e.key === 'Enter' || e.key === ' ') openMenu();
}}>Menu</button>
```

Prefer native `<button>` + ARIA over `role="button"` on div.

## [WCAG 2.4.2] Page Titles

**HTML:**
```html
<!-- Before -->
<title>Home</title>

<!-- After -->
<title>Home — My Site</title>
```

**MDX/Markdown:** Verify framework renders the `title` frontmatter field into the `<title>` tag.

## [WCAG 2.4.4] Link Purpose

**Bare or generic text (Markdown):**
```markdown
<!-- Before -->
[click here](https://example.com)
[read more](blog.md)

<!-- After -->
[Learn about our accessibility practices](practices.md)
[View the Q4 report](2024-q4-report.pdf)
```

**Icon-only link (HTML):**
```html
<!-- Before -->
<a href="/settings"><svg>...</svg></a>

<!-- After -->
<a href="/settings" aria-label="Settings"><svg aria-hidden="true">...</svg></a>
```

## [WCAG 2.4.7] Focus Visible

**outline:none without replacement (CSS):**
```css
/* Before */
button:focus {
  outline: none;
}

/* After */
button:focus-visible {
  outline: 2px solid #0066cc;
  outline-offset: 2px;
}
```

**Tailwind (JSX):**
```jsx
<!-- Before -->
<button className="focus:outline-none">Click</button>

<!-- After -->
<button className="focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600">Click</button>
```

## [WCAG 3.1.1] Page Language

**HTML:**
```html
<!-- Before -->
<html>

<!-- After -->
<html lang="en">
```

**MDX/Markdown site config (e.g., MkDocs):**
```yaml
# mkdocs.yml
theme:
  language: en
```

Verify rendered HTML includes `lang` attribute.

## [WCAG 3.3.2] Form Labels

**Input without label (HTML):**
```html
<!-- Before -->
<input type="email" placeholder="Email address" />

<!-- After -->
<label for="email">Email address <span aria-label="required">*</span></label>
<input type="email" id="email" required />
```

**Placeholder as only label (JSX):**
```jsx
<!-- Before -->
<input type="text" placeholder="Name" />

<!-- After -->
<label htmlFor="name">Name <span className="text-red-600" aria-label="required">*</span></label>
<input type="text" id="name" required />
```

Placeholder alone is never sufficient. Visually hidden labels via `sr-only` class are acceptable.
