#!/usr/bin/env python3
"""
NeuralForge — Backend
Unified dashboard for managing local AI services
"""

import asyncio
import json
import re
import os
import signal
import subprocess
import time
import urllib.request
import urllib.parse
import threading
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

import docker
import psutil
import yaml
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

import metrics
import model_resolver
from model_resolver import resolve_model

@asynccontextmanager
async def lifespan(_app):
    # Start only once the server has actually bound its port — this keeps
    # crash-looping duplicate instances (that fail to bind :9000) from
    # polluting metrics with phantom samples.
    metrics.start_sampler(60)
    asyncio.get_running_loop().run_in_executor(None, _autostart_modules)
    yield


app = FastAPI(title="NeuralForge", lifespan=lifespan)


def _autostart_modules():
    """Start modules marked `autostart: true` that aren't running (e.g. the RAG
    reranker after a reboot). systemd units are skipped — they need sudo and
    have their own enablement."""
    # Startup runs before uvicorn binds :9000 — give it a moment, then make sure
    # this is the instance that actually owns the port (not a duplicate that is
    # about to die with "address already in use").
    time.sleep(3)
    me = psutil.Process()
    conns = me.net_connections("tcp") if hasattr(me, "net_connections") else me.connections("tcp")
    if not any(c.status == psutil.CONN_LISTEN and c.laddr.port == 9000 for c in conns):
        return
    for m in load_modules():
        if not m.get("autostart") or m.get("type") not in ("process", "docker"):
            continue
        try:
            if get_module_status(m)["status"] == "stopped":
                print(f"[autostart] starting {m['name']}", flush=True)
                start_module(m)
        except Exception as e:
            print(f"[autostart] {m['name']} failed: {e}", flush=True)


Path("static").mkdir(exist_ok=True)  # empty dirs aren't in git — a fresh clone lacks it
app.mount("/static", StaticFiles(directory="static"), name="static")

MODULES_DIR = Path("modules")
LOG_DIR = Path("/tmp/ai-panel-logs")
LOG_DIR.mkdir(exist_ok=True)
SECRETS_FILE = Path("secrets.json")


def _safe_name(name: str) -> str:
    """Strip any directory part from a user-supplied file name/id (blocks ../ traversal)."""
    return Path(name).name


def _load_secrets() -> dict:
    if SECRETS_FILE.exists():
        try:
            return json.loads(SECRETS_FILE.read_text())
        except Exception:
            pass
    return {}


# ─── Module Loading ───────────────────────────────────────────────

def load_modules() -> list[dict]:
    modules = []
    for f in sorted(MODULES_DIR.glob("*.yaml")):
        with open(f) as fh:
            m = yaml.safe_load(fh)
            m["_file"] = f.name
            modules.append(m)
    return modules


# ─── System Metrics ───────────────────────────────────────────────

_GPU_CACHE_TTL = 2.0
_gpu_cache: dict = {}


def _cached(key: str, fn):
    """nvidia-smi is slow (~100ms) and called per module per refresh — cache briefly."""
    hit = _gpu_cache.get(key)
    if hit and time.monotonic() - hit[0] < _GPU_CACHE_TTL:
        return hit[1]
    value = fn()
    _gpu_cache[key] = (time.monotonic(), value)
    return value


def _explain_gpu_error(output: str) -> str:
    if "Driver/library version mismatch" in output:
        return ("NVIDIA driver was updated but the old kernel module is still loaded "
                "(Driver/library version mismatch). Reboot to load the new driver.")
    if "couldn't communicate with the NVIDIA driver" in output:
        return "NVIDIA driver is not loaded. Check the driver installation and reboot."
    return output.strip().splitlines()[0][:200] if output.strip() else "nvidia-smi returned no data"


def _query_gpu_info() -> dict:
    empty = {"mem_used": 0, "mem_free": 0, "mem_total": 0, "temp": 0, "power": 0, "util": 0,
             "name": "N/A", "error": None}
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.free,memory.total,temperature.gpu,power.draw,utilization.gpu,name",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return {**empty, "error": _explain_gpu_error(result.stdout + result.stderr)}
        parts = [x.strip() for x in result.stdout.strip().splitlines()[0].split(",")]

        def num(v, cast):
            # nvidia-smi prints "[N/A]" for sensors some GPUs don't expose
            try:
                return cast(float(v))
            except ValueError:
                return 0

        return {
            "mem_used": num(parts[0], int),
            "mem_free": num(parts[1], int),
            "mem_total": num(parts[2], int),
            "temp": num(parts[3], int),
            "power": num(parts[4], float),
            "util": num(parts[5], int),
            "name": parts[6],
            "error": None,
        }
    except FileNotFoundError:
        return {**empty, "error": "nvidia-smi not found — NVIDIA driver is not installed"}
    except Exception as e:
        return {**empty, "error": f"GPU query failed: {e}"}


def get_gpu_info() -> dict:
    return _cached("info", _query_gpu_info)


def _query_gpu_processes() -> list[dict]:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return []
        procs = []
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                parts = [x.strip() for x in line.split(",")]
                procs.append({"pid": int(parts[0]), "name": parts[1], "vram_mb": int(parts[2])})
        return procs
    except Exception:
        return []


def get_gpu_processes() -> list[dict]:
    return _cached("procs", _query_gpu_processes)


def get_system_info() -> dict:
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    load = psutil.getloadavg()
    return {
        "ram_used_gb": round(mem.used / 1024**3, 1),
        "ram_available_gb": round(mem.available / 1024**3, 1),
        "ram_total_gb": round(mem.total / 1024**3, 1),
        "ram_percent": mem.percent,
        "disk_used_gb": round(disk.used / 1024**3),
        "disk_free_gb": round(disk.free / 1024**3),
        "disk_total_gb": round(disk.total / 1024**3),
        "disk_percent": round(disk.percent),
        "cpu_percent": psutil.cpu_percent(interval=0.5),
        "cpu_count": psutil.cpu_count(),
        "load_1m": round(load[0], 2),
    }


# ─── Service Status ───────────────────────────────────────────────

def check_port(port: int) -> bool:
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            return s.connect_ex(("127.0.0.1", port)) == 0
    except Exception:
        return False


def get_module_status(module: dict) -> dict:
    mtype = module.get("type", "")
    status = "stopped"
    pid = None
    vram_mb = 0

    if mtype == "systemd":
        try:
            result = subprocess.run(
                ["systemctl", "is-active", module["service_name"]],
                capture_output=True, text=True, timeout=3
            )
            if result.stdout.strip() == "active":
                status = "running"
        except Exception:
            pass

    elif mtype == "docker":
        try:
            client = docker.from_env()
            container = client.containers.get(module["container_name"])
            if container.status == "running":
                status = "running"
        except Exception:
            pass

    elif mtype == "process":
        # First check if port is open (most reliable)
        port = module.get("port")
        if port and check_port(port):
            status = "running"
        else:
            # Fallback to process pattern
            pattern = module.get("process_pattern", "")
            if pattern:
                try:
                    # Use ps + grep to avoid pgrep matching itself
                    result = subprocess.run(
                        ["bash", "-c", f"ps aux | grep '[{pattern[0]}]{pattern[1:]}' | grep -v grep | head -1 | awk '{{print $2}}'"],
                        capture_output=True, text=True, timeout=3
                    )
                    pid_str = result.stdout.strip()
                    if pid_str and pid_str.isdigit():
                        status = "starting"  # process exists but port not ready
                        pid = int(pid_str)
                except Exception:
                    pass

    # Check VRAM usage — match by process pattern across all GPU processes
    if status in ("running", "starting"):
        pattern = module.get("process_pattern", "")
        for gp in get_gpu_processes():
            if pid and gp["pid"] == pid:
                vram_mb = gp["vram_mb"]
                break
            # Also try matching by name
            try:
                proc = psutil.Process(gp["pid"])
                cmdline = " ".join(proc.cmdline())
                if pattern and pattern in cmdline:
                    vram_mb = gp["vram_mb"]
                    pid = gp["pid"]
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    return {
        "status": status,
        "pid": pid,
        "vram_mb": vram_mb,
    }


# ─── Service Control ──────────────────────────────────────────────

