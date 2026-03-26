#!/usr/bin/env python3
"""
MCP Server for NeuralForge
Allows Claude Code to directly manage services, run agents, search RAG, etc.
"""

import json
import subprocess
import time
import urllib.request
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("NeuralForge")

PANEL_URL = "http://localhost:9000"
QDRANT_URL = "http://localhost:6333"
OLLAMA_URL = "http://localhost:11434"


def api_call(endpoint: str, method: str = "GET", data: dict = None) -> dict:
    """Call NeuralForge API"""
    url = f"{PANEL_URL}{endpoint}"
    if data:
        payload = json.dumps(data).encode('utf-8')
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method=method)
    else:
        req = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


@mcp.tool()
def get_system_status() -> str:
    """Get current system status: GPU, RAM, CPU, disk usage and all running services"""
    data = api_call("/api/status")
    gpu = data["gpu"]
    sys_info = data["system"]

    lines = [
        f"GPU: {gpu['mem_used']}MB / {gpu['mem_total']}MB VRAM ({gpu['temp']}°C, {gpu['util']}%)",
        f"RAM: {sys_info['ram_used_gb']}GB / {sys_info['ram_total_gb']}GB ({sys_info['ram_available_gb']}GB available)",
        f"CPU: {sys_info['cpu_percent']}% ({sys_info['cpu_count']} threads)",
        f"Disk: {sys_info['disk_used_gb']}GB / {sys_info['disk_total_gb']}GB ({sys_info['disk_free_gb']}GB free)",
        "",
        "Services:",
    ]
    for m in data["modules"]:
        vram = f" [{m['vram_mb']}MB VRAM]" if m.get('vram_mb', 0) > 0 else ""
        lines.append(f"  {'●' if m['status']=='running' else '○'} {m['name']}: {m['status']}{vram} (:{m.get('port','?')})")

    ollama = data.get("ollama_models", [])
    if ollama:
        lines.append("\nLoaded LLM models:")
        for m in ollama:
            lines.append(f"  ● {m['name']} ({m['vram_gb']}GB VRAM)")

    return "\n".join(lines)


@mcp.tool()
def start_service(service_name: str) -> str:
    """Start an AI service. Names: comfyui, wan2gp, hunyuan3d, ace-step, qwen3-tts, whisper-webui, ollama, open-webui, perplexica, searxng, qdrant"""
    # Map friendly names to yaml filenames
    name_map = {
        "comfyui": "comfyui.yaml", "wan2gp": "wan2gp.yaml", "wan": "wan2gp.yaml",
        "hunyuan3d": "hunyuan3d.yaml", "hunyuan": "hunyuan3d.yaml", "3d": "hunyuan3d.yaml",
        "ace-step": "ace-step.yaml", "music": "ace-step.yaml",
        "qwen3-tts": "qwen3-tts.yaml", "tts": "qwen3-tts.yaml",
        "whisper": "whisper-webui.yaml", "stt": "whisper-webui.yaml",
        "ollama": "ollama.yaml", "open-webui": "open-webui.yaml",
        "perplexica": "perplexica.yaml", "searxng": "searxng.yaml",
        "qdrant": "qdrant.yaml",
    }
    filename = name_map.get(service_name.lower().replace(" ", ""), f"{service_name}.yaml")
    result = api_call(f"/api/module/{filename}/start", method="POST")
    return result.get("message", str(result))


@mcp.tool()
def stop_service(service_name: str) -> str:
    """Stop an AI service."""
    name_map = {
        "comfyui": "comfyui.yaml", "wan2gp": "wan2gp.yaml", "wan": "wan2gp.yaml",
        "hunyuan3d": "hunyuan3d.yaml", "hunyuan": "hunyuan3d.yaml",
        "ace-step": "ace-step.yaml", "music": "ace-step.yaml",
        "qwen3-tts": "qwen3-tts.yaml", "tts": "qwen3-tts.yaml",
        "whisper": "whisper-webui.yaml", "stt": "whisper-webui.yaml",
        "ollama": "ollama.yaml", "open-webui": "open-webui.yaml",
        "perplexica": "perplexica.yaml", "searxng": "searxng.yaml",
        "qdrant": "qdrant.yaml",
    }
    filename = name_map.get(service_name.lower().replace(" ", ""), f"{service_name}.yaml")
    result = api_call(f"/api/module/{filename}/stop", method="POST")
    return result.get("message", str(result))


