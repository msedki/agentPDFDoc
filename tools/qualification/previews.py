"""Small local visual previews of controlled fixtures; no OCR or benchmark."""
from __future__ import annotations

import json
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]


def main():
    manifest = json.loads((ROOT / "evals/qualification-v2.1/manifest.json").read_text(encoding="utf-8"))
    entries = {entry["key"]: entry for entry in manifest["entries"]}
    selected = [("development-DA-P03", 1), ("development-DA-P04", 0), ("crop-rotate-90", 0), ("unicode-selection", 0), ("scan-fr-en", 0), ("boundary-45", 4)]
    output = ROOT / "evals/qualification-v2.1/reports/previews"
    output.mkdir(parents=True, exist_ok=True)
    sheet = Image.new("RGB", (1200, 2600), "#d8dee3")
    draw = ImageDraw.Draw(sheet)
    for index, (key, page_index) in enumerate(selected):
        doc = pdfium.PdfDocument(str(ROOT / "fixtures" / entries[key]["path"]))
        page = doc[page_index]
        bitmap = page.render(scale=0.9)
        try:
            image = bitmap.to_pil().convert("RGB").copy()
            image.save(output / f"{key}-p{page_index+1}.png")
            x, y = (index % 2) * 600 + 20, (index // 2) * 860 + 50
            sheet.paste(image, (x, y))
            draw.text((x, y - 30), f"{key} / physical page {page_index+1}", fill="#20272b", font=ImageFont.load_default(size=16))
            image.close()
        finally:
            bitmap.close(); page.close(); doc.close()
    sheet.save(output / "contact-sheet.png")
    sheet.close()
    print(output / "contact-sheet.png")


if __name__ == "__main__":
    main()