def start_module(module: dict) -> dict:
    mtype = module.get("type", "")

    if mtype == "systemd":
        subprocess.run(["sudo", "systemctl", "start", module["service_name"]], timeout=10)
        return {"ok": True, "message": f"{module['name']} started"}

    elif mtype == "docker":
        try:
            client = docker.from_env()
            container = client.containers.get(module["container_name"])
            container.start()
            return {"ok": True, "message": f"{module['name']} started"}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    elif mtype == "process":
        work_dir = module.get("work_dir", "")
        venv = module.get("venv", "")
        cmd = module.get("start_cmd", "")
        log_file = LOG_DIR / f"{module['_file'].replace('.yaml', '.log')}"

        if venv:
            activate = f"source {venv}/bin/activate"
            full_cmd = f"cd {work_dir} && {activate} && {cmd}"
        else:
            full_cmd = f"cd {work_dir} && {cmd}"

        env = os.environ.copy()
        secrets = _load_secrets()
        if secrets.get("hf_token"):
            env["HF_TOKEN"] = secrets["hf_token"]

        log_fh = open(log_file, "w")
        subprocess.Popen(
            ["bash", "-c", full_cmd],
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            cwd=work_dir,
            env=env,
        )
        log_fh.close()
        return {"ok": True, "message": f"{module['name']} starting...", "log": str(log_file)}

    return {"ok": False, "message": "Unknown module type"}


def stop_module(module: dict) -> dict:
    mtype = module.get("type", "")

    if mtype == "systemd":
        subprocess.run(["sudo", "systemctl", "stop", module["service_name"]], timeout=10)
        return {"ok": True, "message": f"{module['name']} stopped"}

    elif mtype == "docker":
        try:
            client = docker.from_env()
            container = client.containers.get(module["container_name"])
            container.stop(timeout=10)
            return {"ok": True, "message": f"{module['name']} stopped"}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    elif mtype == "process":
        pattern = module.get("process_pattern", "")
        port = module.get("port")
        killed = False
        # Method 1: Kill by port via fuser (works without root)
        if port:
            try:
                subprocess.run(["fuser", "-k", f"{port}/tcp"], capture_output=True, timeout=5)
                killed = True
            except Exception:
                pass
        # Method 2: Kill by port via lsof
        if not killed and port:
            try:
                result = subprocess.run(
                    ["lsof", "-ti", f":{port}"],
                    capture_output=True, text=True, timeout=5
                )
                for pid_str in result.stdout.strip().split("\n"):
                    if pid_str.strip().isdigit():
                        os.kill(int(pid_str.strip()), signal.SIGTERM)
                        killed = True
            except Exception:
                pass
        # Method 3: Kill by pattern
        if not killed and pattern:
            subprocess.run(["pkill", "-f", pattern], timeout=5, capture_output=True)
        time.sleep(3)
        # Force kill if still running
        if port and check_port(port):
            try:
                subprocess.run(["fuser", "-k", "-9", f"{port}/tcp"], capture_output=True, timeout=5)
            except Exception:
                subprocess.run(["bash", "-c", f"lsof -ti:{port} | xargs kill -9 2>/dev/null"], capture_output=True, timeout=5)
        return {"ok": True, "message": f"{module['name']} stopped"}

    return {"ok": False, "message": "Unknown module type"}


# ─── API Routes ───────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse("templates/index.html")


def get_ollama_loaded() -> list:
    """Check which LLM models are currently loaded in Ollama"""
    try:
        req = urllib.request.Request("http://localhost:11434/api/ps")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            models = []
            for m in data.get("models", []):
                size_gb = round(m.get("size", 0) / 1024**3, 1)
                vram_gb = round(m.get("size_vram", 0) / 1024**3, 1)
                models.append({
                    "name": m.get("name", "?"),
                    "size_gb": size_gb,
                    "vram_gb": vram_gb,
                    "processor": m.get("details", {}).get("parameter_size", ""),
                    "expires": m.get("expires_at", ""),
                })
            return models
    except Exception:
        return []


# ─── Quick Actions ─────────────────────────────────────────────────

@app.post("/api/actions/stop-all-heavy")
def api_stop_all_heavy():
    """Stop all GPU-heavy services to free VRAM"""
    stopped = []
    modules = load_modules()
    for m in modules:
        if m.get("exclusive_group") == "heavy_gpu" or (m.get("type") == "process" and m.get("vram_estimate", "0") != "0 GB"):
            s = get_module_status(m)
            if s["status"] in ("running", "starting"):
                stop_module(m)
                stopped.append(m["name"])
    return {"ok": True, "message": f"Stopped: {', '.join(stopped)}" if stopped else "Nothing to stop"}


@app.post("/api/actions/start-basics")
def api_start_basics():
    """Ensure all basic services are running"""
    started = []
    basic_files = ["ollama.yaml", "open-webui.yaml", "perplexica.yaml", "searxng.yaml", "qdrant.yaml"]
    modules = load_modules()
    for m in modules:
        if m["_file"] in basic_files:
            s = get_module_status(m)
            if s["status"] != "running":
                start_module(m)
                started.append(m["name"])
    return {"ok": True, "message": f"Started: {', '.join(started)}" if started else "Everything is already running"}


@app.post("/api/actions/free-vram")
def api_free_vram():
    """Unload all Ollama models to free VRAM"""
    try:
        req = urllib.request.Request("http://localhost:11434/api/ps")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            unloaded = []
            for m in data.get("models", []):
                payload = json.dumps({"model": m["name"], "keep_alive": 0}).encode('utf-8')
                req2 = urllib.request.Request("http://localhost:11434/api/generate",
                    data=payload, headers={"Content-Type": "application/json"})
                urllib.request.urlopen(req2, timeout=10)
                unloaded.append(m["name"])
        return {"ok": True, "message": f"Unloaded: {', '.join(unloaded)}" if unloaded else "VRAM is already free"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


# ─── Telegram Bot API ──────────────────────────────────────────────

TG_CONFIG = Path("/home/definitelynotme/Desktop/NeuralForge/panel/telegram_config.json")
TG_SESSIONS_DIR = Path("/home/definitelynotme/Desktop/NeuralForge/panel/telegram_sessions")
TG_BOT_SCRIPT = "/home/definitelynotme/Desktop/NeuralForge/panel/telegram_bot.py"
TG_BOT_LOG = Path("/tmp/telegram_bot.log")
TG_HASH_MASK = "••••••••"


@app.get("/api/telegram")
def api_telegram():
    config = json.loads(TG_CONFIG.read_text()) if TG_CONFIG.exists() else {}
    running = _bot_running()
    # Load sessions list
    sessions = []
    if TG_SESSIONS_DIR.exists():
        for f in sorted(TG_SESSIONS_DIR.glob("session_*.json"), reverse=True):
            try:
                s = json.loads(f.read_text())
                total_msgs = sum(len(c["messages"]) for c in s.get("contacts", {}).values())
                sessions.append({
                    "id": s.get("id", f.stem),
                    "started": s.get("started", "?"),
                    "persona": s.get("persona", ""),
                    "model": s.get("model", ""),
                    "contacts": len(s.get("contacts", {})),
                    "messages": total_msgs,
                })
            except Exception:
                pass
    # Never send the API hash to the browser — only whether it's set
    if config.get("api_hash"):
        config["api_hash"] = TG_HASH_MASK
    return {
        "config": config,
        "running": running,
        "sessions": sessions,
        "personas": config.get("personas", {}),
        # Last lines of the bot log — shows why it stopped if it crashed
        "log_tail": TG_BOT_LOG.read_text(errors="replace").splitlines()[-15:] if TG_BOT_LOG.exists() else [],
    }


@app.get("/api/telegram/session/{session_id}")
async def api_telegram_session(session_id: str):
    f = TG_SESSIONS_DIR / f"session_{_safe_name(session_id)}.json"
    if not f.exists():
        return {"ok": False, "error": "Session not found"}
    data = json.loads(f.read_text())
    return {"ok": True, "session": data}


@app.delete("/api/telegram/session/{session_id}")
async def api_telegram_delete_session(session_id: str):
    f = TG_SESSIONS_DIR / f"session_{_safe_name(session_id)}.json"
    if f.exists():
        f.unlink()
    return {"ok": True}


@app.post("/api/telegram/config")
async def api_telegram_config(req: Request):
    try:
        new_config = await req.json()
    except Exception:
        return {"ok": False}
    # The UI shows a mask instead of the real hash — don't save the mask over it
    if not new_config.get("api_hash") or str(new_config["api_hash"]).startswith("•"):
        new_config.pop("api_hash", None)
    # Merge with existing
    config = json.loads(TG_CONFIG.read_text()) if TG_CONFIG.exists() else {}
    config.update(new_config)
    TG_CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2))
    return {"ok": True, "message": "Settings saved"}


DEFAULT_PERSONA_IDS = {
    "philosopher", "gopnik", "it_demon", "granny", "noir", "pirate",
    "cat", "conspiracy", "shakespeare", "zombie", "corporate",
    "capybara", "crypto", "custom",
}


