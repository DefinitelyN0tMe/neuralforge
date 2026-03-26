#!/usr/bin/env python3
"""
Image → Video → 3D Pipeline
Fully automated with smart VRAM management
"""

import json
import os
import shutil
import socket
import time
import urllib.request
from pathlib import Path
from datetime import datetime


PANEL_URL = "http://localhost:9000"
COMFYUI_URL = "http://localhost:8188"
OUTPUT_DIR = Path("/home/definitelynotme/Desktop/pipeline_output")
OUTPUT_DIR.mkdir(exist_ok=True)

# ─── Ready-to-use example prompts ────────────────────────────────
EXAMPLES = {
    "robot": {
        "prompt": "a cute chibi robot character with glowing blue eyes, metallic silver body, small antenna, standing pose, 3D render style, studio lighting, white background",
        "video_prompt": "the robot slowly waves its hand and tilts its head curiously, smooth motion",
        "steps": "image,video,3d",
    },
    "dragon": {
        "prompt": "a baby crystal dragon sitting on a rock, translucent purple scales, glowing from inside, fantasy art style, white background, centered",
        "video_prompt": "the dragon spreads its tiny wings and breathes a small sparkle of fire",
        "steps": "image,video,3d",
    },
    "car": {
        "prompt": "a futuristic cyberpunk sports car, neon blue accents, sleek aerodynamic design, concept art, studio photo, white background",
        "video_prompt": "the car slowly rotates showing all angles, headlights turn on",
        "steps": "image,video,3d",
    },
    "cat": {
        "prompt": "an adorable cat astronaut in a tiny spacesuit, holding a small flag, cartoon 3D style, white background, centered, high detail",
        "video_prompt": "the cat astronaut plants the flag and salutes, floating slightly",
        "steps": "image,video,3d",
    },
    "sword": {
        "prompt": "an ancient magical sword with glowing runes on the blade, crystal pommel, ethereal blue energy, fantasy game asset, white background, centered",
        "video_prompt": "the sword slowly rotates, runes pulsing with light",
        "steps": "image,3d",
    },
}


def api_call(endpoint: str, method: str = "GET", data: dict = None) -> dict:
    url = f"{PANEL_URL}{endpoint}"
    if data:
        payload = json.dumps(data).encode('utf-8')
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method=method)
    else:
        req = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def wait_for_service(port: int, timeout: int = 120) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2)
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    return True
        except Exception:
            pass
        time.sleep(3)
    return False


def free_vram():
    print("  🧹 Freeing VRAM...")
    try:
        api_call("/api/actions/stop-all-heavy", method="POST")
    except Exception:
        pass
    try:
        api_call("/api/actions/free-vram", method="POST")
    except Exception:
        pass
    time.sleep(5)


def stop_service(name: str):
    try:
        api_call(f"/api/module/{name}.yaml/stop", method="POST")
    except Exception:
        pass
    time.sleep(3)


def start_service(name: str, port: int, timeout: int = 120) -> bool:
    print(f"  🚀 Starting {name}...")
    api_call(f"/api/module/{name}.yaml/start", method="POST")
    if not wait_for_service(port, timeout):
        print(f"  ❌ {name} failed to start in {timeout}s")
        return False
    time.sleep(5)  # give it a moment to fully load
    print(f"  ✅ {name} ready")
    return True


# ─── Step 1: Image via ComfyUI ──────────────────────────────────
def step1_generate_image(prompt: str) -> str | None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"\n{'─'*55}")
    print(f"  📸 STEP 1: Image generation  [{ts}]")
    print(f"  Prompt: {prompt[:80]}...")
    print(f"{'─'*55}")

    free_vram()

    if not start_service("comfyui", 8188):
        return None

    workflow = {
        "prompt": {
            "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "flux-2-klein-4b-fp8.safetensors", "weight_dtype": "default"}},
            "2": {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae.safetensors"}},
            "3": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_3_4b.safetensors", "type": "flux2"}},
            "4": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["3", 0]}},
            "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1024, "batch_size": 1}},
            "6": {"class_type": "KSampler", "inputs": {
                "model": ["1", 0], "positive": ["4", 0], "negative": ["4", 0],
                "latent_image": ["5", 0], "seed": int(time.time()) % 999999,
                "steps": 4, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0
            }},
            "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["2", 0]}},
            "8": {"class_type": "SaveImage", "inputs": {"images": ["7", 0], "filename_prefix": "pipeline"}},
        }
    }

    print("  🎨 Generating...")
    payload = json.dumps(workflow).encode('utf-8')
    req = urllib.request.Request(f"{COMFYUI_URL}/api/prompt", data=payload, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=120)
    resp_data = json.loads(resp.read())
    prompt_id = resp_data.get("prompt_id", "")

    # Poll for completion
    print("  ⏳ Waiting for result...", end="", flush=True)
    comfyui_output = Path("/home/definitelynotme/Desktop/ComfyUI/output")
    for _ in range(60):  # max 120 seconds
        time.sleep(2)
        print(".", end="", flush=True)
        # Check history for completion
        try:
            hist_req = urllib.request.Request(f"{COMFYUI_URL}/api/history/{prompt_id}")
            hist_resp = urllib.request.urlopen(hist_req, timeout=10)
            hist = json.loads(hist_resp.read())
            if prompt_id in hist:
                outputs = hist[prompt_id].get("outputs", {})
                for node_id, node_out in outputs.items():
                    images = node_out.get("images", [])
                    if images:
                        fname = images[0]["filename"]
                        subfolder = images[0].get("subfolder", "")
                        src = comfyui_output / subfolder / fname if subfolder else comfyui_output / fname
                        if src.exists():
                            dest = OUTPUT_DIR / f"step1_{int(time.time())}.png"
                            shutil.copy2(str(src), str(dest))
                            print(f"\n  ✅ Done: {dest}")
                            return str(dest)
        except Exception:
            pass

    # Fallback: find latest pipeline image
    print()
    images = sorted(comfyui_output.glob("pipeline_*.png"), key=lambda f: f.stat().st_mtime, reverse=True)
    if images:
        dest = OUTPUT_DIR / f"step1_{int(time.time())}.png"
        shutil.copy2(str(images[0]), str(dest))
        print(f"  ✅ Done (fallback): {dest}")
        return str(dest)

    print("  ❌ Image was not generated")
    return None