@mcp.tool()
def rag_search(query: str, collection: str = "estonian_laws") -> str:
    """Search documents in RAG vector database. Default collection: estonian_laws (Estonian legislation)"""
    try:
        # Get embedding
        payload = json.dumps({"model": "bge-m3", "input": query}).encode('utf-8')
        req = urllib.request.Request(f"{OLLAMA_URL}/api/embed", data=payload,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            vec = json.loads(resp.read())["embeddings"][0]

        # Search Qdrant
        payload = json.dumps({"vector": vec, "limit": 5, "with_payload": True}).encode('utf-8')
        req = urllib.request.Request(f"{QDRANT_URL}/collections/{collection}/points/search",
            data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        results = []
        for p in data.get("result", []):
            results.append(f"[Score: {p['score']:.4f}] Source: {p['payload']['source']}\n{p['payload']['text'][:500]}")

        return "\n\n---\n\n".join(results) if results else "No results found"
    except Exception as e:
        return f"RAG search error: {e}"


@mcp.tool()
def rag_list_collections() -> str:
    """List all RAG document collections with their sizes"""
    try:
        data = api_call("/api/rag/status")
        lines = []
        for c in data.get("collections", []):
            lines.append(f"  {c['name']}: {c['points']:,} vectors ({c['status']})")
        return "\n".join(lines) if lines else "No collections"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def get_storage_info() -> str:
    """Get storage usage for generated content (images, video, music, etc)"""
    data = api_call("/api/storage")
    lines = []
    total = 0
    for s in data.get("storage", []):
        lines.append(f"  {s['name']}: {s['files']} files, {s['size_mb']} MB")
        total += s['size_mb']
    lines.append(f"\n  Total: {total:.1f} MB")
    return "\n".join(lines)


@mcp.tool()
def cleanup_storage(service: str) -> str:
    """Clean up generated files for a service. Services: comfyui, wan2gp, ace-step, whisper-webui, gradio-cache"""
    name_map = {
        "comfyui": "comfyui.yaml", "wan2gp": "wan2gp.yaml",
        "ace-step": "ace-step.yaml", "music": "ace-step.yaml",
        "whisper": "whisper-webui.yaml", "gradio": "gradio-cache",
    }
    key = name_map.get(service.lower(), service)
    result = api_call(f"/api/cleanup/{key}", method="POST")
    return result.get("message", str(result))


@mcp.tool()
def finetune_status() -> str:
    """Get current LoRA fine-tuning status, training log, and list of trained adapters"""
    data = api_call("/api/finetune")
    lines = [f"Status: {data.get('status', 'idle')}"]

    if data.get("status") == "running":
        elapsed = int(time.time() - data.get("started", 0))
        lines.append(f"Model: {data.get('model', '?')}")
        lines.append(f"Elapsed: {elapsed//60}m {elapsed%60}s")
        if data.get("log"):
            lines.append(f"\nLog (last 500 chars):\n{data['log'][-500:]}")

    adapters = data.get("adapters", [])
    if adapters:
        lines.append(f"\nTrained adapters ({len(adapters)}):")
        for a in adapters:
            lines.append(f"  {a.get('base_model','?').split('/')[-1]} — Loss: {a.get('final_loss','?')}, {a.get('timestamp','')}")

    lines.append(f"\nAvailable models: {', '.join(data.get('models', {}).keys())}")
    return "\n".join(lines)


@mcp.tool()
def finetune_start(model: str, dataset_path: str, epochs: int = 3, lora_rank: int = 16) -> str:
    """Start LoRA fine-tuning. Model example: unsloth/Qwen2.5-7B-Instruct. Dataset: path to JSON/CSV file."""
    result = api_call("/api/finetune/start", method="POST", data={
        "model": model,
        "dataset": dataset_path,
        "epochs": epochs,
        "rank": lora_rank,
    })
    return result.get("message", str(result))


@mcp.tool()
def finetune_stop() -> str:
    """Stop current LoRA fine-tuning"""
    result = api_call("/api/finetune/stop", method="POST")
    return result.get("message", str(result))


@mcp.tool()
def run_pipeline(prompt: str, steps: str = "image,video,3d") -> str:
    """Run Image→Video→3D generation pipeline with smart VRAM management. Steps: image, video, 3d (comma-separated)."""
    import subprocess
    config = json.dumps({"prompt": prompt, "steps": steps})
    result = subprocess.run(
        ["bash", "-c", f"source /home/definitelynotme/Desktop/ai-panel/venv/bin/activate && python3 /home/definitelynotme/Desktop/ai-panel/pipeline.py --config '{config}'"],
        capture_output=True, text=True, timeout=300
    )
    return result.stdout[-3000:] if result.returncode == 0 else f"Error: {result.stderr[-1000:]}"


@mcp.tool()
def run_backup() -> str:
    """Run AI Station backup — saves configs, agent memory, workflows, panel settings"""
    import subprocess
    result = subprocess.run(
        ["bash", "/home/definitelynotme/Desktop/ai-panel/backup.sh"],
        capture_output=True, text=True, timeout=60
    )
    return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"


@mcp.tool()
def get_gpu_processes() -> str:
    """Show what's using GPU VRAM right now"""
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if not result.stdout.strip():
            return "GPU is idle — nothing is using VRAM"
        lines = ["PID | Process | VRAM"]
        for line in result.stdout.strip().split("\n"):
            parts = [x.strip() for x in line.split(",")]
            if len(parts) >= 3:
                lines.append(f"{parts[0]} | {parts[1]} | {parts[2]} MB")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def ollama_loaded_models() -> str:
    """Show which LLM models are currently loaded in Ollama VRAM"""
    try:
        req = urllib.request.Request("http://localhost:11434/api/ps")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            models = data.get("models", [])
            if not models:
                return "No loaded models — VRAM is free"
            lines = []
            for m in models:
                vram = round(m.get("size_vram", 0) / 1024**3, 1)
                lines.append(f"● {m['name']} — {vram} GB VRAM")
            return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def rag_index_file(file_path: str, collection: str = "default") -> str:
    """Index a file into RAG vector database. Supports: PDF, TXT, MD, CSV, JSON, Python files."""
    try:
        import subprocess
        result = subprocess.run(
            ["bash", "-c", f"source /home/definitelynotme/Desktop/Claude_Test/.venv/bin/activate && python3 /home/definitelynotme/Desktop/Claude_Test/agents/rag_tool.py index-file --path '{file_path}' --collection '{collection}'"],
            capture_output=True, text=True, timeout=120
        )
        return result.stdout if result.stdout else result.stderr
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def rag_index_directory(dir_path: str, collection: str = "default") -> str:
    """Index all files in a directory into RAG. Supports: PDF, TXT, MD, CSV, JSON, Python files."""
    try:
        import subprocess
        result = subprocess.run(
            ["bash", "-c", f"source /home/definitelynotme/Desktop/Claude_Test/.venv/bin/activate && python3 /home/definitelynotme/Desktop/Claude_Test/agents/rag_tool.py index-dir --path '{dir_path}' --collection '{collection}'"],
            capture_output=True, text=True, timeout=600
        )
        return result.stdout[-2000:] if result.stdout else result.stderr
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def convert_audio(input_path: str, output_format: str = "wav") -> str:
    """Convert audio file to another format (wav, mp3, flac). Useful for Whisper STT and Qwen3-TTS."""
    try:
        from pathlib import Path
        p = Path(input_path)
        output_path = str(p.with_suffix(f".{output_format}"))
        import subprocess
        result = subprocess.run(
            ["ffmpeg", "-i", input_path, output_path, "-y"],
            capture_output=True, text=True, timeout=60
        )
        if Path(output_path).exists():
            return f"Converted: {output_path}"
        return f"Error: {result.stderr[-200:]}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def run_agent(task: str, role: str = "researcher", model: str = "qwen3.5:35b-a3b") -> str:
    """Run a single AI agent with a task. Roles: researcher, coder, analyst, writer, summarizer, critic, translator, email_writer, tester, trade_analyst, tutor, security_auditor"""
    result = api_call("/api/agents/run", method="POST", data={
        "task": task, "role": role, "model": model, "tools": []
    })
    if not result.get("ok"):
        return result.get("message", "Error")

    # Poll for result
    for _ in range(120):
        time.sleep(5)
        status = api_call("/api/agents/status")
        if status.get("status") != "running":
            return status.get("log", "")[-3000:]
    return "Timeout: agent still running after 10 minutes"


@mcp.tool()
def run_agent_team(task: str, chain: str = "researcher,writer", model_override: str = "") -> str:
    """Run a team of AI agents. Chain example: researcher,analyst,writer,critic. Each agent passes results to next."""
    chain_list = [r.strip() for r in chain.split(",")]
    result = api_call("/api/agents/run-team", method="POST", data={
        "task": task, "chain": chain_list, "model_override": model_override or None
    })
    if not result.get("ok"):
        return result.get("message", "Error")

    for _ in range(180):
        time.sleep(5)
        status = api_call("/api/agents/status")
        if status.get("status") != "running":
            return status.get("log", "")[-5000:]
    return "Timeout: team still running after 15 minutes"


@mcp.tool()
def run_orchestrator(task: str) -> str:
    """Run AI Orchestrator — automatically selects agents, order, and models for the task."""
    result = api_call("/api/agents/run-orchestrator", method="POST", data={"task": task})
    if not result.get("ok"):
        return result.get("message", "Error")

    for _ in range(180):
        time.sleep(5)
        status = api_call("/api/agents/status")
        if status.get("status") != "running":
            return status.get("log", "")[-5000:]
    return "Timeout: orchestrator still running after 15 minutes"


@mcp.tool()
def stop_all_and_free_vram() -> str:
    """Emergency: stop all heavy GPU services AND unload all LLM models to completely free VRAM"""
    r1 = api_call("/api/actions/stop-all-heavy", method="POST")
    r2 = api_call("/api/actions/free-vram", method="POST")
    return f"{r1.get('message','')} | {r2.get('message','')}"


@mcp.tool()
def generate_image(prompt: str) -> str:
    """Generate an image using FLUX Klein 4B via ComfyUI. Returns path to generated image."""
    # Start ComfyUI if needed
    api_call("/api/module/comfyui.yaml/start", method="POST")
    import socket
    for _ in range(30):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            if s.connect_ex(("127.0.0.1", 8188)) == 0:
                break
            s.close()
        except Exception:
            pass
        time.sleep(2)

    time.sleep(3)

    workflow = {
        "prompt": {
            "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "flux-2-klein-4b-fp8.safetensors", "weight_dtype": "default"}},
            "2": {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae.safetensors"}},
            "3": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_3_4b.safetensors", "type": "flux2"}},
            "4": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["3", 0]}},
            "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1024, "batch_size": 1}},
            "6": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["4", 0], "negative": ["4", 0], "latent_image": ["5", 0], "seed": int(time.time()) % 999999, "steps": 4, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
            "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["2", 0]}},
            "8": {"class_type": "SaveImage", "inputs": {"images": ["7", 0], "filename_prefix": "mcp_gen"}},
        }
    }
    payload = json.dumps(workflow).encode('utf-8')
    req = urllib.request.Request("http://localhost:8188/api/prompt", data=payload, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=120)
    time.sleep(15)

    from pathlib import Path
    images = sorted(Path("/home/definitelynotme/Desktop/ComfyUI/output").glob("mcp_gen_*.png"), key=lambda f: f.stat().st_mtime, reverse=True)
    return f"Image saved: {images[0]}" if images else "Generation may still be processing"


@mcp.tool()
def ask_rag(question: str, collection: str = "estonian_laws", language: str = "english") -> str:
    """Ask a question to RAG system — searches documents and generates answer using LLM"""
    result = api_call("/api/rag/chat", method="POST", data={
        "query": question,
        "collection": collection,
        "model": "nemotron-3-nano:30b",
        "language": language,
    })
    if result.get("ok"):
        answer = result.get("answer", "No answer")
        sources = result.get("sources", [])
        src_text = "\n".join(f"  [{s['score']}] {s['source']}" for s in sources[:3])
        return f"{answer}\n\nSources:\n{src_text}"
    return result.get("message", "Error")


@mcp.tool()
def check_health() -> str:
    """Check system health — returns alerts for GPU temperature, VRAM, RAM, disk, service outages"""
    data = api_call("/api/health")
    if data.get("healthy") and not data.get("alerts"):
        return "✅ System healthy — no alerts"
    lines = [f"Healthy: {data.get('healthy', '?')}"]
    for a in data.get("alerts", []):
        icon = "🔴" if a["level"] == "critical" else "⚠️"
        lines.append(f"{icon} {a['msg']}")
    return "\n".join(lines)


@mcp.resource("status://system")
def system_status_resource() -> str:
    """Current system status as a resource"""
    data = api_call("/api/status")
    gpu = data["gpu"]
    sys_info = data["system"]
    return f"GPU: {gpu['mem_used']}MB/{gpu['mem_total']}MB ({gpu['temp']}°C) | RAM: {sys_info['ram_used_gb']}/{sys_info['ram_total_gb']}GB | CPU: {sys_info['cpu_percent']}%"


if __name__ == "__main__":
    mcp.run(transport="stdio")