@app.post("/api/telegram/personas")
async def api_telegram_persona_create(req: Request):
    """Create a new persona"""
    try:
        data = await req.json()
    except Exception:
        return {"ok": False, "error": "Bad JSON"}
    name = (data.get("name") or "").strip()
    icon = (data.get("icon") or "🤖").strip()
    prompt = (data.get("system_prompt") or "").strip()
    if not name or not prompt:
        return {"ok": False, "error": "Name and prompt are required"}
    # Generate ID from name
    pid = data.get("id") or name.lower().replace(" ", "_")
    import re
    pid = re.sub(r'[^a-z0-9_]', '', pid) or f"persona_{int(__import__('time').time())}"
    config = json.loads(TG_CONFIG.read_text()) if TG_CONFIG.exists() else {}
    personas = config.get("personas", {})
    if pid in personas:
        pid = f"{pid}_{int(__import__('time').time()) % 10000}"
    personas[pid] = {"name": name, "icon": icon, "system_prompt": prompt}
    if data.get("voice_reply"):
        personas[pid]["voice_reply"] = True
    if data.get("send_capybara"):
        personas[pid]["send_capybara"] = True
    config["personas"] = personas
    TG_CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2))
    return {"ok": True, "id": pid, "message": f"Persona \"{name}\" created"}


@app.put("/api/telegram/personas/{persona_id}")
async def api_telegram_persona_update(persona_id: str, req: Request):
    """Update an existing persona"""
    try:
        data = await req.json()
    except Exception:
        return {"ok": False, "error": "Bad JSON"}
    config = json.loads(TG_CONFIG.read_text()) if TG_CONFIG.exists() else {}
    personas = config.get("personas", {})
    if persona_id not in personas:
        return {"ok": False, "error": "Persona not found"}
    p = personas[persona_id]
    if "name" in data and data["name"].strip():
        p["name"] = data["name"].strip()
    if "icon" in data and data["icon"].strip():
        p["icon"] = data["icon"].strip()
    if "system_prompt" in data:
        p["system_prompt"] = data["system_prompt"].strip()
    if "voice_reply" in data:
        p["voice_reply"] = bool(data["voice_reply"])
    if "send_capybara" in data:
        p["send_capybara"] = bool(data["send_capybara"])
    config["personas"] = personas
    TG_CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2))
    return {"ok": True, "message": f"Persona \"{p['name']}\" updated"}


@app.delete("/api/telegram/personas/{persona_id}")
async def api_telegram_persona_delete(persona_id: str):
    """Delete a custom persona (defaults cannot be deleted)"""
    if persona_id in DEFAULT_PERSONA_IDS:
        return {"ok": False, "error": "Default personas cannot be deleted, only edited"}
    config = json.loads(TG_CONFIG.read_text()) if TG_CONFIG.exists() else {}
    personas = config.get("personas", {})
    if persona_id not in personas:
        return {"ok": False, "error": "Persona not found"}
    name = personas[persona_id].get("name", persona_id)
    del personas[persona_id]
    if config.get("active_persona") == persona_id:
        config["active_persona"] = "philosopher"
    config["personas"] = personas
    TG_CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2))
    return {"ok": True, "message": f"Persona \"{name}\" deleted"}


# ─── Telegram login (the bot runs headless and can't prompt for a code) ──

TG_SESSION_PATH = "/home/definitelynotme/Desktop/NeuralForge/panel/telegram_session"
_tg_login: dict = {}  # client / phone / phone_code_hash for the login in progress


def _bot_running() -> bool:
    try:
        return subprocess.run(["pgrep", "-f", "python3 -u " + TG_BOT_SCRIPT],
                              capture_output=True, timeout=3).returncode == 0
    except Exception:
        return False


async def _tg_new_client():
    from telethon import TelegramClient
    config = json.loads(TG_CONFIG.read_text()) if TG_CONFIG.exists() else {}
    if not config.get("api_id") or not config.get("api_hash"):
        raise ValueError("Set API ID and API Hash first (my.telegram.org)")
    client = TelegramClient(TG_SESSION_PATH, int(config["api_id"]), config["api_hash"])
    await client.connect()
    return client


async def _tg_finish_login(client) -> dict:
    me = await client.get_me()
    await client.disconnect()
    _tg_login.clear()
    return {"ok": True, "authorized": True,
            "message": f"Logged in as {me.first_name}" + (f" (@{me.username})" if me.username else "")}


@app.get("/api/telegram/auth/status")
async def api_telegram_auth_status():
    if _bot_running():
        # The bot holds the session file and only keeps running when authorized
        return {"authorized": True, "message": "Bot is running"}
    try:
        client = await _tg_new_client()
    except Exception as e:
        return {"authorized": False, "message": str(e)}
    try:
        if await client.is_user_authorized():
            me = await client.get_me()
            return {"authorized": True, "message": f"Logged in as {me.first_name}"
                    + (f" (@{me.username})" if me.username else "")}
        return {"authorized": False, "message": "Not logged in"}
    finally:
        await client.disconnect()


@app.post("/api/telegram/auth/send-code")
async def api_telegram_send_code(req: Request):
    data = await req.json()
    phone = (data.get("phone") or "").strip().replace(" ", "")
    if not phone:
        return {"ok": False, "message": "Enter your phone number"}
    if _bot_running():
        return {"ok": False, "message": "Stop the bot first"}
    old = _tg_login.get("client")
    if old:
        await old.disconnect()
    try:
        client = await _tg_new_client()
        sent = await client.send_code_request(phone)
    except Exception as e:
        return {"ok": False, "message": f"Failed to send code: {e}"}
    _tg_login.update(client=client, phone=phone, phone_code_hash=sent.phone_code_hash)
    return {"ok": True, "message": "Code sent — check Telegram on your other device"}


@app.post("/api/telegram/auth/sign-in")
async def api_telegram_sign_in(req: Request):
    from telethon.errors import SessionPasswordNeededError
    data = await req.json()
    client = _tg_login.get("client")
    if not client:
        return {"ok": False, "message": "Request a code first"}
    try:
        if data.get("password"):
            await client.sign_in(password=data["password"])
        else:
            code = (data.get("code") or "").strip()
            if not code:
                return {"ok": False, "message": "Enter the code"}
            await client.sign_in(_tg_login["phone"], code, phone_code_hash=_tg_login["phone_code_hash"])
    except SessionPasswordNeededError:
        return {"ok": False, "need_password": True, "message": "Two-step verification is on — enter your cloud password"}
    except Exception as e:
        return {"ok": False, "message": f"Sign-in failed: {e}"}
    return await _tg_finish_login(client)


@app.post("/api/telegram/start")
async def api_telegram_start():
    if _bot_running():
        return {"ok": False, "message": "Bot is already running"}
    status = await api_telegram_auth_status()
    if not status["authorized"]:
        return {"ok": False, "need_login": True,
                "message": f"Telegram account is not logged in — log in first ({status['message']})"}
    # Ensure enabled in config
    config = json.loads(TG_CONFIG.read_text()) if TG_CONFIG.exists() else {}
    config["enabled"] = True
    TG_CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2))
    # Start bot
    venv = "/home/definitelynotme/Desktop/NeuralForge/panel/venv"
    tg_log_fh = open(TG_BOT_LOG, "w")
    subprocess.Popen(
        ["bash", "-c", f"source {venv}/bin/activate && python3 -u {TG_BOT_SCRIPT}"],
        stdout=tg_log_fh,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    tg_log_fh.close()
    return {"ok": True, "message": "Telegram bot started"}


@app.post("/api/telegram/stop")
def api_telegram_stop():
    config = json.loads(TG_CONFIG.read_text()) if TG_CONFIG.exists() else {}
    config["enabled"] = False
    TG_CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2))
    subprocess.run(["pkill", "-f", "python3 -u " + TG_BOT_SCRIPT], capture_output=True, timeout=5)
    return {"ok": True, "message": "Telegram bot stopped"}


@app.delete("/api/telegram/sessions")
async def api_telegram_delete_all_sessions():
    """Delete all session files"""
    count = 0
    if TG_SESSIONS_DIR.exists():
        for f in TG_SESSIONS_DIR.glob("session_*.json"):
            f.unlink()
            count += 1
    return {"ok": True, "message": f"Deleted sessions: {count}"}


@app.delete("/api/telegram/messages")
async def api_telegram_clear_messages():
    """Legacy endpoint — kept for compat"""
    return {"ok": True}


@app.get("/api/secrets")
async def api_secrets_get():
    """Return which secrets are configured (without values)."""
    secrets = _load_secrets()
    return {k: bool(v) for k, v in secrets.items()}


