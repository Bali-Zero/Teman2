#!/usr/bin/env python3
"""
ComfyUI Flux Image Generator — replaces gemini_image_generator.py
Generates cover images via ComfyUI API (localhost:8000) using Flux.1 Dev Q8.
Falls back to Pollinations.ai (free, no auth) if ComfyUI is unavailable.
Used by both intel scraper (step 8) and war-room (step 3).
"""
import json
import sys
import time
import uuid
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from typing import Optional

COMFYUI_URL = "http://127.0.0.1:8000"
POLLINATIONS_URL = "https://image.pollinations.ai/prompt"

# Flux.1 Dev GGUF workflow — minimal text-to-image
WORKFLOW_TEMPLATE = {
    "3": {
        "class_type": "UnetLoaderGGUF",
        "inputs": {
            "unet_name": "flux1-dev-Q8_0.gguf"
        }
    },
    "6": {
        "class_type": "DualCLIPLoader",
        "inputs": {
            "clip_name1": "clip_l.safetensors",
            "clip_name2": "t5xxl_fp8_e4m3fn.safetensors",
            "type": "flux"
        }
    },
    "8": {
        "class_type": "VAELoader",
        "inputs": {
            "vae_name": "ae.safetensors"
        }
    },
    "10": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": "",  # filled at runtime
            "clip": ["6", 0]
        }
    },
    "13": {
        "class_type": "EmptyLatentImage",
        "inputs": {
            "width": 1024,
            "height": 1024,
            "batch_size": 1
        }
    },
    "14": {
        "class_type": "FluxGuidance",
        "inputs": {
            "guidance": 3.5,
            "conditioning": ["10", 0]
        }
    },
    "15": {
        "class_type": "KSampler",
        "inputs": {
            "seed": 0,  # randomized at runtime
            "steps": 8,  # Flux works well at 8 steps on MPS (vs 20 default)
            "cfg": 1.0,
            "sampler_name": "euler",
            "scheduler": "simple",
            "denoise": 1.0,
            "model": ["3", 0],
            "positive": ["14", 0],
            "negative": ["10", 0],
            "latent_image": ["13", 0]
        }
    },
    "17": {
        "class_type": "VAEDecode",
        "inputs": {
            "samples": ["15", 0],
            "vae": ["8", 0]
        }
    },
    "19": {
        "class_type": "SaveImage",
        "inputs": {
            "filename_prefix": "flux_output",
            "images": ["17", 0]
        }
    }
}


def check_comfyui() -> bool:
    """Check if ComfyUI is running."""
    try:
        resp = urllib.request.urlopen(f"{COMFYUI_URL}/system_stats", timeout=5)
        return resp.status == 200
    except Exception:
        return False


def queue_prompt(prompt_text: str, width: int = 1024, height: int = 1024,
                 filename_prefix: str = "flux_output") -> Optional[str]:
    """Queue a Flux image generation and return the prompt_id."""
    workflow = json.loads(json.dumps(WORKFLOW_TEMPLATE))

    # Set prompt text
    workflow["10"]["inputs"]["text"] = prompt_text
    # Random seed
    workflow["15"]["inputs"]["seed"] = int(time.time() * 1000) % (2**32)
    # Image dimensions
    workflow["13"]["inputs"]["width"] = width
    workflow["13"]["inputs"]["height"] = height
    # Filename
    workflow["19"]["inputs"]["filename_prefix"] = filename_prefix

    payload = json.dumps({"prompt": workflow, "client_id": str(uuid.uuid4())}).encode()
    req = urllib.request.Request(
        f"{COMFYUI_URL}/prompt",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read())
        return data.get("prompt_id")
    except Exception as e:
        print(f"Error queuing prompt: {e}", file=sys.stderr)
        return None


