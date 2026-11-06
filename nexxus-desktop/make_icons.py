#!/usr/bin/env python3
"""Генерация иконок NeXXus Node Monitor: красная N в синем семиугольнике.

Заливка через L-маску (ImageDraw.polygon в этой сборке PIL заливает
инвертированно — рисуем маску отдельно и paste по ней).
"""
from PIL import Image, ImageDraw, ImageFont
import math
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
BLUE = (25, 118, 210, 255)
BLUE_DARK = (13, 71, 161, 255)
RED = (229, 57, 53, 255)


def make(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    cx = cy = size / 2
    R = size * 0.47
    pts = [(cx + R * math.sin(2 * math.pi * i / 7 - math.pi / 2),
            cy - R * math.cos(2 * math.pi * i / 7 - math.pi / 2)) for i in range(7)]

    # Маска семиугольника
    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    md.polygon(pts, fill=255)
    if sum(mask.getdata()) == 0:  # инверсная сборка PIL — компенсируем
        mask = Image.eval(mask, lambda v: 255 - v)
    img.paste(BLUE, mask=mask)

    # Обводка
    d = ImageDraw.Draw(img)
    d.line(pts + [pts[0]], fill=BLUE_DARK, width=max(2, size // 32),
           joint="curve")

    # Красная N
    font = ImageFont.truetype(FONT, int(size * 0.62))
    bbox = d.textbbox((0, 0), "N", font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text((cx - w / 2 - bbox[0], cy - h / 2 - bbox[1]), "N",
           font=font, fill=RED)
    return img


for s in (512, 256, 128, 64, 48, 32, 16):
    make(s).save(f"src-tauri/icons/icon-{s}.png")
make(128).save("src-tauri/icons/tray-icon.png")
make(256).save("src-tauri/icons/icon.png")

# Bundle-иконки (tauri.conf.json -> bundle.icon = "icons/icon-*.png").
# Раньше тут лежал стоковый шаблон с градиентом — теперь та же иконка N/семиугольник.
os.makedirs("icons", exist_ok=True)
for s in (512, 256, 128, 64, 48, 32, 16):
    make(s).save(f"icons/icon-{s}.png")
make(256).save("icons/icon.png")


def svg_path() -> str:
    cx = cy = 256.0
    R = 256 * 0.47
    pts = " ".join(
        f"{cx + R * math.sin(2 * math.pi * i / 7 - math.pi / 2):.2f},"
        f"{cy - R * math.cos(2 * math.pi * i / 7 - math.pi / 2):.2f}"
        for i in range(7)
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" '
        'viewBox="0 0 512 512">\n'
        f'  <polygon points="{pts}" fill="#1976d2" stroke="#0d47a1" '
        'stroke-width="14" stroke-linejoin="round"/>\n'
        '  <text x="256" y="256" font-family="DejaVu Sans, sans-serif" '
        'font-size="300" font-weight="bold" fill="#e53935" '
        'text-anchor="middle" dominant-baseline="central">N</text>\n'
        '</svg>\n'
    )


with open("icons/icon.svg", "w") as f:
    f.write(svg_path())

# Самопроверка: внутри синий, снаружи прозрачно, центр — красный
t = Image.open("src-tauri/icons/tray-icon.png")
inside = t.getpixel((30, 64))
outside = t.getpixel((5, 5))
center = t.getpixel((64, 64))
assert inside[:3] == (25, 118, 210), f"inside={inside}"
assert outside[3] == 0, f"outside={outside}"
assert center[:3] == (229, 57, 53), f"center={center}"
print("icons OK: heptagon blue fill, red N, transparent outside")
