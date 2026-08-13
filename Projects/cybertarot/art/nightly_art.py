#!/usr/bin/env python3
"""
CyberTarot — Nightly Art Factory
Extracts style from reference images in a folder, generates high-quality
tarot card art at max resolution, saves to art/cards/.

Runs via cron at scheduled time. Uses img2img style transfer via ComfyUI.

Usage:
  python nightly_art.py                          # full run
  python nightly_art.py --references "C:/Users/tomas/Downloads"  # custom ref folder
  python nightly_art.py --model sdxl            # SDXL 1024×1536
  python nightly_art.py --denoise 0.65          # style strength (0=copy ref, 1=ignore)
  python nightly_art.py --dry-run               # print plan without generating
"""

import json
import sys
import os
import time
import random
import urllib.request
import urllib.error
from pathlib import Path

# --- Config ---
COMFY_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8189")
SCRIPT_DIR = Path(__file__).parent
PROMPTS_FILE = SCRIPT_DIR / "prompts.json"
OUTPUT_DIR = SCRIPT_DIR / "cards"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
REFERENCES_DIR = Path(os.environ.get(
    "CYBERTAROT_REFERENCES",
    "C:/Users/tomas/Downloads"
))

# Supported image extensions
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

# Master style prompt
STYLE_PREFIX = (
    "breathtaking digital painting, masterpiece, "
    "Van Gogh swirling impasto brushstrokes, Gaudi organic trencadis mosaic architecture, "
    "sacred geometry, ornate golden border, vertical tarot card composition, "
)
STYLE_SUFFIX = (
    ", ultra detailed, dramatic cinematic lighting, oil painting texture, "
    "vivid saturated colors, dark atmospheric background, trending on ArtStation, 8K"
)
NEGATIVE_PROMPT = (
    "low quality, blurry, deformed, ugly, text, watermark, bad anatomy, "
    "extra limbs, jpeg artifacts, cropped, flat colors, cartoon, anime, 3d render"
)

MODELS = {
    "sd15": "v1-5-pruned-emaonly.safetensors",
    "sdxl": "sd_xl_base_1.0.safetensors",
}


def find_references(ref_dir: Path) -> list[Path]:
    """Find all image files in reference folder."""
    if not ref_dir.exists():
        return []
    refs = [f for f in ref_dir.iterdir()
            if f.suffix.lower() in IMAGE_EXTS and f.stat().st_size > 10000]
    return sorted(refs)


def build_prompt(card_data: dict) -> str:
    return (
        f"{STYLE_PREFIX}"
        f'"{card_data["name"]}", {card_data["concept"]}, '
        f"color palette: {card_data['colors']}, "
        f"mood: {card_data['mood']}"
        f"{STYLE_SUFFIX}"
    )