def wait_for_completion(prompt_id: str, timeout: int = 300) -> Optional[dict]:
    """Poll ComfyUI until the prompt completes. Returns history entry."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = urllib.request.urlopen(f"{COMFYUI_URL}/history/{prompt_id}", timeout=10)
            data = json.loads(resp.read())
            if prompt_id in data:
                return data[prompt_id]
        except Exception:
            pass
        time.sleep(3)
    return None


def get_image_path(history: dict) -> Optional[str]:
    """Extract the output image filename from history."""
    outputs = history.get("outputs", {})
    for node_id, node_out in outputs.items():
        images = node_out.get("images", [])
        if images:
            return images[0].get("filename")
    return None


def download_image(filename: str, dest: Path) -> bool:
    """Download generated image from ComfyUI output."""
    try:
        url = f"{COMFYUI_URL}/view?filename={filename}&type=output"
        resp = urllib.request.urlopen(url, timeout=30)
        dest.write_bytes(resp.read())
        return dest.stat().st_size > 5000
    except Exception as e:
        print(f"Download error: {e}", file=sys.stderr)
        return False


def generate_image(prompt: str, output_path: Path,
                   width: int = 1024, height: int = 1024,
                   timeout: int = 300) -> bool:
    """Full pipeline: queue → wait → download."""
    prefix = output_path.stem
    prompt_id = queue_prompt(prompt, width, height, prefix)
    if not prompt_id:
        return False

    print(f"  Queued: {prompt_id}", file=sys.stderr)
    history = wait_for_completion(prompt_id, timeout)
    if not history:
        print(f"  Timeout after {timeout}s", file=sys.stderr)
        return False

    if history.get("status", {}).get("status_str") == "error":
        print(f"  Generation error: {history.get('status', {}).get('messages', '')}", file=sys.stderr)
        return False

    filename = get_image_path(history)
    if not filename:
        print(f"  No output image found", file=sys.stderr)
        return False

    if download_image(filename, output_path):
        print(f"  Saved: {output_path} ({output_path.stat().st_size / 1024:.0f}KB)", file=sys.stderr)
        return True
    return False


# ── Pollinations.ai fallback ──

def generate_image_pollinations(prompt: str, output_path: Path,
                                width: int = 1200, height: int = 630) -> bool:
    """Fallback: generate via Pollinations.ai (free, no auth).
    Tries each available model in order until one succeeds.
    Used when ComfyUI is not available (e.g. machine off, cold start)."""
    # Models in preference order (quality → speed)
    models = ["sana", "turbo", "zimage"]
    encoded = urllib.parse.quote(prompt)
    seed = int(time.time()) % 99999

    for model in models:
        url = f"{POLLINATIONS_URL}/{encoded}?width={width}&height={height}&seed={seed}&nologo=true&model={model}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "BaliZero-IntelScraper/1.0"})
            resp = urllib.request.urlopen(req, timeout=90)
            if resp.status != 200:
                print(f"  Pollinations [{model}]: HTTP {resp.status}", file=sys.stderr)
                continue
            data = resp.read()
            if len(data) < 5000:
                print(f"  Pollinations [{model}]: response too small ({len(data)} bytes)", file=sys.stderr)
                continue
            output_path.write_bytes(data)
            print(f"  Saved via Pollinations [{model}]: {output_path} ({len(data) // 1024}KB)", file=sys.stderr)
            return True
        except Exception as e:
            print(f"  Pollinations [{model}] error: {e}", file=sys.stderr)

    return False


# ── CLI entrypoint for intel scraper step 8 ──
def main():
    """
    Usage: python comfyui_image_generator.py <state_file>
    Reads pipeline state, generates cover images for enriched articles.
    """
    if len(sys.argv) < 2:
        print("Usage: comfyui_image_generator.py <state_file>", file=sys.stderr)
        sys.exit(1)

    state_file = Path(sys.argv[1])
    state = json.loads(state_file.read_text())
    articles = state.get("articles", [])
    # Only generate covers for articles that were actually published
    targets = [a for a in articles if a.get("_published_item_id") and a.get("enrichment")]

    if not targets:
        print("No published articles with enrichment — nothing to do", file=sys.stderr)
        sys.exit(0)

    use_comfyui = check_comfyui()
    if use_comfyui:
        print("ComfyUI available — using local Flux", file=sys.stderr)
    else:
        print("ComfyUI not running — falling back to Pollinations.ai", file=sys.stderr)

    output_dir = state_file.parent / "images"
    output_dir.mkdir(exist_ok=True)
    generated = 0

    for i, art in enumerate(targets):
        enr = art.get("enrichment", {})
        title = enr.get("headline", art.get("title", ""))
        category = art.get("category", "general")

        # Build editorial prompt using Bali Zero brand style
        # Pass summary so Claude can generate symbolic (not literal) visuals
        from bz_image_style import build_cover_prompt
        summary = enr.get("the_facts", enr.get("bali_zero_take", ""))
        prompt = build_cover_prompt(title, category, summary=summary or None)

        item_id = art.get("_published_item_id", f"article_{i}")
        img_path = output_dir / f"cover_{item_id}.png"
        print(f"\n[{i+1}/{len(targets)}] {title[:60]}...", file=sys.stderr)

        if use_comfyui:
            # First image takes ~5min (model load), subsequent ~30s
            img_timeout = 600 if i == 0 else 180
            ok = generate_image(prompt, img_path, width=1200, height=630, timeout=img_timeout)
            if not ok:
                print(f"  ComfyUI failed — trying Pollinations fallback", file=sys.stderr)
                ok = generate_image_pollinations(prompt, img_path)
        else:
            ok = generate_image_pollinations(prompt, img_path)

        if ok:
            art["image_path"] = str(img_path)
            art["image_source"] = "comfyui" if use_comfyui else "pollinations"
            generated += 1
        else:
            print(f"  Failed — skipping", file=sys.stderr)

        time.sleep(2)

    # Update state file
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    print(f"\nGenerated {generated}/{len(targets)} cover images", file=sys.stderr)


if __name__ == "__main__":
    main()