@app.post("/api/secrets")
async def api_secrets_save(req: Request):
    """Save API keys to secrets.json."""
    try:
        data = await req.json()
    except Exception:
        return {"ok": False, "message": "Invalid request"}
    secrets = _load_secrets()
    for key in ("hf_token",):
        if key in data and data[key] and data[key] != "••••••••••••":
            secrets[key] = data[key].strip()
    SECRETS_FILE.write_text(json.dumps(secrets, indent=2))
    return {"ok": True, "message": "API key saved"}


@app.get("/api/health")
def api_health():
    """Health monitoring — alerts for GPU temp, disk, RAM"""
    alerts = []
    gpu = get_gpu_info()
    sys_info = get_system_info()

    if gpu.get("error"):
        alerts.append({"level": "critical", "msg": f"GPU monitoring unavailable: {gpu['error']}"})

    if gpu["temp"] > 85:
        alerts.append({"level": "critical", "msg": f"GPU overheating: {gpu['temp']}C (>85)"})
    elif gpu["temp"] > 75:
        alerts.append({"level": "warning", "msg": f"GPU hot: {gpu['temp']}C (>75)"})

    vram_pct = gpu["mem_used"] / gpu["mem_total"] * 100 if gpu["mem_total"] else 0
    if vram_pct > 95:
        alerts.append({"level": "critical", "msg": f"VRAM nearly full: {vram_pct:.0f}%"})

    if sys_info["ram_available_gb"] < 5:
        alerts.append({"level": "critical", "msg": f"Low RAM: {sys_info['ram_available_gb']}GB"})

    if sys_info.get("disk_free_gb", 999) < 50:
        alerts.append({"level": "critical", "msg": f"Low disk space: {sys_info['disk_free_gb']}GB"})

    for name, port in [("Ollama", 11434), ("Qdrant", 6333)]:
        if not check_port(port):
            alerts.append({"level": "critical", "msg": f"{name} not responding :{port}"})

    return {"alerts": alerts, "healthy": len([a for a in alerts if a["level"] == "critical"]) == 0}


@app.get("/api/status")
def api_status():
    modules = load_modules()
    gpu = get_gpu_info()
    system = get_system_info()
    gpu_procs = get_gpu_processes()
    ollama_models = get_ollama_loaded()

    module_statuses = []
    for m in modules:
        s = get_module_status(m)
        module_statuses.append({**m, **s})

    return {
        "gpu": gpu,
        "system": system,
        "gpu_processes": gpu_procs,
        "modules": module_statuses,
        "ollama_models": ollama_models,
    }


@app.post("/api/module/{filename}/start")
def api_start(filename: str):
    modules = load_modules()
    module = next((m for m in modules if m["_file"] == filename), None)
    if not module:
        return {"ok": False, "message": "Module not found"}

    # Check if already running
    current = get_module_status(module)
    if current["status"] in ("running", "starting"):
        return {"ok": False, "message": f"{module['name']} is already running"}

    # Check exclusive group — auto-stop conflicting services
    if module.get("exclusive_group"):
        for m in modules:
            if m["_file"] != filename and m.get("exclusive_group") == module["exclusive_group"]:
                s = get_module_status(m)
                if s["status"] in ("running", "starting"):
                    stop_module(m)
                    time.sleep(5)

    return start_module(module)


@app.post("/api/module/{filename}/stop")
def api_stop(filename: str):
    modules = load_modules()
    module = next((m for m in modules if m["_file"] == filename), None)
    if not module:
        return {"ok": False, "message": "Module not found"}
    return stop_module(module)


@app.get("/api/module/{filename}/log")
def api_log(filename: str):
    log_file = LOG_DIR / filename.replace(".yaml", ".log")
    if log_file.exists():
        lines = log_file.read_text().split("\n")[-50:]
        return {"lines": lines}
    return {"lines": []}


# ─── Agents API ───────────────────────────────────────────────────

AGENTS_DIR = Path("/home/definitelynotme/Desktop/NeuralForge/agents/agents")
AGENTS_VENV = "/home/definitelynotme/Desktop/NeuralForge/agents/.venv"
AGENT_LOGS_DIR = Path("/tmp/ai-panel-agents")
AGENT_LOGS_DIR.mkdir(exist_ok=True)

# Track running agents
_running_agents: dict[str, dict] = {}


UNIVERSAL_AGENT = str(AGENTS_DIR / "universal.py")
TEAM_AGENT = str(AGENTS_DIR / "team.py")
ORCHESTRATOR_AGENT = str(AGENTS_DIR / "orchestrator.py")

ROLE_PRESETS = {
    "researcher": {"name": "Researcher", "icon": "🔍", "desc": "Searches and analyzes information"},
    "coder": {"name": "Programmer", "icon": "💻", "desc": "Writes, tests, and debugs code"},
    "analyst": {"name": "Data Analyst", "icon": "📊", "desc": "Analyzes data, draws conclusions"},
    "writer": {"name": "Content Manager", "icon": "✍️", "desc": "Writes texts, articles, posts"},
    "summarizer": {"name": "Summarizer", "icon": "📋", "desc": "Briefly summarizes content"},
    "critic": {"name": "Critic-Editor", "icon": "🔎", "desc": "Checks facts, improves results"},
    "translator": {"name": "Translator", "icon": "🔄", "desc": "RU, EN, ET, DE, FR, ES + 5 more languages"},
    "email_writer": {"name": "Email Assistant", "icon": "📧", "desc": "Writes emails in the desired style"},
    "tester": {"name": "Tester", "icon": "🧪", "desc": "Writes tests, finds bugs"},
    "trade_analyst": {"name": "Trade Analyst", "icon": "📈", "desc": "Analyzes markets and trends"},
    "tutor": {"name": "Tutor", "icon": "🎓", "desc": "Explains complex things simply"},
    "security_auditor": {"name": "Security Auditor", "icon": "🛡️", "desc": "Finds vulnerabilities in code"},
    "custom": {"name": "Custom Agent", "icon": "🛠️", "desc": "Full customization of role and tools"},
}

AVAILABLE_TOOLS = {
    "web_search": {"name": "Web Search", "icon": "🌐"},
    "read_url": {"name": "Read URL", "icon": "📄"},
    "run_python": {"name": "Python Code", "icon": "🐍"},
    "read_file": {"name": "Read Files", "icon": "📁"},
    "write_file": {"name": "Write Files", "icon": "💾"},
    "analyze_file": {"name": "Analyze Files", "icon": "📊"},
    "analyze_image": {"name": "Analyze Images", "icon": "🖼️"},
    "rag_search": {"name": "RAG Search (documents)", "icon": "📚"},
    "deep_scrape": {"name": "Deep Scraping (multiple URLs)", "icon": "🕸️"},
}

# Human-readable labels for known models. The actual list shown in the UI comes
# from what is installed in Ollama (see get_installed_models), so models that
# are pulled later appear automatically and deleted ones disappear.
MODEL_LABELS = {
    "qwen3.8:27b": "Qwen 3.8 27B (newest, dense, vision)",
    "qwen3.6:35b-a3b": "Qwen 3.6 35B-A3B (MoE, fast workhorse)",
    "qwen3.6:27b": "Qwen 3.6 27B (dense, high quality)",
    "qwen3-coder:30b": "Qwen3-Coder 30B (code)",
    "nemotron-3-nano:30b": "Nemotron 3 Nano 30B (NVIDIA, 1M context)",
    "qwen3.5:9b": "Qwen 3.5 9B (lightweight, fast, vision)",
    "gemma4:26b": "Gemma 4 26B (multilingual, vision)",
    "deepseek-r1:32b": "DeepSeek-R1 32B (reasoning)",
    "deepseek-r1:14b": "DeepSeek-R1 14B (reasoning, lightweight)",
    "phi4-reasoning:14b": "Phi-4 Reasoning 14B (math/logic)",
    "qwen3-vl:8b": "Qwen3-VL 8B (vision, video, GUI)",
    "minicpm-v:8b": "MiniCPM-V 8B (vision, compact)",
    "mistral-small:24b": "Mistral Small 24B (general purpose)",
    "phi4:14b": "Phi 4 14B (compact)",
    "glm-ocr:latest": "GLM-OCR 1.1B (document OCR)",
}
# Order used when sorting the installed list (best general-purpose first)
_MODEL_ORDER = list(MODEL_LABELS)
def get_installed_models() -> list[dict]:
    """Installed Ollama models as [{id, label, size_gb, vision, chat}] for the UI."""
    models = [{
        "id": m["id"],
        "label": MODEL_LABELS.get(m["id"]) or f"{m['id']} ({m['details'].get('parameter_size', '?')})",
        "size_gb": round(m["size"] / 1024**3, 1),
        "vision": "vision" in m["capabilities"],
        "chat": model_resolver.is_chat(m),
    } for m in model_resolver.installed_models() or []]
    models.sort(key=lambda m: (_MODEL_ORDER.index(m["id"]) if m["id"] in _MODEL_ORDER else len(_MODEL_ORDER), m["id"]))
    return models