def upload_image(image_path: Path) -> dict:
    """Upload an image to ComfyUI's input folder."""
    import mimetypes
    boundary = "----CyberTarotBoundary123"
    mime = mimetypes.guess_type(str(image_path))[0] or "image/png"

    with open(image_path, "rb") as f:
        image_data = f.read()

    # Build multipart body: properly formatted with name field
    parts = []
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(f'Content-Disposition: form-data; name="image"; filename="{image_path.name}"\r\n'.encode())
    parts.append(f"Content-Type: {mime}\r\n\r\n".encode())
    parts.append(image_data)
    parts.append(f"\r\n--{boundary}--\r\n".encode())

    body = b"".join(parts)

    req = urllib.request.Request(
        f"{COMFY_URL}/upload/image",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def submit_img2img(prompt_text: str, negative: str, model: str,
                   ref_filename: str, denoise: float = 0.65,
                   seed: int = -1) -> dict:
    """Submit img2img workflow using reference image for style."""
    if seed == -1:
        seed = random.randint(0, 2**32 - 1)

    is_sdxl = "xl" in model.lower()
    w, h = (1024, 1536) if is_sdxl else (512, 768)
    steps = 30 if is_sdxl else 25
    cfg = 7.5

    workflow = {
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": model},
        },
        "5": {
            "class_type": "LoadImage",
            "inputs": {"image": ref_filename},
        },
        "6": {
            "class_type": "ImageScale",
            "inputs": {
                "image": ["5", 0],
                "upscale_method": "lanczos",
                "width": w,
                "height": h,
                "crop": "center",
            },
        },
        "7": {
            "class_type": "VAEEncode",
            "inputs": {"pixels": ["6", 0], "vae": ["4", 2]},
        },
        "8": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt_text, "clip": ["4", 1]},
        },
        "9": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative, "clip": ["4", 1]},
        },
        "10": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "euler_ancestral",
                "scheduler": "normal",
                "denoise": denoise,
                "model": ["4", 0],
                "positive": ["8", 0],
                "negative": ["9", 0],
                "latent_image": ["7", 0],
            },
        },
        "11": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["10", 0], "vae": ["4", 2]},
        },
        "12": {
            "class_type": "SaveImage",
            "inputs": {"images": ["11", 0], "filename_prefix": "cybertarot_style"},
        },
    }

    payload = json.dumps({"prompt": workflow}).encode("utf-8")
    req = urllib.request.Request(
        f"{COMFY_URL}/api/prompt",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def poll_result(prompt_id: str, timeout: int = 600) -> dict | None:
    """Poll /history/{prompt_id} until done."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{COMFY_URL}/history/{prompt_id}", timeout=10) as r:
                data = json.loads(r.read())
            if prompt_id in data:
                return data[prompt_id]
        except Exception:
            pass
        time.sleep(3)
    return None


def download_image(filename: str, subfolder: str, output_path: Path):
    """Download generated image from ComfyUI."""
    url = f"{COMFY_URL}/view?filename={filename}&subfolder={subfolder}&type=output"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        output_path.write_bytes(resp.read())


def generate_card_with_style(
    card_id: str,
    card_data: dict,
    model_key: str,
    reference_path: Path,
    denoise: float,
) -> bool:
    """Generate one card using a reference image for style."""
    model_file = MODELS[model_key]
    prompt_text = build_prompt(card_data)
    output_file = OUTPUT_DIR / f"{card_id}.png"

    if output_file.exists():
        print(f"  ✓ {card_id} already exists, skipping")
        return True

    print(f"  → Generating {card_id} ({card_data['name']})...")
    print(f"    Reference: {reference_path.name}")
    print(f"    Model: {model_file} | Denoise: {denoise}")

    try:
        # Upload reference image
        upload_result = upload_image(reference_path)
        ref_filename = upload_result["name"]
        print(f"    Uploaded ref: {ref_filename}")

        # Submit img2img
        result = submit_img2img(
            prompt_text, NEGATIVE_PROMPT, model_file,
            ref_filename, denoise
        )
        prompt_id = result.get("prompt_id")
        if not prompt_id:
            print(f"    ✗ No prompt_id: {result}")
            return False

        print(f"    Submitted: {prompt_id}")
        print(f"    Generating (this may take 2-10 min)...")

        history = poll_result(prompt_id, timeout=900)
        if not history:
            print(f"    ✗ Timeout for {card_id}")
            return False

        # Extract output
        for node_id, node_output in history.get("outputs", {}).items():
            if "images" in node_output:
                for img in node_output["images"]:
                    download_image(
                        img["filename"],
                        img.get("subfolder", ""),
                        output_file
                    )
                    size = output_file.stat().st_size
                    print(f"    ✓ Saved: {output_file} ({size // 1024}KB)")
                    return True

        print(f"    ✗ No image in outputs")
        return False

    except Exception as e:
        print(f"    ✗ Error: {e}")
        return False


def main():
    import argparse
    p = argparse.ArgumentParser(description="CyberTarot Nightly Art Factory")
    p.add_argument("--references", default=str(REFERENCES_DIR),
                   help="Folder with reference images")
    p.add_argument("--model", choices=["sd15", "sdxl"], default="sd15")
    p.add_argument("--denoise", type=float, default=0.65,
                   help="Style strength: 0=copy ref, 1=ignore ref (default 0.65)")
    p.add_argument("--only", help="Generate only this card ID")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    ref_dir = Path(args.references)
    refs = find_references(ref_dir)

    print(f"\n=== CyberTarot Nightly Art Factory ===")
    print(f"References: {len(refs)} images in {ref_dir}")
    for r in refs:
        print(f"  - {r.name} ({r.stat().st_size // 1024}KB)")

    if not refs:
        print(f"✗ No reference images found in {ref_dir}")
        sys.exit(1)

    # Check server
    if not args.dry_run:
        try:
            with urllib.request.urlopen(f"{COMFY_URL}/system_stats", timeout=5) as r:
                stats = json.loads(r.read())
            dev = stats.get("devices", [{}])[0]
            print(f"ComfyUI: {stats['system']['comfyui_version']}")
            print(f"GPU: {dev['name']} | VRAM free: {dev.get('vram_free', 0) // (1024**3):.1f}GB")
        except Exception as e:
            print(f"✗ ComfyUI not reachable at {COMFY_URL}: {e}")
            sys.exit(1)

    # Load prompts
    with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
        prompts = json.load(f)

    if args.only:
        if args.only not in prompts:
            print(f"✗ Card '{args.only}' not found")
            sys.exit(1)
        prompts = {args.only: prompts[args.only]}

    print(f"\nCards to generate: {len(prompts)}")
    print(f"Model: {args.model} | Denoise: {args.denoise}")

    if args.dry_run:
        # Pick one reference per card (round-robin)
        for i, (cid, cdata) in enumerate(prompts.items()):
            ref = refs[i % len(refs)]
            print(f"  {cid}: {cdata['name']} ← ref: {ref.name}")
        return

    # Generate: rotate through references for variety
    success = 0
    failed = 0
    for i, (cid, cdata) in enumerate(prompts.items()):
        ref = refs[i % len(refs)]
        if generate_card_with_style(cid, cdata, args.model, ref, args.denoise):
            success += 1
        else:
            failed += 1
        # Brief pause between submissions
        time.sleep(2)

    print(f"\n=== Done: {success} generated, {failed} failed ===")
    print(f"Output: {OUTPUT_DIR}")

    # Write manifest
    manifest = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": args.model,
        "denoise": args.denoise,
        "references": [r.name for r in refs],
        "cards_generated": success,
        "cards_failed": failed,
    }
    manifest_path = SCRIPT_DIR / "last_run.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
