"""
Thumbnail diagnostic — run with: pixi run python debug_thumb.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import fitz

pdf_path = "/Users/ishikajohari/dev/ada-compliance/samples/IV-A 2024.pdf"

print(f"[THUMB] pymupdf version: {fitz.version}", flush=True)
print(f"[THUMB] opening: {pdf_path}", flush=True)

doc = fitz.open(pdf_path)
print(f"[THUMB] page count: {doc.page_count}", flush=True)

from core.extractor import extract

print("[THUMB] extracting...", flush=True)
extraction = extract(pdf_path)

picture_els = [
    (p["page_number"], el)
    for p in extraction["pages"]
    for el in p["elements"]
    if el.get("docling_label") == "picture"
]
print(f"[THUMB] found {len(picture_els)} picture element(s)", flush=True)

if not picture_els:
    print("[THUMB] no pictures found — cannot test thumbnail", flush=True)
    sys.exit(0)

page_num, el = picture_els[0]
bbox = el.get("bbox")
print(f"[THUMB] first picture: page={page_num}  bbox={bbox}", flush=True)



# replace the clip creation in debug_thumb.py with this:
page = doc[page_num - 1]
page_height = page.rect.height
x0, y_bottom, x1, y_top = bbox
pymupdf_y0 = page_height - y_bottom
pymupdf_y1 = page_height - y_top
clip = fitz.Rect(x0, pymupdf_y0, x1, pymupdf_y1)
print(f"[THUMB] converted clip: {clip}", flush=True)
print(f"[THUMB] clip.is_empty: {clip.is_empty}", flush=True)
pix = page.get_pixmap(dpi=144, clip=clip)
print(f"[THUMB] pixmap size: {pix.width}x{pix.height}", flush=True)
png_bytes = pix.tobytes("png")
print(f"[THUMB] png bytes: {len(png_bytes)}", flush=True)

from PIL import Image
import io
img = Image.open(io.BytesIO(png_bytes))
print(f"[THUMB] PIL image size: {img.size}", flush=True)
img.thumbnail((400, 400))
print(f"[THUMB] after thumbnail(): {img.size}", flush=True)

out = io.BytesIO()
img.save(out, format="PNG")
print(f"[THUMB] final PNG bytes: {len(out.getvalue())}", flush=True)
print("[THUMB] SUCCESS", flush=True)

doc.close()
