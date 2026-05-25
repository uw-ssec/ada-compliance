"""
PDF extraction layer using docling.

Extracts structured content (text, images, tables) from programmatic PDFs
and returns a JSON-serialisable dict matching the ExtractionOutput schema.
Scanned PDFs (no embedded text) raise ValueError.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.base_models import InputFormat
from docling.datamodel.document import DoclingDocument
from docling_core.types.doc import DocItemLabel, ImageRefMode


def _make_id(counter: int) -> str:
    return f"el_{counter:03d}"


def _is_bold(font_name: str | None) -> bool | None:
    if font_name is None:
        return None
    lower = font_name.lower()
    return "bold" in lower or "heavy" in lower or lower.endswith("-bd")


def _bbox_to_list(bbox: Any) -> list | None:
    """Convert a docling BoundingBox to [x0, y0, x1, y1] or return None."""
    if bbox is None:
        return None
    try:
        return [bbox.l, bbox.t, bbox.r, bbox.b]
    except AttributeError:
        return None


def extract(pdf_path: str | Path) -> dict:
    """
    Extract structured content from a programmatic PDF.

    Parameters
    ----------
    pdf_path:
        Path to the PDF file.

    Returns
    -------
    dict
        JSON-serialisable dict matching the ExtractionOutput schema.

    Raises
    ------
    FileNotFoundError
        If the PDF does not exist at the given path.
    ValueError
        If the PDF appears to be scanned (no embedded text found).
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = False          # disable OCR — programmatic PDFs only
    pipeline_options.do_table_structure = True
    pipeline_options.generate_picture_images = False

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )

    result = converter.convert(str(pdf_path))
    doc: DoclingDocument = result.document

    # ── scanned-PDF guard ──────────────────────────────────────────────────
    # Collect all text across all pages; if completely empty, treat as scanned.
    all_text = doc.export_to_text().strip()
    if not all_text:
        raise ValueError(
            "This PDF appears to be scanned. Only programmatic PDFs with "
            "embedded text are supported."
        )

    # ── metadata ──────────────────────────────────────────────────────────
    page_count = len(doc.pages) if doc.pages else 0

    title: str | None = None
    language: str | None = None

    # DoclingDocument stores metadata in doc.name and doc.origin;
    # use getattr throughout to be safe across docling versions.
    title = getattr(doc, "name", None) or None
    lang_raw = getattr(doc, "lang", None)
    if lang_raw:
        # lang may be a list or a string depending on docling version
        if isinstance(lang_raw, list):
            language = lang_raw[0] if lang_raw else None
        else:
            language = str(lang_raw)

    metadata = {
        "title": title,
        "language": language,
        "page_count": page_count,
    }

    # ── build a page_number → page_index map ─────────────────────────────
    # doc.pages is a dict keyed by PageNo (1-based int-like objects)
    page_numbers = sorted(doc.pages.keys(), key=lambda p: int(p))

    pages_map: dict[int, list[dict]] = {int(p): [] for p in page_numbers}

    element_counter = 1  # sequential across the whole document

    # ── iterate document items ─────────────────────────────────────────────
    for item, _level in doc.iterate_items():
        label = getattr(item, "label", None)
        if label is None:
            continue

        # Determine page number for this item
        prov = getattr(item, "prov", None)
        page_no: int | None = None
        bbox_list: list | None = None

        if prov:
            first_prov = prov[0] if isinstance(prov, (list, tuple)) and prov else prov
            raw_page = getattr(first_prov, "page_no", None)
            if raw_page is not None:
                page_no = int(raw_page)
            raw_bbox = getattr(first_prov, "bbox", None)
            bbox_list = _bbox_to_list(raw_bbox)

        if page_no is None or page_no not in pages_map:
            # Fall back to page 1 if provenance is missing
            page_no = int(page_numbers[0]) if page_numbers else 1
            if page_no not in pages_map:
                pages_map[page_no] = []

        el_id = _make_id(element_counter)
        element_counter += 1

        # ── TEXT elements ──────────────────────────────────────────────────
        if label in (
            DocItemLabel.TEXT,
            DocItemLabel.PARAGRAPH,
            DocItemLabel.SECTION_HEADER,
            DocItemLabel.TITLE,
            DocItemLabel.CAPTION,
            DocItemLabel.FOOTNOTE,
            DocItemLabel.PAGE_HEADER,
            DocItemLabel.PAGE_FOOTER,
            DocItemLabel.LIST_ITEM,
            DocItemLabel.CODE,
            DocItemLabel.FORMULA,
        ):
            text_content = getattr(item, "text", None)

            # Font metadata (available on TextItem)
            font_size: float | None = None
            font_bold: bool | None = None
            orig = getattr(item, "orig", None)
            if orig:
                style = getattr(orig, "font", None) or getattr(orig, "style", None)
                if style:
                    font_size = getattr(style, "size", None)
                    font_bold = _is_bold(getattr(style, "name", None))

            element: dict = {
                "id": el_id,
                "type": "text",
                "docling_label": label.value,
                "text": text_content,
                "font_size": font_size,
                "font_bold": font_bold,
                "bbox": bbox_list,
                "current_tag": None,
            }
            pages_map[page_no].append(element)

        # ── IMAGE elements ─────────────────────────────────────────────────
        elif label == DocItemLabel.PICTURE:
            element = {
                "id": el_id,
                "type": "image",
                "docling_label": label.value,
                "bbox": bbox_list,
                "has_alt_text": False,  # pikepdf will check real alt text later
            }
            pages_map[page_no].append(element)

        # ── TABLE elements ─────────────────────────────────────────────────
        elif label == DocItemLabel.TABLE:
            rows: int | None = None
            cols: int | None = None

            # docling TableItem exposes .data with num_rows / num_cols
            table_data = getattr(item, "data", None)
            if table_data is not None:
                rows = getattr(table_data, "num_rows", None)
                cols = getattr(table_data, "num_cols", None)

            element = {
                "id": el_id,
                "type": "table",
                "docling_label": label.value,
                "rows": rows,
                "cols": cols,
                "has_header_row": "unknown",  # Claude infers this in the analysis layer
            }
            pages_map[page_no].append(element)

        # All other label types are skipped for now.

    # ── assemble pages list ────────────────────────────────────────────────
    pages = [
        {"page_number": pn, "elements": pages_map[pn]}
        for pn in sorted(pages_map.keys())
    ]

    return {
        "file_type": "pdf",
        "metadata": metadata,
        "pages": pages,
    }