def available_chat_models() -> dict:
    installed = [m for m in get_installed_models() if m["chat"]]
    if not installed:  # Ollama down — fall back to the known list so the UI isn't empty
        return {k: v for k, v in MODEL_LABELS.items() if "ocr" not in k}
    return {m["id"]: m["label"] for m in installed}


@app.get("/api/llm-models")
def api_llm_models():
    """Installed Ollama models for every model dropdown in the UI."""
    return {"models": get_installed_models()}


def load_agents() -> list[dict]:
    return [{"id": "constructor", "name": "Agent Constructor", "type": "constructor"}]


@app.get("/api/agents")
async def api_agents():
    info = _running_agents.get("constructor")
    status = info["status"] if info else "idle"
    return {
        "roles": ROLE_PRESETS,
        "tools": AVAILABLE_TOOLS,
        "models": available_chat_models(),
        "status": status,
        "current": info,
    }


@app.post("/api/agents/run")
async def api_run_agent(req: Request):
    import uuid

    try:
        request = await req.json()
    except Exception:
        return {"ok": False, "message": "Invalid request"}

    if "constructor" in _running_agents and _running_agents["constructor"]["status"] == "running":
        return {"ok": False, "message": "Agent is already running a task"}

    task_text = request.get("task", "").strip()
    if not task_text:
        return {"ok": False, "message": "Enter a task"}

    role_id = request.get("role", "researcher")
    model_id = resolve_model(request.get("model") or "qwen3.6:35b-a3b")
    tool_ids = request.get("tools", [])
    custom_role = request.get("custom_role", "")
    custom_goal = request.get("custom_goal", "")
    custom_backstory = request.get("custom_backstory", "")

    task_id = str(uuid.uuid4())[:8]
    role_name = ROLE_PRESETS.get(role_id, {}).get("name", role_id)
    log_file = AGENT_LOGS_DIR / f"{role_id}_{task_id}.log"

    attached_files = request.get("attached_files", [])
    export_pdf = request.get("export_pdf", False)

    config = {
        "task": task_text,
        "role": role_id,
        "model": model_id,
        "tools": ",".join(tool_ids) if tool_ids else "",
        "custom_role": custom_role,
        "custom_goal": custom_goal,
        "custom_backstory": custom_backstory,
        "attached_files": attached_files,
        "export_pdf": export_pdf,
    }

    # Write config to temp file to avoid shell escaping issues
    config_file = AGENT_LOGS_DIR / f"config_{task_id}.json"
    config_file.write_text(json.dumps(config, ensure_ascii=False))

    cmd = f"source {AGENTS_VENV}/bin/activate && python3 -u {UNIVERSAL_AGENT} dummy --config \"$(cat {config_file})\""

    proc = subprocess.Popen(
        ["bash", "-c", cmd],
        stdout=open(log_file, "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    _running_agents["constructor"] = {
        "status": "running",
        "task_id": task_id,
        "pid": proc.pid,
        "topic": task_text,
        "role": role_name,
        "model": model_id,
        "log_file": str(log_file),
        "started": time.time(),
    }

    asyncio.get_event_loop().create_task(asyncio.to_thread(proc.wait))

    return {"ok": True, "task_id": task_id, "message": f"{role_name} started: {task_text[:80]}"}


UPLOAD_DIR = Path("/tmp/ai-panel-uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@app.post("/api/agents/upload")
async def api_upload_file(file: UploadFile = File(...)):
    """Upload file for agent analysis"""
    dest = UPLOAD_DIR / Path(file.filename).name
    with open(dest, "wb") as f:
        content = await file.read()
        f.write(content)
    return {"ok": True, "path": str(dest), "name": file.filename, "size": len(content)}


@app.get("/api/agents/pdf/{filename}")
async def api_get_export(filename: str):
    """Download exported PDF or MD"""
    file_path = AGENT_LOGS_DIR / _safe_name(filename)
    if file_path.exists():
        if file_path.suffix == ".pdf":
            return FileResponse(file_path, media_type="application/pdf", filename=filename)
        elif file_path.suffix == ".md":
            return FileResponse(file_path, media_type="text/markdown", filename=filename)
    return {"ok": False, "message": "File not found"}


@app.post("/api/agents/run-team")
async def api_run_team(req: Request):
    import uuid

    try:
        request = await req.json()
    except Exception:
        return {"ok": False, "message": "Invalid request"}

    if "constructor" in _running_agents and _running_agents["constructor"]["status"] == "running":
        return {"ok": False, "message": "Agent is already running a task"}

    task_text = request.get("task", "").strip()
    if not task_text:
        return {"ok": False, "message": "Enter a task"}

    chain = request.get("chain", ["researcher", "writer"])
    model_override = request.get("model_override") or None
    if model_override:
        model_override = resolve_model(model_override)
    attached_files = request.get("attached_files", [])

    if len(chain) < 2:
        return {"ok": False, "message": "Select at least 2 roles for the team"}

    task_id = str(uuid.uuid4())[:8]
    chain_names = " → ".join(ROLE_PRESETS.get(r, {}).get("name", r) for r in chain)
    log_file = AGENT_LOGS_DIR / f"team_{task_id}.log"

    config = {
        "task": task_text,
        "chain": chain,
        "model_override": model_override,
        "attached_files": attached_files,
    }
    config_file = AGENT_LOGS_DIR / f"config_{task_id}.json"
    config_file.write_text(json.dumps(config, ensure_ascii=False))

    cmd = f"source {AGENTS_VENV}/bin/activate && python3 -u {TEAM_AGENT} dummy --config \"$(cat {config_file})\""

    proc = subprocess.Popen(
        ["bash", "-c", cmd],
        stdout=open(log_file, "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    _running_agents["constructor"] = {
        "status": "running",
        "task_id": task_id,
        "pid": proc.pid,
        "topic": task_text,
        "role": f"Team: {chain_names}",
        "model": model_override or "auto",
        "log_file": str(log_file),
        "started": time.time(),
    }

    asyncio.get_event_loop().create_task(asyncio.to_thread(proc.wait))

    return {"ok": True, "task_id": task_id, "message": f"Team started: {chain_names}"}


@app.post("/api/agents/run-orchestrator")
async def api_run_orchestrator(req: Request):
    import uuid

    try:
        request = await req.json()
    except Exception:
        return {"ok": False, "message": "Invalid request"}

    if "constructor" in _running_agents and _running_agents["constructor"]["status"] == "running":
        return {"ok": False, "message": "Agent is already running a task"}

    task_text = request.get("task", "").strip()
    if not task_text:
        return {"ok": False, "message": "Enter a task"}

    attached_files = request.get("attached_files", [])
    export_pdf = request.get("export_pdf", False)
    model_override = request.get("model_override") or None
    if model_override:
        model_override = resolve_model(model_override)

    task_id = str(uuid.uuid4())[:8]
    log_file = AGENT_LOGS_DIR / f"orchestrator_{task_id}.log"

    config = {
        "task": task_text,
        "attached_files": attached_files,
        "model_override": model_override,
    }
    config_file = AGENT_LOGS_DIR / f"config_{task_id}.json"
    config_file.write_text(json.dumps(config, ensure_ascii=False))

    cmd = f"source {AGENTS_VENV}/bin/activate && python3 -u {ORCHESTRATOR_AGENT} dummy --config \"$(cat {config_file})\""

    proc = subprocess.Popen(
        ["bash", "-c", cmd],
        stdout=open(log_file, "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    _running_agents["constructor"] = {
        "status": "running",
        "task_id": task_id,
        "pid": proc.pid,
        "topic": task_text,
        "role": "Orchestrator (auto-select)",
        "model": "auto",
        "log_file": str(log_file),
        "started": time.time(),
    }

    asyncio.get_event_loop().create_task(asyncio.to_thread(proc.wait))

    return {"ok": True, "task_id": task_id, "message": f"Orchestrator started: {task_text[:80]}"}


@app.get("/api/agents/status")
def api_agent_status():
    info = _running_agents.get("constructor")
    if not info:
        return {"status": "idle"}

    # Check if process still running
    try:
        proc = psutil.Process(info["pid"])
        if not proc.is_running():
            info["status"] = "done"
    except psutil.NoSuchProcess:
        info["status"] = "done"

    # Read log
    log_file = Path(info["log_file"])
    log_content = ""
    if log_file.exists():
        log_content = log_file.read_text()

    return {
        "status": info["status"],
        "task_id": info.get("task_id"),
        "topic": info.get("topic"),
        "role": info.get("role"),
        "model": info.get("model"),
        "elapsed": round(time.time() - info["started"]),
        "log": log_content[-8000:],
    }


@app.post("/api/agents/stop")
async def api_stop_agent():
    info = _running_agents.get("constructor")
    if not info or info["status"] != "running":
        return {"ok": False, "message": "Agent is not running"}

    try:
        os.killpg(os.getpgid(info["pid"]), signal.SIGTERM)
    except Exception:
        try:
            os.kill(info["pid"], signal.SIGKILL)
        except Exception:
            pass

    info["status"] = "stopped"
    return {"ok": True, "message": "Agent stopped"}


@app.get("/api/agents/history")
async def api_agent_history():
    """List past agent results"""
    results = []
    for f in sorted(AGENT_LOGS_DIR.glob("*.log"), key=os.path.getmtime, reverse=True)[:20]:
        results.append({
            "file": f.name,
            "size": f.stat().st_size,
            "modified": time.strftime("%d.%m %H:%M", time.localtime(f.stat().st_mtime)),
        })
    return {"history": results}


@app.get("/api/agents/history/{filename}")
async def api_agent_history_view(filename: str):
    """View a specific agent log"""
    log_file = AGENT_LOGS_DIR / _safe_name(filename)
    if log_file.exists() and log_file.suffix == ".log":
        return {"content": log_file.read_text()}
    return {"content": "File not found"}


@app.delete("/api/agents/history/{filename}")
async def api_agent_history_delete(filename: str):
    """Delete a specific agent log + all related files"""
    log_file = AGENT_LOGS_DIR / _safe_name(filename)
    if not (log_file.exists() and log_file.suffix == ".log"):
        return {"ok": False, "message": "File not found"}

    # Extract task_id from filename (e.g. researcher_6f7e9418.log -> 6f7e9418)
    task_id = log_file.stem.split("_")[-1]
    deleted = [log_file.name]
    log_file.unlink()

    # Delete related config, pdf, md
    for pattern in [f"config_{task_id}.json", f"report_*.pdf", f"report_*.md"]:
        for f in AGENT_LOGS_DIR.glob(pattern):
            # For reports, match by checking if created within 5 sec of log
            if pattern.startswith("config_"):
                f.unlink()
                deleted.append(f.name)

    return {"ok": True, "message": f"Deleted: {', '.join(deleted)}"}


@app.delete("/api/agents/history")
async def api_agent_history_clear():
    """Clear all agent history, configs, exports, uploads"""
    count = 0
    # Clean agent logs, configs, exports
    for f in AGENT_LOGS_DIR.glob("*"):
        if f.is_file():
            f.unlink()
            count += 1
    # Clean uploads
    for f in UPLOAD_DIR.glob("*"):
        if f.is_file():
            f.unlink()
            count += 1
    return {"ok": True, "message": f"Deleted {count} files"}


# ─── Cleanup API ──────────────────────────────────────────────────

OUTPUT_DIRS = {
    "comfyui.yaml": {
        "name": "ComfyUI",
        "paths": ["/home/definitelynotme/Desktop/NeuralForge/data/comfyui/output"],
        "extensions": [".png", ".jpg", ".jpeg", ".webp"],
    },
    "wan2gp.yaml": {
        "name": "Wan2GP",
        "paths": ["/home/definitelynotme/Desktop/NeuralForge/data/wan2gp/outputs"],
        "extensions": [".mp4", ".wav", ".mp3", ".png"],
    },
    "ace-step.yaml": {
        "name": "ACE-Step (music)",
        "paths": ["/home/definitelynotme/Desktop/NeuralForge/apps/ACE-Step-1.5/gradio_outputs"],
        "extensions": [".wav", ".mp3", ".flac", ".ogg", ".mid"],
    },
    "whisper-webui.yaml": {
        "name": "Whisper STT (subtitles + BGM)",
        "paths": ["/home/definitelynotme/Desktop/NeuralForge/apps/Whisper-WebUI/outputs"],
        "extensions": [".srt", ".vtt", ".txt", ".tsv", ".json", ".wav", ".mp3", ".flac"],
    },
    "gradio-cache": {
        "name": "Gradio cache (TTS, 3D, etc.)",
        "paths": ["/tmp/gradio"],
        "extensions": None,
    },
}


@app.get("/api/storage")
def api_storage():
    """Get storage usage for each service output"""
    result = []
    for module_file, info in OUTPUT_DIRS.items():
        total_size = 0
        file_count = 0
        for p in info["paths"]:
            path = Path(p)
            if path.exists():
                for f in path.rglob("*"):
                    if f.is_file():
                        if info["extensions"] is None or f.suffix.lower() in info["extensions"]:
                            total_size += f.stat().st_size
                            file_count += 1
        result.append({
            "module": module_file,
            "name": info["name"],
            "size_mb": round(total_size / 1024 / 1024, 1),
            "files": file_count,
        })
    return {"storage": result}


@app.post("/api/cleanup/{module_file}")
def api_cleanup(module_file: str):
    info = OUTPUT_DIRS.get(module_file)
    if not info:
        return {"ok": False, "message": "Unknown module"}

    deleted = 0
    freed = 0
    for p in info["paths"]:
        path = Path(p)
        if not path.exists():
            continue
        for f in path.rglob("*"):
            if f.is_file():
                if info["extensions"] is None or f.suffix.lower() in info["extensions"]:
                    freed += f.stat().st_size
                    f.unlink()
                    deleted += 1
        # Remove empty dirs
        for d in sorted(path.rglob("*"), reverse=True):
            if d.is_dir():
                try:
                    d.rmdir()
                except OSError:
                    pass

    freed_mb = round(freed / 1024 / 1024, 1)
    return {"ok": True, "message": f"{info['name']}: deleted {deleted} files, freed {freed_mb} MB"}


# ─── RAG Indexing Status ──────────────────────────────────────────

@app.get("/api/rag/status")
def api_rag_status():
    """Check RAG indexing status and collections"""
    try:
        # Get collections
        req = urllib.request.Request("http://localhost:6333/collections")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            collections = []
            for c in data.get("result", {}).get("collections", []):
                # Get collection details
                try:
                    req2 = urllib.request.Request(f"http://localhost:6333/collections/{c['name']}")
                    with urllib.request.urlopen(req2, timeout=3) as resp2:
                        details = json.loads(resp2.read()).get("result", {})
                        collections.append({
                            "name": c["name"],
                            "points": details.get("points_count", 0),
                            "status": details.get("status", "?"),
                        })
                except Exception:
                    collections.append({"name": c["name"], "points": 0, "status": "?"})

        # Check if indexing is running
        indexing = False
        indexing_log = ""
        try:
            result = subprocess.run(
                ["bash", "-c", "ps aux | grep 'parse_estonian\\|rag_tool.*index' | grep -v grep | head -1"],
                capture_output=True, text=True, timeout=3
            )
            indexing = bool(result.stdout.strip())
        except Exception:
            pass

        if indexing:
            log_file = Path("/tmp/estonian_laws.log")
            if log_file.exists():
                lines = log_file.read_text().split("\n")
                indexing_log = "\n".join(lines[-5:])

        return {
            "collections": collections,
            "indexing": indexing,
            "log": indexing_log,
        }
    except Exception:
        return {"collections": [], "indexing": False, "log": ""}


# ─── LoRA Fine-Tuning API ─────────────────────────────────────────

FINETUNE_SCRIPT = "/home/definitelynotme/Desktop/NeuralForge/agents/finetune/train_lora.py"
FINETUNE_OUTPUT = Path("/home/definitelynotme/Desktop/NeuralForge/agents/finetune/outputs")
FINETUNE_OUTPUT.mkdir(parents=True, exist_ok=True)
_finetune_status: dict = {}

# Small curated set of classic LoRA bases (always offered). The rest of the
# list is built automatically — see _finetune_catalog().
FINETUNE_MODELS = {
    "unsloth/Qwen3.5-4B": "Qwen 3.5 4B — compact (8 GB, ~1h)",
    "unsloth/NVIDIA-Nemotron-3-Nano-4B": "NVIDIA Nemotron 3 Nano 4B — blazing fast (5 GB, ~30min)",
    "unsloth/Qwen2.5-7B-Instruct": "Qwen 2.5 7B — fast (15 GB, ~1-2h)",
    "unsloth/Llama-3.1-8B-Instruct": "Llama 3.1 8B — general purpose (15 GB, ~1-2h)",
    "unsloth/gemma-3-12b-it": "Gemma 3 12B — Google multimodal (17 GB, ~3-4h)",
    "unsloth/phi-4": "Phi-4 14B — math/science (18 GB, ~3-4h)",
    "unsloth/DeepSeek-R1-Distill-Qwen-14B": "DeepSeek-R1 Distill 14B — reasoning (18 GB, ~3-4h)",
    "unsloth/gpt-oss-20b": "GPT-OSS 20B (OpenAI) — MoE 3.6B active (14 GB, ~2-3h)",
}

# ── Auto catalog: trainable (unsloth) versions of installed Ollama models ──
FT_CATALOG_FILE = Path("data/finetune_catalog.json")
_HF_NAME_ALIASES = {"deepseek-r1": "DeepSeek-R1-Distill-Qwen"}
_HF_SKIP = ("gguf", "mlx", "nvfp4", "fp8", "-base", "omni", "mtp", "bnb", "awq", "gptq")
_ft_lock = threading.Lock()


def _hf_trainable_for(ollama_id: str):
    """unsloth HF repo matching an Ollama model (e.g. qwen3.6:27b -> unsloth/Qwen3.6-27B)."""
    name, _, tag = ollama_id.partition(":")
    size = re.match(r"(\d+(?:\.\d+)?b)", tag.lower())
    if not size:
        return None
    size = size.group(1)
    queries = [_HF_NAME_ALIASES.get(name, name), re.sub(r"([a-z])(\d)", r"\1-\2", name)]
    for q in dict.fromkeys(queries):
        # Network errors propagate so the caller doesn't cache a false "no match"
        url = f"https://huggingface.co/api/models?author=unsloth&search={urllib.parse.quote(q)}&limit=40"
        with urllib.request.urlopen(url, timeout=10) as resp:
            ids = [m["id"] for m in json.loads(resp.read())]
        hits = [i for i in ids if re.search(rf"(^|[-_/]){re.escape(size)}([-_]|$)", i.lower())
                and not any(k in i.lower() for k in _HF_SKIP)]
        if hits:
            # Prefer the instruct/it variant, then the shortest (canonical) repo name
            return sorted(hits, key=lambda i: (not re.search(r"instruct|-it$|-it-", i.lower()), len(i)))[0]
    return None


def _refresh_finetune_catalog():
    """Look up newly installed Ollama models on HF (runs in background, cached on disk)."""
    if not _ft_lock.acquire(blocking=False):
        return
    try:
        cache = json.loads(FT_CATALOG_FILE.read_text()) if FT_CATALOG_FILE.exists() else {}
        changed = False
        for m in model_resolver.installed_models() or []:
            if m["id"] in cache or not model_resolver.is_chat(m):
                continue
            try:
                cache[m["id"]] = _hf_trainable_for(m["id"])
                changed = True
            except Exception:
                break  # offline — try again next time
        if changed:
            FT_CATALOG_FILE.parent.mkdir(exist_ok=True)
            FT_CATALOG_FILE.write_text(json.dumps(cache, indent=2))
    finally:
        _ft_lock.release()


def _hf_downloaded_models() -> list[str]:
    """Text LLMs already in the HF cache (skips TTS/3D/music/embedding repos)."""
    hub = Path(os.environ.get("HF_HOME", Path.home() / ".cache/huggingface")) / "hub"
    found = []
    for d in hub.glob("models--*"):
        for cfg in d.glob("snapshots/*/config.json"):
            try:
                archs = json.loads(cfg.read_text()).get("architectures") or []
            except Exception:
                continue
            # Rerankers/embedders are Qwen3ForCausalLM too, but not chat bases
            if any(a.endswith("ForCausalLM") for a in archs) and not any(
                    k in d.name.lower() for k in ("reranker", "embed", "guard")):
                found.append(d.name[len("models--"):].replace("--", "/", 1))
            break
    return found


def _finetune_catalog() -> dict:
    """{hf_id: label}: installed-model matches first, then downloaded, then curated.
    Follows Ollama — models you pull appear, models you delete disappear."""
    threading.Thread(target=_refresh_finetune_catalog, daemon=True).start()
    cache = json.loads(FT_CATALOG_FILE.read_text()) if FT_CATALOG_FILE.exists() else {}
    catalog = {}
    for m in model_resolver.installed_models() or []:
        hf = cache.get(m["id"])
        if hf and hf not in catalog:
            params = m["details"].get("parameter_size", "")
            try:  # QLoRA 4-bit rule of thumb: ~0.6 GB per B params + ~3 GB overhead
                gb = round(float(params.rstrip("BM")) * (0.6 if params.endswith("B") else 0.0006) + 3)
                est = f", ~{gb} GB VRAM" + (" ⚠ likely too big for 24 GB" if gb > 23 else "")
            except ValueError:
                est = ""
            catalog[hf] = f"{hf.split('/')[-1]} — matches installed {m['id']}{est}"
    for hf in _hf_downloaded_models():
        catalog.setdefault(hf, f"{hf.split('/')[-1]} — already downloaded")
    for hf, label in FINETUNE_MODELS.items():
        catalog.setdefault(hf, label)
    return catalog


@app.get("/api/finetune")
def api_finetune_info():
    info = _finetune_status.copy() if _finetune_status else {"status": "idle"}

    # Check if process still running
    if info.get("status") == "running" and info.get("pid"):
        try:
            proc = psutil.Process(info["pid"])
            if not proc.is_running():
                info["status"] = "done"
        except psutil.NoSuchProcess:
            info["status"] = "done"

    # Read log
    if info.get("log_file"):
        log_path = Path(info["log_file"])
        if log_path.exists():
            info["log"] = log_path.read_text()[-5000:]

    # List existing adapters
    adapters = []
    for d in FINETUNE_OUTPUT.glob("*/lora_adapter"):
        info_file = d.parent / "training_info.json"
        if info_file.exists():
            adapters.append(json.loads(info_file.read_text()))
    info["adapters"] = adapters
    info["models"] = _finetune_catalog()

    return info


@app.post("/api/finetune/start")
async def api_finetune_start(req: Request):
    import uuid

    if _finetune_status.get("status") == "running":
        return {"ok": False, "message": "Training is already running"}

    try:
        request = await req.json()
    except Exception:
        return {"ok": False, "message": "Invalid request"}

    task_id = str(uuid.uuid4())[:8]
    log_file = FINETUNE_OUTPUT / f"train_{task_id}.log"

    config = {
        "model": request.get("model", "unsloth/Qwen2.5-7B-Instruct"),
        "dataset": request.get("dataset", ""),
        "output": str(FINETUNE_OUTPUT / f"run_{task_id}"),
        "rank": request.get("rank", 16),
        "alpha": request.get("alpha", 16),
        "epochs": request.get("epochs", 3),
        "batch": request.get("batch", 2),
        "lr": request.get("lr", 0.0002),
        "seq_len": request.get("seq_len", 2048),
    }

    config_file = FINETUNE_OUTPUT / f"config_{task_id}.json"
    config_file.write_text(json.dumps(config, ensure_ascii=False))

    cmd = f"source {AGENTS_VENV}/bin/activate && python3 -u {FINETUNE_SCRIPT} --config \"$(cat {config_file})\""

    proc = subprocess.Popen(
        ["bash", "-c", cmd],
        stdout=open(log_file, "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    _finetune_status.update({
        "status": "running",
        "task_id": task_id,
        "pid": proc.pid,
        "model": config["model"],
        "dataset": config["dataset"],
        "log_file": str(log_file),
        "started": time.time(),
    })

    return {"ok": True, "message": f"Training started: {config['model'].split('/')[-1]}"}


@app.post("/api/finetune/stop")
async def api_finetune_stop():
    if _finetune_status.get("status") != "running":
        return {"ok": False, "message": "Training is not running"}
    try:
        os.killpg(os.getpgid(_finetune_status["pid"]), signal.SIGTERM)
    except Exception:
        pass
    _finetune_status["status"] = "stopped"
    return {"ok": True, "message": "Training stopped"}


@app.post("/api/finetune/upload-dataset")
async def api_finetune_upload(file: UploadFile = File(...)):
    dest = FINETUNE_OUTPUT / f"datasets"
    dest.mkdir(exist_ok=True)
    filepath = dest / Path(file.filename).name
    with open(filepath, "wb") as f:
        content = await file.read()
        f.write(content)
    return {"ok": True, "path": str(filepath), "name": file.filename, "size": len(content)}


# ─── RAG Chat API ─────────────────────────────────────────────────

def _rag_tool_cmd(action: str, path: str, collection: str) -> list[str]:
    # argv list, no shell — paths/collection names with quotes can't break or inject
    return [f"{AGENTS_VENV}/bin/python3", "-u", str(AGENTS_DIR / "rag_tool.py"),
            action, "--path", path, "--collection", collection]


@app.post("/api/rag/index")
async def api_rag_index(req: Request):
    """Index a file or directory into RAG"""
    try:
        request = await req.json()
    except Exception:
        return {"ok": False, "message": "Invalid request"}

    path = request.get("path", "").strip()
    collection = request.get("collection", "default").strip()
    mode = request.get("mode", "file")  # file or dir

    if not path:
        return {"ok": False, "message": "Specify a path"}

    from pathlib import Path as P
    if not P(path).exists():
        return {"ok": False, "message": f"Path not found: {path}"}

    # Run indexing in background
    log_file = f"/tmp/rag_index_{int(time.time())}.log"
    subprocess.Popen(
        _rag_tool_cmd("index-dir" if mode == "dir" else "index-file", path, collection),
        stdout=open(log_file, "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    return {"ok": True, "message": f"Indexing started: {path} → {collection}", "log": log_file}


@app.post("/api/rag/upload-and-index")
async def api_rag_upload_index(file: UploadFile = File(...), collection: str = Form("default")):
    """Upload file and index into RAG"""
    dest = Path("/tmp/ai-panel-uploads")
    dest.mkdir(exist_ok=True)
    filepath = dest / Path(file.filename).name
    with open(filepath, "wb") as f:
        content = await file.read()
        f.write(content)

    # Index
    result = await asyncio.to_thread(
        subprocess.run, _rag_tool_cmd("index-file", str(filepath), collection),
        capture_output=True, text=True, timeout=120)

    return {
        "ok": True,
        "message": f"File {file.filename} indexed into '{collection}'",
        "output": result.stdout[-500:]
    }


@app.delete("/api/rag/collection/{name}")
def api_rag_delete_collection(name: str):
    """Delete a RAG collection"""
    try:
        req = urllib.request.Request(f"http://localhost:6333/collections/{name}", method="DELETE")
        urllib.request.urlopen(req, timeout=5)
        return {"ok": True, "message": f"Collection '{name}' deleted"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


# Embedding cache
_embed_cache: dict = {}

RERANK_URL = "http://localhost:7997/rerank"
RERANK_MODEL = "Qwen/Qwen3-Reranker-0.6B"


def _rerank(query: str, documents: list, top_n: int = 5):
    """Rerank documents via Qwen3-Reranker (Infinity, CPU).
    Returns a list of original indices ordered by relevance, or None on
    failure so the caller can fall back to the vector-search order."""
    if not documents:
        return []
    try:
        payload = json.dumps({
            "model": RERANK_MODEL, "query": query,
            "documents": documents, "top_n": top_n,
        }).encode("utf-8")
        r = urllib.request.Request(RERANK_URL, data=payload,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(r, timeout=30) as resp:
            data = json.loads(resp.read())
        results = data.get("results", [])
        # Infinity returns [{"index": i, "relevance_score": s}, ...] desc
        return [item["index"] for item in results if "index" in item][:top_n]
    except Exception:
        return None


@app.post("/api/rag/chat")
async def api_rag_chat(req: Request):
    """Ask a question using RAG — search documents + LLM answer"""
    try:
        request = await req.json()
    except Exception:
        return {"ok": False, "message": "Invalid request"}
    # Embedding + search + generation can take minutes — keep the event loop free
    return await asyncio.to_thread(_rag_chat, request)


def _rag_chat(request: dict) -> dict:
    query = request.get("query", "").strip()
    collection = request.get("collection", "estonian_laws")
    model = resolve_model(request.get("model") or "qwen3.6:35b-a3b")
    language = request.get("language", "english")

    if not query:
        return {"ok": False, "message": "Enter a question"}

    import re as _re

    # Step 1: Embedding with cache
    cache_key = query[:200]
    if cache_key in _embed_cache:
        vec = _embed_cache[cache_key]
    else:
        try:
            payload = json.dumps({"model": "bge-m3", "input": query}).encode('utf-8')
            r = urllib.request.Request("http://localhost:11434/api/embed",
                data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(r, timeout=30) as resp:
                vec = json.loads(resp.read())["embeddings"][0]
            _embed_cache[cache_key] = vec
            # Keep cache under 500 entries
            if len(_embed_cache) > 500:
                oldest = list(_embed_cache.keys())[0]
                del _embed_cache[oldest]
        except Exception as e:
            return {"ok": False, "message": f"Embedding error: {e}"}

    # Step 2: Search Qdrant — support multi-collection ("all" = search all)
    collections_to_search = [collection]
    if collection == "__all__":
        try:
            r = urllib.request.Request("http://localhost:6333/collections")
            with urllib.request.urlopen(r, timeout=5) as resp:
                cdata = json.loads(resp.read())
                collections_to_search = [c["name"] for c in cdata.get("result", {}).get("collections", [])]
        except Exception:
            pass

    RETRIEVE_K = 20   # over-retrieve candidates for reranking
    FINAL_K = 5       # documents actually fed to the LLM
    contexts = []
    sources = []
    try:
        for col in collections_to_search:
            payload = json.dumps({"vector": vec, "limit": RETRIEVE_K, "with_payload": True}).encode('utf-8')
            r = urllib.request.Request(f"http://localhost:6333/collections/{col}/points/search",
                data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(r, timeout=10) as resp:
                data = json.loads(resp.read())
            for p in data.get("result", []):
                contexts.append(p["payload"]["text"])
                sources.append({"source": f"[{col}] {p['payload']['source']}", "score": round(p["score"], 4)})
        # Vector pre-ranking: keep the top RETRIEVE_K candidates across collections
        paired = sorted(zip(sources, contexts), key=lambda x: -x[0]["score"])[:RETRIEVE_K]
        sources = [p[0] for p in paired]
        contexts = [p[1] for p in paired]
    except Exception as e:
        return {"ok": False, "message": f"Search error: {e}"}

    if not contexts:
        return {"ok": True, "answer": "No relevant documents found.", "sources": []}

    # Rerank candidates with Qwen3-Reranker; fall back to vector order if unavailable
    reranked = False
    order = _rerank(query, contexts, top_n=FINAL_K)
    if order is not None:
        reranked = True
        sources = [sources[i] for i in order]
        contexts = [contexts[i] for i in order]
    else:
        sources = sources[:FINAL_K]
        contexts = contexts[:FINAL_K]

    # Step 3: LLM with context
    context_text = "\n\n---\n\n".join(contexts)
    prompt = f"""Answer the question ONLY based on the documents below.
If the documents do not contain the answer — say so honestly. Cite sources.
Answer in {language}. Be concise and to the point.
/no_think

DOCUMENTS:
{context_text}

QUESTION: {query}

ANSWER:"""

    _t0 = time.monotonic()
    try:
        payload = json.dumps({
            "model": model, "prompt": prompt, "stream": False, "think": False,
            "options": {"num_predict": 2000, "temperature": 0.3}
        }).encode('utf-8')
        r = urllib.request.Request("http://localhost:11434/api/generate",
            data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(r, timeout=180) as resp:
            _resp = json.loads(resp.read())
        answer = _resp.get("response", "")
        answer = _re.sub(r'<think>.*?</think>', '', answer, flags=_re.DOTALL).strip()
        metrics.log_ollama("rag", model, _resp, _t0, ok=True, extra=collection)
    except Exception as e:
        metrics.log_call("rag", model, (time.monotonic() - _t0) * 1000, ok=False, extra=str(e)[:80])
        return {"ok": False, "message": f"LLM error: {e}"}

    return {"ok": True, "answer": answer, "sources": sources, "reranked": reranked}



# ─── Observability / metrics ─────────────────────────────────────
@app.get("/api/metrics/summary")
async def api_metrics_summary(hours: int = 24):
    return metrics.summary(hours)


@app.get("/api/metrics/timeseries")
async def api_metrics_timeseries(hours: int = 24):
    return metrics.timeseries(hours)


@app.get("/api/metrics/services")
async def api_metrics_services(hours: int = 24):
    return metrics.services(hours)


@app.get("/api/metrics/recent")
async def api_metrics_recent(limit: int = 50):
    return {"calls": metrics.recent(limit)}


# ─── SMM AI Department (modularized) ─────────────────────────────
from smm import register_smm_routes
register_smm_routes(app, load_modules, start_module, stop_module)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    def snapshot() -> dict:
        module_statuses = []
        for m in load_modules():
            s = get_module_status(m)
            module_statuses.append({
                "name": m["name"],
                "_file": m["_file"],
                "status": s["status"],
                "vram_mb": s["vram_mb"],
            })
        return {"gpu": get_gpu_info(), "system": get_system_info(), "modules": module_statuses}

    try:
        while True:
            # Blocking probes (nvidia-smi, docker, cpu_percent) run off the event loop
            await websocket.send_json(await asyncio.to_thread(snapshot))
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        pass


@app.post("/api/restart")
async def api_restart():
    """Graceful restart: re-exec the server process."""
    import sys
    os.execv(sys.executable, [sys.executable] + sys.argv)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
