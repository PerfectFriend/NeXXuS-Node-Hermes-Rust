# HOT
#!/usr/bin/env python3
"""
CyberTarot — Simple 4x Upscaler (Lanczos + Unsharp Mask)
Fast, reliable, no VRAM issues. 512×768 → 2048×3072
"""

import sys
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

UPSCALE_FACTOR = 4
SHARPEN_RADIUS = 1.5
SHARPEN_PERCENT = 150
SHARPEN_THRESHOLD = 3


def upscale_image(input_path: Path, output_path: Path) -> bool:
    """Upscale single image 4x with Lanczos + unsharp mask."""
    if output_path.exists():
        print(f"  ✓ {input_path.name} already upscaled, skipping")
        return True

    try:
        print(f"  → Upscaling {input_path.name}...")

        with Image.open(input_path) as img:
            # Convert to RGB if needed
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")

            # 1. 4x Lanczos upscale
            w, h = img.size
            new_w, new_h = w * UPSCALE_FACTOR, h * UPSCALE_FACTOR
            img = img.resize((new_w, new_h), Image.LANCZOS)

            # 2. Unsharp mask for crispness
            img = img.filter(ImageFilter.UnsharpMask(
                radius=SHARPEN_RADIUS,
                percent=SHARPEN_PERCENT,
                threshold=SHARPEN_THRESHOLD
            ))

            # 3. Slight contrast boost
            img = ImageEnhance.Contrast(img).enhance(1.05)

            # Save
            output_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(output_path, "PNG", optimize=True, compress_level=6)

            size_kb = output_path.stat().st_size // 1024
            print(f"    ✓ Saved: {output_path.name} ({size_kb}KB, {new_w}×{new_h})")
            return True

    except (OSError, Image.DecompressionBombError, Image.UnidentifiedImageError) as e:
        print(f"    ✗ Error: {e}")
        return False


def main():
    import argparse
    p = argparse.ArgumentParser(description="CyberTarot 4x Upscaler (Python)")
    p.add_argument("--input", required=True, help="Input directory")
    p.add_argument("--output", required=True, help="Output directory")
    p.add_argument("--only", help="Only upscale this filename")
    args = p.parse_args()

    in_dir = Path(args.input)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.only:
        images = [in_dir / args.only]
        if not images[0].exists():
            print(f"✗ {args.only} not found")
            sys.exit(1)
    else:
        images = sorted(in_dir.glob("*.png"))

    print(f"\n=== 4x Upscaler (Python): {len(images)} images ===")

    success = 0
    for img_path in images:
        out_path = out_dir / img_path.name
        if upscale_image(img_path, out_path):
            success += 1

    print(f"\n=== Done: {success}/{len(images)} upscaled ===")
    print(f"Output: {out_dir}")


if __name__ == "__main__":
    main()