def extract_docx(file_path: str | Path) -> dict:
    """
    Extract structured content from a Word .docx file.

    Returns the same JSON-serialisable dict schema as extract():
      {
        "file_type": "docx",
        "metadata": {"title": ..., "language": ..., "page_count": 1},
        "pages": [{"page_number": 1, "elements": [...]}]
      }
    """
    from docx import Document as DocxDocument

    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    doc = DocxDocument(str(file_path))

    # ── metadata ──────────────────────────────────────────────────────────
    props = doc.core_properties
    title: str | None = props.title or None
    language: str | None = props.language or None

    metadata = {
        "title": title,
        "language": language,
        "page_count": 1,  # docx has no reliable page count without rendering
    }

    _STYLE_MAP = {
        "Heading 1": "title",
        "Heading 2": "section_header",
        "Heading 3": "section_header",
        "Heading 4": "section_header",
        "List Paragraph": "list_item",
        "Caption": "caption",
    }

    elements: list[dict] = []
    counter = 1

    # ── paragraphs ────────────────────────────────────────────────────────
    for para in doc.paragraphs:
        if not para.text.strip():
            continue

        style_name = para.style.name if para.style else "Normal"
        docling_label = _STYLE_MAP.get(style_name, "text")

        font_bold: bool | None = None
        if para.runs:
            font_bold = para.runs[0].bold

        # Check for inline images in this paragraph
        has_image = False
        for run in para.runs:
            xml = run._r.xml
            if "<a:blip" in xml or "drawing" in xml or "pic:" in xml:
                has_image = True
                break

        if has_image:
            # Detect alt text on drawing element
            has_alt = False
            try:
                from lxml import etree
                ns = {"wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"}
                for run in para.runs:
                    for drawing in run._r.findall(".//{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}docPr"):
                        descr = drawing.get("descr", "")
                        if descr and descr.strip():
                            has_alt = True
            except Exception:
                pass

            elements.append({
                "id": f"el_{counter:03d}",
                "type": "image",
                "docling_label": "picture",
                "text": None,
                "page": 1,
                "bbox": None,
                "current_tag": None,
                "has_alt_text": has_alt,
            })
            counter += 1
        else:
            elements.append({
                "id": f"el_{counter:03d}",
                "type": "text",
                "docling_label": docling_label,
                "text": para.text,
                "page": 1,
                "bbox": None,
                "current_tag": style_name,
                "has_alt_text": None,
                "font_size": None,
                "font_bold": font_bold,
            })
            counter += 1

    # ── tables ────────────────────────────────────────────────────────────
    for table in doc.tables:
        has_header = "unknown"
        if table.rows:
            first_cell_style = ""
            try:
                first_cell_style = table.rows[0].cells[0].paragraphs[0].style.name
            except (IndexError, AttributeError):
                pass
            if first_cell_style in ("Table Header", "Heading 1", "Heading 2"):
                has_header = "true"

        elements.append({
            "id": f"el_{counter:03d}",
            "type": "table",
            "docling_label": "table",
            "text": None,
            "page": 1,
            "bbox": None,
            "current_tag": None,
            "rows": len(table.rows),
            "cols": len(table.columns),
            "has_header_row": has_header,
        })
        counter += 1

    return {
        "file_type": "docx",
        "metadata": metadata,
        "pages": [{"page_number": 1, "elements": elements}],
    }


def is_tagged_pdf(pdf_path: str) -> bool:
    """
    Return True if the PDF has an accessibility tag tree (/StructTreeRoot).

    Parameters
    ----------
    pdf_path:
        Path to the PDF file.

    Returns
    -------
    bool — True if tagged, False if untagged or on any error.
    """
    try:
        import pikepdf
        with pikepdf.open(str(pdf_path)) as pdf:
            struct_tree = pdf.Root.get("/StructTreeRoot")
            return struct_tree is not None
    except Exception:
        return False


def extract_to_json(pdf_path: str | Path, output_path: str | Path | None = None) -> str:
    """
    Extract a PDF and return the result as a JSON string.

    Optionally writes the JSON to *output_path* as well.
    """
    result = extract(pdf_path)
    json_str = json.dumps(result, indent=2, default=str)
    if output_path is not None:
        Path(output_path).write_text(json_str, encoding="utf-8")
    return json_str