# ─── Step 2: Video via Wan2GP Gradio API ─────────────────────────
def step2_generate_video(image_path: str, prompt: str) -> str | None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"\n{'─'*55}")
    print(f"  🎬 STEP 2: Video generation  [{ts}]")
    print(f"  From: {image_path}")
    print(f"  Prompt: {prompt[:60]}...")
    print(f"{'─'*55}")

    stop_service("comfyui")
    free_vram()

    if not start_service("wan2gp", 7860, timeout=150):
        return None

    # Try Gradio API automation
    try:
        from gradio_client import Client, handle_file
        print("  🤖 Connecting to Wan2GP API...")
        client = Client("http://localhost:7860", verbose=False)

        # Discover available API endpoints
        api_info = client.view_api(print_info=False, return_format="dict")
        endpoints = api_info.get("named_endpoints", {})
        unnamed = api_info.get("unnamed_endpoints", {})

        print(f"  📡 API endpoints: {list(endpoints.keys()) if endpoints else list(unnamed.keys())[:5]}")

        # Try common Wan2GP i2v endpoint patterns
        result = None
        for ep_name in ["/image_to_video", "/i2v_generate", "/generate", "/run"]:
            if ep_name in endpoints:
                print(f"  ▶ Calling {ep_name}...")
                result = client.predict(
                    handle_file(image_path),
                    prompt,
                    api_name=ep_name,
                )
                break

        if result is None and unnamed:
            # Try first unnamed endpoint
            print("  ▶ Calling unnamed endpoint...")
            result = client.predict(
                handle_file(image_path),
                prompt,
            )

        if result:
            # Result could be file path or tuple
            video_path = result if isinstance(result, str) else (result[0] if isinstance(result, (list, tuple)) else str(result))
            if isinstance(video_path, dict):
                video_path = video_path.get("video", video_path.get("value", ""))
            if video_path and Path(video_path).exists():
                dest = OUTPUT_DIR / f"step2_{int(time.time())}.mp4"
                shutil.copy2(video_path, str(dest))
                print(f"  ✅ Video: {dest}")
                return str(dest)

        print("  ⚠️ Gradio API returned unexpected result, switching to manual mode")
    except Exception as e:
        print(f"  ⚠️ Gradio API: {e}")

    # Fallback — manual
    print(f"\n  📋 MANUAL MODE:")
    print(f"     1. Open http://localhost:7860")
    print(f"     2. Upload: {image_path}")
    print(f"     3. Prompt: {prompt}")
    print(f"     4. Click Generate")
    return f"MANUAL:http://localhost:7860"


