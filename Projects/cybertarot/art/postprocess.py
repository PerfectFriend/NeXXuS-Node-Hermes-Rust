#!/usr/bin/env python3
"""
CyberTarot — Post-process
Adds sacred geometry border, color correction, watermark to final cards.
"""

import sys
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
import argparse

BORDER_COLOR = "#E8B94A"  # Gold
BORDER_WIDTH = 8
WATERMARK_TEXT = "CyberTarot"
WATERMARK_OPACITY = 30
SATURATION_BOOST = 1.15
CONTRAST_BOOST = 1.08


def add_sacred_border(img: Image.Image, border_width: int = BORDER_WIDTH,
                      color: str = BORDER_COLOR) -> Image.Image:
    """Add golden sacred geometry inspired border."""
    w, h = img.size
    new_w, new_h = w + 2 * border_width, h + 2 * border_width
    result = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 0))

    # Fill with border color
    draw = ImageDraw.Draw(result)
    draw.rectangle([0, 0, new_w, new_h], fill=color)

    # Inner dark area
    draw.rectangle(
        [border_width, border_width, new_w - border_width, new_h - border_width],
        fill="#0B0E1A"
    )

    # Sacred geometry corners (simplified - small squares at corners)
    corner_size = border_width * 3
    for cx, cy in [
        (border_width, border_width),
        (new_w - corner_size - border_width, border_width),
        (border_width, new_h - corner_size - border_width),
        (new_w - corner_size - border_width, new_h - corner_size - border_width),
    ]:
        draw.rectangle([cx, cy, cx + corner_size, cy + corner_size],
                       outline=color, width=2)

    # Paste original in center
    result.paste(img, (border_width, border_width))
    return result


def enhance_colors(img: Image.Image, saturation: float = SATURATION_BOOST,
                   contrast: float = CONTRAST_BOOST) -> Image.Image:
    """Boost saturation and contrast for cyberpunk look."""
    img = ImageEnhance.Color(img).enhance(saturation)
    img = ImageEnhance.Contrast(img).enhance(contrast)
    return img


def add_watermark(img: Image.Image, text: str = WATERMARK_TEXT,
                  opacity: int = WATERMARK_OPACITY) -> Image.Image:
    """Add subtle watermark in bottom right."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    w, h = img.size
    watermark = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(watermark)

    # Try to use a nice font
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except:
        font = ImageFont.load_default()

    # Position bottom-right with margin
    margin = 20
    # Use textbbox instead of deprecated textsize
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = w - text_w - margin
    y = h - text_h - margin

    # Draw with gold color at low opacity
    gold = (232, 185, 74, opacity)
    draw.text((x, y), text, font=font, fill=gold)

    return Image.alpha_composite(img, watermark)


def process_image(input_path: Path, output_path: Path) -> bool:
    """Process single image through full pipeline."""
    try:
        with Image.open(input_path) as img:
            # Convert to RGBA
            if img.mode != "RGBA":
                img = img.convert("RGBA")

            # 1. Color enhancement
            img = enhance_colors(img)

            # 2. Sacred border
            img = add_sacred_border(img)

            # 3. Watermark
            img = add_watermark(img)

            # Save
            output_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(output_path, "PNG", optimize=True)
            return True
    except Exception as e:
        print(f"  ✗ Error processing {input_path.name}: {e}")
        return False


def main():
    p = argparse.ArgumentParser(description="CyberTarot Post-process")
    p.add_argument("--input", required=True, help="Input directory")
    p.add_argument("--output", required=True, help="Output directory")
    args = p.parse_args()

    in_dir = Path(args.input)
    out_dir = Path(args.output)

    if not in_dir.exists():
        print(f"✗ Input dir not found: {in_dir}")
        sys.exit(1)

    images = sorted(in_dir.glob("*.png"))
    if not images:
        print(f"✗ No PNG files in {in_dir}")
        sys.exit(1)

    print(f"\n=== Post-process: {len(images)} images ===")

    success = 0
    for img_path in images:
        out_path = out_dir / img_path.name
        if process_image(img_path, out_path):
            size = out_path.stat().st_size
            print(f"  ✓ {img_path.name} → {size // 1024}KB")
            success += 1
        else:
            print(f"  ✗ {img_path.name} failed")

    print(f"\n=== Done: {success}/{len(images)} processed ===")
    print(f"Output: {out_dir}")


if __name__ == "__main__":
    main()