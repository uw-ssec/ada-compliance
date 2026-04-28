---
name: notebook-accessibility
description: WCAG 2.1 AA guidance specific to Jupyter notebooks (.ipynb). Use when reviewing notebook content for heading hierarchy, figure alt text, interactive output accessibility, DataFrame rendering, inline HTML, execution order, and export contexts.
---

**Contents:** [Heading Hierarchy L8-L16] · [Matplotlib Alt Text L17-L41] · [Plotly and Interactive L42-L58] · [Pandas DataFrames L59-L78] · [Inline HTML L79-L84] · [Execution Order L85-L95] · [Export Contexts L96-L104]

## Heading Hierarchy Across Cells

Notebooks read top-to-bottom. Heading hierarchy must be consistent across Markdown cells — skip from h1 to h3 across cell boundaries is a violation [WCAG 1.3.1]. Bold text in Markdown cells is not a heading.

Before: Cell 1 has `# Title`, Cell 2 has `### Subsection` (skips h2)
After: Cell 1 has `# Title`, Cell 2 has `## Subsection`, Cell 3 has `### Subsection.1`

Use heading styles from the notebook's heading palette or verify cell-by-cell order by reading Markdown source.

## Matplotlib Alt Text

**Export via nbconvert/jupyter-book:**
```python
# Before
fig, ax = plt.subplots()
ax.plot([1, 2, 3], [1, 4, 9])
plt.show()

# After
fig, ax = plt.subplots()
ax.plot([1, 2, 3], [1, 4, 9])
fig.set_label("Line chart: exponential growth from 1 to 9")
plt.show()
```

Verify your nbconvert template renders fig.get_label() as the alt attribute in exported HTML.

**Markdown cell below output:**
```markdown
*Figure 1: Line chart showing exponential growth curve, values 1–9*
```

Place descriptive alt text in the Markdown cell immediately following the figure output cell.

## Plotly and Interactive Outputs

Plotly figures are keyboard-navigable by default [WCAG 2.1.1]. Text alternatives required [WCAG 1.1.1] only when the chart is the sole data source; if a table below it duplicates the data, the table meets the alternative requirement.

```python
import plotly.graph_objects as go

fig = go.Figure(data=[go.Bar(y=[2, 3, 1])])
fig.update_layout(title="Q4 Sales by Region", xaxis_title="Region", yaxis_title="Sales")
fig.show()

# In following Markdown cell:
# Figure: Q4 Sales by Region showing West at 2, Central at 3, East at 1
```

Add a descriptive caption below every interactive figure.

## Pandas DataFrame Rendering

Default HTML table output lacks accessible headers and caption [WCAG 1.3.1]. Use df.style.

**Before:**
```python
df = pd.DataFrame({"Name": ["Alice", "Bob"], "Score": [95, 87]})
df
```

**After:**
```python
df.style.set_caption("Q4 Student Scores").set_table_styles([
    {"selector": "caption", "props": "caption-side: bottom; font-size: 1.1em;"},
    {"selector": "th", "props": "background-color: #000066; color: white;"}
]).set_properties(**{"text-align": "center"})
```

Verify th elements are rendered as scope="col" in exported HTML output.

## Inline HTML in Markdown Cells

Inline HTML in Markdown cells is treated as HTML [WCAG 1.1.1 through 3.3.2]. Apply all standard WCAG HTML rules: alt text on images, ARIA labels on icons, no color-only information, sufficient contrast. Point violations to compliance-reviewer.

Raw HTML bypasses Markdown rendering and can introduce ARIA/structural issues invisible in .md files.

## Execution Order and Reading Flow

Notebooks execute top-to-bottom but output cells can be stale if cells are re-run out of sequence. Screen readers read cell execution numbers (shown in square brackets: `[1]`, `[2]`, etc.). Out-of-order execution numbers create reading-order confusion.

```bash
# Check execution count in notebook JSON:
grep -o '"execution_count": [0-9]*' notebook.ipynb | sort -u
```

If execution counts jump or are non-sequential, flag as reading-order issue. Restart kernel and re-run all cells in order.

## Export Contexts

| Export Method | Rendering Notes | Accessibility |
| --- | --- | --- |
| jupyter-book | Converts to HTML; applies Sphinx theming | fig.set_label() → alt; Markdown captions visible; heading hierarchy critical |
| nbconvert --to html | Embeds cells as HTML divs | Headings and alt text preserved; df.style renders as HTML table |
| Quarto | Renders as HTML/PDF; supports code folding | Captions and alt text supported; test PDF export for structure |
| GitHub renderer | Outputs markdown → HTML in browser | No fig.set_label() alt support; use Markdown captions; tables render as HTML |