# ─── Step 3: 3D via Hunyuan3D Gradio API ─────────────────────────
def step3_generate_3d(image_path: str) -> str | None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"\n{'─'*55}")
    print(f"  🧊 STEP 3: 3D model generation  [{ts}]")
    print(f"  From: {image_path}")
    print(f"{'─'*55}")

    stop_service("wan2gp")
    free_vram()

    if not start_service("hunyuan3d", 7870, timeout=180):
        return None

    # Try Gradio API automation
    try:
        from gradio_client import Client, handle_file
        print("  🤖 Connecting to Hunyuan3D API...")
        client = Client("http://localhost:7870", verbose=False)

        api_info = client.view_api(print_info=False, return_format="dict")
        endpoints = api_info.get("named_endpoints", {})
        unnamed = api_info.get("unnamed_endpoints", {})

        print(f"  📡 API endpoints: {list(endpoints.keys()) if endpoints else list(unnamed.keys())[:5]}")

        result = None
        for ep_name in ["/image_to_3d", "/generate_3d", "/generate", "/run"]:
            if ep_name in endpoints:
                print(f"  ▶ Calling {ep_name}...")
                result = client.predict(
                    handle_file(image_path),
                    api_name=ep_name,
                )
                break

        if result is None and unnamed:
            print("  ▶ Calling unnamed endpoint...")
            result = client.predict(handle_file(image_path))

        if result:
            model_path = result if isinstance(result, str) else (result[0] if isinstance(result, (list, tuple)) else str(result))
            if isinstance(model_path, dict):
                model_path = model_path.get("model", model_path.get("value", ""))
            if model_path and Path(model_path).exists():
                ext = Path(model_path).suffix or ".glb"
                dest = OUTPUT_DIR / f"step3_{int(time.time())}{ext}"
                shutil.copy2(model_path, str(dest))
                print(f"  ✅ 3D model: {dest}")
                return str(dest)

        print("  ⚠️ Gradio API returned unexpected result, switching to manual mode")
    except Exception as e:
        print(f"  ⚠️ Gradio API: {e}")

    # Fallback — manual
    print(f"\n  📋 MANUAL MODE:")
    print(f"     1. Open http://localhost:7870")
    print(f"     2. Upload: {image_path}")
    print(f"     3. Click Generate")
    return f"MANUAL:http://localhost:7870"


# ─── Pipeline orchestrator ────────────────────────────────────────
def run_pipeline(prompt: str, steps: str = "image,video,3d", video_prompt: str = ""):
    start_time = time.time()
    step_list = [s.strip() for s in steps.split(",")]

    print(f"\n{'━'*55}")
    print(f"  🔄 PIPELINE: {' → '.join(s.upper() for s in step_list)}")
    print(f"  Prompt: {prompt[:70]}...")
    if video_prompt:
        print(f"  Video:  {video_prompt[:70]}...")
    print(f"{'━'*55}")

    results = {}

    # Step 1: Image
    if "image" in step_list:
        image_path = step1_generate_image(prompt)
        results["image"] = image_path
        if not image_path:
            print("\n  ❌ Pipeline stopped — image was not created")
            return results

    # Step 2: Video
    if "video" in step_list:
        img = results.get("image")
        if img:
            vp = video_prompt or prompt
            results["video"] = step2_generate_video(img, vp)

    # Step 3: 3D
    if "3d" in step_list:
        img = results.get("image")
        if img:
            results["3d"] = step3_generate_3d(img)

    # Done — cleanup
    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    print(f"\n{'━'*55}")
    print(f"  ✅ PIPELINE COMPLETE  ({minutes}m {seconds}s)")
    print(f"{'─'*55}")
    for k, v in results.items():
        icon = {"image": "📸", "video": "🎬", "3d": "🧊"}.get(k, "•")
        print(f"  {icon} {k}: {v}")
    print(f"{'─'*55}")
    print(f"  📂 Results: {OUTPUT_DIR}")
    print(f"{'━'*55}")

    return results


# ─── CLI ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Image → Video → 3D Pipeline")
    parser.add_argument("prompt", nargs="?", help="Image generation prompt")
    parser.add_argument("--steps", default="image,video,3d", help="Steps: image,video,3d")
    parser.add_argument("--video-prompt", default="", help="Optional separate prompt for video")
    parser.add_argument("--example", choices=list(EXAMPLES.keys()), help="Use a ready-made example")
    parser.add_argument("--list-examples", action="store_true", help="List available examples")
    parser.add_argument("--config", default="", help="JSON config string")
    args = parser.parse_args()

    if args.list_examples:
        print("\n📋 Available examples:\n")
        for name, ex in EXAMPLES.items():
            print(f"  {name:10s}  {ex['prompt'][:60]}...")
            print(f"  {'':10s}  steps: {ex['steps']}")
            print()
        exit(0)

    if args.config:
        config = json.loads(args.config)
        prompt = config.get("prompt", "")
        steps = config.get("steps", "image,video,3d")
        video_prompt = config.get("video_prompt", "")
    elif args.example:
        ex = EXAMPLES[args.example]
        prompt = ex["prompt"]
        steps = ex["steps"]
        video_prompt = ex.get("video_prompt", "")
    elif args.prompt:
        prompt = args.prompt
        steps = args.steps
        video_prompt = args.video_prompt
    else:
        # Default demo
        ex = EXAMPLES["robot"]
        prompt = ex["prompt"]
        steps = ex["steps"]
        video_prompt = ex.get("video_prompt", "")
        print("  ℹ️  Using example 'robot'. To choose: --example cat")

    run_pipeline(prompt, steps, video_prompt)
