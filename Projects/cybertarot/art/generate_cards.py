#!/usr/bin/env python3
"""
CyberTarot — Card Art Generator via ComfyUI REST API
Generates tarot card art in Cyberpunk + Van Gogh + Gaudi style.

Usage:
  python generate_cards.py                    # generate ALL cards
  python generate_cards.py --only 00_fool     # generate one card
  python generate_cards.py --model sd15       # use SD 1.5 (faster, 512x768)
  python generate_cards.py --model sdxl       # use SDXL (slower, 1024x1536)
  python generate_cards.py --dry-run          # print prompts without generating
"""

import json
import sys
import os
import time
import urllib.request
import urllib.error
from pathlib import Path

# --- Config ---
COMFY_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8189")
SCRIPT_DIR = Path(__file__).parent
PROMPTS_FILE = SCRIPT_DIR / "prompts.json"
OUTPUT_DIR = SCRIPT_DIR / "cards"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MODELS = {
    "sd15": "v1-5-pruned-emaonly.safetensors",
    "sdxl": "sd_xl_base_1.0.safetensors",
}

# Master style prompt — applied to every card
STYLE_PREFIX = (
    "breathtaking digital painting of cyberpunk tarot card, "
    "Van Gogh swirling impasto brushstrokes, Gaudi organic trencadis mosaic architecture, "
    "sacred geometry, ornate golden border, vertical composition, "
)
STYLE_SUFFIX = (
    ", ultra detailed, masterpiece, dramatic cinematic lighting, "
    "oil painting texture, vivid saturated colors, dark atmospheric background, "
    "trending on ArtStation, 8K quality"
)

NEGATIVE_PROMPT = (
    "low quality, blurry, deformed, ugly, text, watermark, "
    "bad anatomy, extra limbs, jpeg artifacts, cropped, "
    "flat colors, cartoon, anime style, 3d render, photograph"
)


def build_prompt(card_data: dict) -> str:
    return (
        f"{STYLE_PREFIX}"
        f'"{card_data["name"]}", {card_data["concept"]}, '
        f"color palette: {card_data['colors']}, "
        f"mood: {card_data['mood']}"
        f"{STYLE_SUFFIX}"
    )


def submit_workflow(prompt_text: str, negative: str, model: str, seed: int = -1) -> dict:
    """Submit a txt2img workflow to ComfyUI and return the response."""
    if seed == -1:
        seed = int(time.time()) % (2**32)

    is_sdxl = "xl" in model.lower()
    w, h = (1024, 1536) if is_sdxl else (512, 768)
    steps = 25 if is_sdxl else 20
    cfg = 7.5

    workflow = {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "euler_ancestral",
                "scheduler": "normal",
                "denoise": 1.0,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
            },
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": model},
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": w, "height": h, "batch_size": 1},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt_text, "clip": ["4", 1]},
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative, "clip": ["4", 1]},
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {"images": ["8", 0], "filename_prefix": "cybertarot"},
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


def poll_result(prompt_id: str, timeout: int = 300) -> dict | None:
    """Poll /history/{prompt_id} until the job is done."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            url = f"{COMFY_URL}/history/{prompt_id}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read())
            if prompt_id in data:
                return data[prompt_id]
        except Exception:
            pass
        time.sleep(2)
    return None


def download_image(filename: str, subfolder: str, output_path: Path):
    """Download a generated image from ComfyUI."""
    url = f"{COMFY_URL}/view?filename={filename}&subfolder={subfolder}&type=output"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        output_path.write_bytes(resp.read())


def generate_card(card_id: str, card_data: dict, model_key: str = "sd15") -> bool:
    """Generate one card. Returns True on success."""
    model_file = MODELS[model_key]
    prompt_text = build_prompt(card_data)
    output_file = OUTPUT_DIR / f"{card_id}.png"

    if output_file.exists():
        print(f"  ✓ {card_id} already exists, skipping")
        return True

    print(f"  → Generating {card_id} ({card_data['name']})...")
    print(f"    Model: {model_file}")
    print(f"    Prompt: {prompt_text[:120]}...")

    try:
        result = submit_workflow(prompt_text, NEGATIVE_PROMPT, model_file)
        prompt_id = result.get("prompt_id")
        if not prompt_id:
            print(f"    ✗ No prompt_id returned: {result}")
            return False

        print(f"    Submitted: {prompt_id}")
        print(f"    Waiting for generation...")

        history = poll_result(prompt_id, timeout=600)
        if not history:
            print(f"    ✗ Timeout waiting for {card_id}")
            return False

        # Extract output image
        outputs = history.get("outputs", {})
        for node_id, node_output in outputs.items():
            if "images" in node_output:
                for img in node_output["images"]:
                    filename = img["filename"]
                    subfolder = img.get("subfolder", "")
                    download_image(filename, subfolder, output_file)
                    size = output_file.stat().st_size
                    print(f"    ✓ Saved: {output_file} ({size // 1024}KB)")
                    return True

        print(f"    ✗ No image in outputs: {outputs}")
        return False

    except Exception as e:
        print(f"    ✗ Error: {e}")
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="CyberTarot Card Generator")
    parser.add_argument("--only", help="Generate only this card ID (e.g. 00_fool)")
    parser.add_argument("--model", choices=["sd15", "sdxl"], default="sd15",
                        help="Model to use (sd15=faster 512x768, sdxl=slower 1024x1536)")
    parser.add_argument("--dry-run", action="store_true", help="Print prompts without generating")
    args = parser.parse_args()

    # Check server
    if not args.dry_run:
        try:
            with urllib.request.urlopen(f"{COMFY_URL}/system_stats", timeout=5) as r:
                stats = json.loads(r.read())
            dev = stats.get("devices", [{}])[0]
            print(f"ComfyUI: {stats.get('system', {}).get('comfyui_version', '?')}")
            print(f"GPU: {dev.get('name', '?')} | VRAM free: {dev.get('vram_free', 0) // (1024**3):.1f}GB")
        except Exception as e:
            print(f"✗ ComfyUI not reachable at {COMFY_URL}: {e}")
            sys.exit(1)

    # Load prompts
    with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
        prompts = json.load(f)

    print(f"\n=== CyberTarot Card Generator ===")
    print(f"Cards: {len(prompts)} | Model: {args.model}")

    if args.only:
        if args.only not in prompts:
            print(f"✗ Card '{args.only}' not found in prompts.json")
            sys.exit(1)
        prompts = {args.only: prompts[args.only]}

    if args.dry_run:
        for cid, cdata in prompts.items():
            print(f"\n--- {cid}: {cdata['name']} ---")
            print(f"Prompt: {build_prompt(cdata)}")
        return

    success = 0
    failed = 0
    for cid, cdata in prompts.items():
        if generate_card(cid, cdata, args.model):
            success += 1
        else:
            failed += 1

    print(f"\n=== Done: {success} generated, {failed} failed ===")
    print(f"Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
