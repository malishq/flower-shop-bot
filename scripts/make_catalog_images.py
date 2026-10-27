from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "data" / "catalog.json"
OUT_DIR = ROOT / "assets" / "catalog"
WIDTH, HEIGHT = 800, 600

TITLE_FONTS = [
    ("/System/Library/Fonts/Supplemental/Georgia Bold.ttf", 0),
    ("/Library/Fonts/Georgia Bold.ttf", 0),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", 0),
]
TEXT_FONTS = [
    ("/System/Library/Fonts/HelveticaNeue.ttc", 1),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 0),
    ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 0),
]
LABEL_FONTS = [
    ("/System/Library/Fonts/HelveticaNeue.ttc", 10),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 0),
    ("/System/Library/Fonts/Supplemental/Arial.ttf", 0),
]

PALETTES = {
    "bouquets": {"bg": "#F7E4E8", "blob1": "#F0C4CF", "blob2": "#DE9AAC", "text": "#4B1E2B", "accent": "#C45C78", "label": "#9B5064"},
    "boxes": {"bg": "#F8EBDC", "blob1": "#F0D3B7", "blob2": "#DFAE85", "text": "#4A2B16", "accent": "#C2703E", "label": "#9A6440"},
    "plants": {"bg": "#E4EEE3", "blob1": "#C8DDC6", "blob2": "#9FC3A0", "text": "#1F3A27", "accent": "#4D8159", "label": "#4F6E56"},
    "extras": {"bg": "#E9E5F4", "blob1": "#D3CCEA", "blob2": "#B3A7DA", "text": "#2D2452", "accent": "#6E5BA8", "label": "#625792"},
    "cover": {"bg": "#F2E8E3", "blob1": "#E6D2CA", "blob2": "#CFAFA6", "text": "#4A2F33", "accent": "#8B5A6C", "label": "#7E5F66"},
}


def load_font(paths, size):
    for path, index in paths:
        if Path(path).exists():
            return ImageFont.truetype(path, size, index=index)
    return ImageFont.load_default()


def money(value):
    return f"{value:,}".replace(",", " ") + " ₽"


def wrap(text, font, max_width, draw):
    words = text.split()
    lines, current = [], ""
    for word in words:
        candidate = (current + " " + word).strip()
        if draw.textlength(candidate, font=font) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def fit_title(draw, text, max_width, max_lines, start_size, min_size):
    size = start_size
    while size >= min_size:
        font = load_font(TITLE_FONTS, size)
        lines = wrap(text, font, max_width, draw)
        if len(lines) <= max_lines and all(draw.textlength(line, font=font) <= max_width for line in lines):
            return font, lines
        size -= 4
    font = load_font(TITLE_FONTS, min_size)
    return font, wrap(text, font, max_width, draw)[:max_lines]


def draw_blobs(base, palette):
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    b1 = Image.new("RGB", (1, 1), palette["blob1"]).getpixel((0, 0))
    b2 = Image.new("RGB", (1, 1), palette["blob2"]).getpixel((0, 0))
    draw.ellipse((470, -220, 980, 290), fill=b1 + (255,))
    draw.ellipse((600, 60, 940, 400), fill=b2 + (150,))
    draw.ellipse((-180, 380, 260, 820), fill=b1 + (255,))
    draw.ellipse((40, 470, 300, 730), fill=b2 + (120,))
    return Image.alpha_composite(base, layer)


def spaced(draw, xy, text, font, fill, spacing):
    x, y = xy
    for char in text:
        draw.text((x, y), char, font=font, fill=fill)
        x += draw.textlength(char, font=font) + spacing


def render_card(title, price, category_title, palette, out_path, subtitle=None):
    base = Image.new("RGBA", (WIDTH, HEIGHT), palette["bg"])
    image = draw_blobs(base, palette)
    draw = ImageDraw.Draw(image)

    label_font = load_font(LABEL_FONTS, 22)
    spaced(draw, (56, 52), category_title.upper(), label_font, palette["label"], 3)

    title_font, lines = fit_title(draw, title, 640, 3, 64, 40)
    line_height = int(title_font.size * 1.15)
    block_height = line_height * len(lines)
    y = 300 - block_height // 2 - 10
    for line in lines:
        draw.text((56, y), line, font=title_font, fill=palette["text"])
        y += line_height

    if subtitle:
        sub_font = load_font(LABEL_FONTS, 28)
        draw.text((56, y + 12), subtitle, font=sub_font, fill=palette["label"])

    if price is not None:
        price_font = load_font(TEXT_FONTS, 38)
        text = money(price)
        tw = draw.textlength(text, font=price_font)
        pad_x, pad_y = 30, 16
        x0, y0 = 56, HEIGHT - 56 - 38 - pad_y * 2
        x1, y1 = x0 + tw + pad_x * 2, HEIGHT - 56
        draw.rounded_rectangle((x0, y0, x1, y1), radius=(y1 - y0) // 2, fill=palette["accent"])
        draw.text((x0 + pad_x, y0 + pad_y - 4), text, font=price_font, fill="#FFFFFF")

    brand_font = load_font(TITLE_FONTS, 30)
    brand = "Flora"
    bw = draw.textlength(brand, font=brand_font)
    draw.text((WIDTH - 56 - bw, HEIGHT - 56 - 34), brand, font=brand_font, fill=palette["text"])

    image.convert("RGB").save(out_path, "PNG", optimize=True)


def main():
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    categories = {c["slug"]: c["title"] for c in data["categories"]}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    render_card("Каталог", None, "Цветочная лавка", PALETTES["cover"], OUT_DIR / "cover.png", subtitle="Выберите категорию")
    for product in data["products"]:
        palette = PALETTES[product["category"]]
        out = OUT_DIR / f"{product['slug']}.png"
        render_card(product["title"], product["price"], categories[product["category"]], palette, out)
        print(out.relative_to(ROOT))


if __name__ == "__main__":
    sys.exit(main())
