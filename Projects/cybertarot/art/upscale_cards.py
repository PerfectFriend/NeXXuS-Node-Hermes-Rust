#!/usr/bin/env python3
"""
CyberTarot — ESRGAN Upscaler
Upscales card art 4x via ComfyUI's built-in upscaler nodes.
512×768 → 2048×3072

Usage:
  python upscale_cards.py --input cards/ --output cards_hd/
  python upscale_cards.py --only 00_fool.png
"""

import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

COMFY_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8189")

# Upscale models available in ComfyUI-Shared/models/upscale_models/
# Common: RealESRGAN_x4plus.pth, 4x_NMKD-Siax.pth
UPSCALE_MODEL = "RealESRGAN_x4plus.pth"


def upscale_image(image_path: Path, output_dir: Path, model: str = UPSCALE_MODEL) -> bool:
    """Upscale a single image 4x via ComfyUI."""
    output_file = output_dir / image_path.name
    if output_file.exists():
        print(f"  ✓ {image_path.name} already upscaled, skipping")
        return True

    # Upload image
    import mimetypes
    boundary = "----UpscaleBoundary123"
    mime = mimetypes.guess_type(str(image_path))[0] or "image/png"
    with open(image_path, "rb") as f:
        image_data = f.read()

    parts = [
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="image"; filename="{image_path.name}"\r\n'.encode(),
        f"Content-Type: {mime}\r\n\r\n".encode(),
        image_data,
        f"\r\n--{boundary}--\r\n".encode(),
    ]
    body = b"".join(parts)

    req = urllib.request.Request(
        f"{COMFY_URL}/upload/image",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        upload_result = json.loads(resp.read())

    ref_filename = upload_result["name"]
    print(f"  → Upscaling {image_path.name}...")
    print(f"    Uploaded: {ref_filename}")

    # Build upscale-only workflow (no checkpoint needed, just upscaler)
    workflow = {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": ref_filename},
        },
        "2": {
            "class_type": "UpscaleModelLoader",
            "inputs": {"model_name": model},
        },
        "3": {
            "class_type": "ImageUpscaleWithModel",
            "inputs": {"upscale_model": ["2", 0], "image": ["1", 0]},
        },
        # Optional: keep original size if upscaler overshoots
        "4": {
            "class_type": "ImageScale",
            "inputs": {
                "image": ["3", 0],
                "upscale_method": "lanczos",
                "width": 2048,
                "height": 3072,
                "crop": "center",
            },
        },
        "5": {
            "class_type": "SaveImage",
            "inputs": {"images": ["4", 0], "filename_prefix": "cybertarot_hd"},
        },
    }

    payload = json.dumps({"prompt": workflow}).encode()
    req = urllib.request.Request(
        f"{COMFY_URL}/api/prompt",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        print(f"    ✗ Submit failed: {e}")
        return False

    prompt_id = result.get("prompt_id")
    if not prompt_id:
        print(f"    ✗ No prompt_id: {result}")
        return False

    print(f"    Submitted: {prompt_id}")
    print("    Upscaling (may take 1-3 min)...")

    # Poll
    deadline = time.time() + 600
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{COMFY_URL}/history/{prompt_id}", timeout=10) as r:
                hist = json.loads(r.read())
            if prompt_id in hist:
                outputs = hist[prompt_id].get("outputs", {})
                for nout in outputs.values():
                    if "images" in nout:
                        for img in nout["images"]:
                            url = f"{COMFY_URL}/view?filename={img['filename']}&subfolder={img.get('subfolder','')}&type=output"
                            with urllib.request.urlopen(url, timeout=30) as r2:
                                output_file.write_bytes(r2.read())
                            size = output_file.stat().st_size
                            print(f"    ✓ Saved: {output_file} ({size // 1024}KB)")
                            return True
                print("    ✗ No image in outputs")
                return False
        except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
            # Log for debugging but continue polling
            logger = logging.getLogger(__name__)
            logger.debug(f"Poll error: {e}")
        time.sleep(3)

    print("    ✗ Timeout")
    return False


def main():
    import argparse
    p = argparse.ArgumentParser(description="CyberTarot ESRGAN Upscaler")
    p.add_argument("--input", required=True, help="Input dir with PNG cards")
    p.add_argument("--output", required=True, help="Output dir for HD cards")
    p.add_argument("--only", help="Only upscale this filename")
    p.add_argument("--model", default=UPSCALE_MODEL, help="Upscale model name")
    args = p.parse_args()

    in_dir = Path(args.input)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Check server
    try:
        with urllib.request.urlopen(f"{COMFY_URL}/system_stats", timeout=5) as r:
            stats = json.loads(r.read())
        dev = stats.get("devices", [{}])[0]
        print(f"ComfyUI: {stats['system']['comfyui_version']}")
        print(f"GPU: {dev['name']} | VRAM free: {dev.get('vram_free', 0) // (1024**3):.1f}GB")
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
            print(f"✗ ComfyUI not reachable: {e}")
            sys.exit(1)

    # Find images
    if args.only:
        images = [in_dir / args.only]
        if not images[0].exists():
            print(f"✗ {args.only} not found in {in_dir}")
            sys.exit(1)
    else:
        images = sorted(in_dir.glob("*.png"))

    print(f"\n=== Upscaler: {len(images)} images → {args.model} ===")

    success = 0
    failed = 0
    for img in images:
        if upscale_image(img, out_dir, args.model):
            success += 1
        else:
            failed += 1
        # Free VRAM between images to avoid OOM
        time.sleep(2)

    print(f"\n=== Done: {success} upscaled, {failed} failed ===")
    print(f"Output: {out_dir}")


if __name__ == "__main__":
    main()
