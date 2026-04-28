---
name: ada-check
description: Run a scoped single-file accessibility review. Routes to the correct specialist based on file extension.
argument-hint: <path>
---

Review the file at the path provided. Route to the correct specialist based on extension:
- .html, .md, .mdx, .jsx, .tsx → web-content-reviewer (structural/semantic) and visual-design-reviewer (color/contrast/focus)
- .ipynb → web-content-reviewer with notebook-accessibility skill loaded
- .pdf, .docx, .doc, .pptx, .ppt, .xlsx, .xls → document-reviewer
- Files containing <video>, <audio>, YouTube/Vimeo/Panopto URLs → av-compliance-reviewer
- .css, .scss → visual-design-reviewer only

If the file extension is ambiguous or unlisted, use web-content-reviewer and note the limitation.
