"""
Image extraction helpers for PDF-to-docx reconstruction.

Uses pymupdf (fitz) to extract embedded images by xref and to render
cropped page regions as PNG bytes. Both functions fail silently (return
empty values) so the caller can fall back to placeholder text.
"""

from __future__ import annotations


def _extract_page_images(pdf_path: str, page_number: int) -> dict[tuple, bytes]:
    """
    Extract all embedded images on a PDF page as raw bytes.

    Uses ``page.get_images(full=True)`` to enumerate xrefs and
    ``doc.extract_image(xref)`` to get the raw image bytes. The bbox for
    each image is obtained from ``page.get_image_rects(xref)``.

    Parameters
    ----------
    pdf_path : str
        Path to the source PDF.
    page_number : int
        0-indexed page number.

    Returns
    -------
    dict[tuple, bytes]
        Keys are ``(x0, y0, x1, y1)`` bbox tuples; values are raw image
        bytes (JPEG, PNG, etc. as stored in the PDF). Returns ``{}`` on any
        error, including a missing pymupdf install.
    """
    try:
        import fitz
    except ImportError:
        return {}

    result: dict[tuple, bytes] = {}
    try:
        doc = fitz.open(pdf_path)
        page = doc[page_number]
        for img_info in page.get_images(full=True):
            xref = img_info[0]
            try:
                rects = page.get_image_rects(xref)
            except Exception:
                rects = []
            img_data = doc.extract_image(xref)
            if img_data and img_data.get("image") and rects:
                for rect in rects:
                    bbox = (rect.x0, rect.y0, rect.x1, rect.y1)
                    result[bbox] = img_data["image"]
        doc.close()
    except Exception:
        pass

    return result


def _crop_region_as_image(
    pdf_path: str,
    page_number: int,
    bbox: list,
    dpi: int = 150,
) -> bytes:
    """
    Render a clipped region of a PDF page as PNG bytes.

    Uses ``page.get_pixmap(clip=fitz.Rect(*bbox), dpi=dpi)``.

    Parameters
    ----------
    pdf_path : str
        Path to the source PDF.
    page_number : int
        0-indexed page number.
    bbox : list
        ``[x0, y0, x1, y1]`` region to clip and render.
    dpi : int
        Render resolution. Default 150; use 200 for formulae.

    Returns
    -------
    bytes
        PNG image bytes, or ``b""`` on any error.
    """
    try:
        import fitz
    except ImportError:
        return b""

    try:
        doc = fitz.open(pdf_path)
        page = doc[page_number]
        pix = page.get_pixmap(clip=fitz.Rect(*bbox), dpi=dpi)
        png_bytes: bytes = pix.tobytes("png")
        doc.close()
        return png_bytes
    except Exception:
        return b""
