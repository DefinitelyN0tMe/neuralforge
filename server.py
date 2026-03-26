#!/usr/bin/env python3
"""
NeuralForge — Backend
Unified dashboard for managing local AI services
"""

import asyncio
import json
import os
import signal
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Optional

import docker
import psutil
import yaml
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="NeuralForge")
app.mount("/static", StaticFiles(directory="static"), name="static")

MODULES_DIR = Path("modules")
LOG_DIR = Path("/tmp/ai-panel-logs")
LOG_DIR.mkdir(exist_ok=True)



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

def get_gpu_info() -> dict:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.free,memory.total,temperature.gpu,power.draw,utilization.gpu,name",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        parts = [x.strip() for x in result.stdout.strip().split(",")]
        return {
            "mem_used": int(parts[0]),
            "mem_free": int(parts[1]),
            "mem_total": int(parts[2]),
            "temp": int(parts[3]),
            "power": float(parts[4]),
            "util": int(parts[5]),
            "name": parts[6],
        }
    except Exception:
        return {"mem_used": 0, "mem_free": 0, "mem_total": 0, "temp": 0, "power": 0, "util": 0, "name": "N/A"}


def get_gpu_processes() -> list[dict]:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        procs = []
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                parts = [x.strip() for x in line.split(",")]
                procs.append({"pid": int(parts[0]), "name": parts[1], "vram_mb": int(parts[2])})
        return procs
    except Exception:
        return []


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
        return {"ok": True, "message": f"{module['name']} запущен"}

    elif mtype == "docker":
        try:
            client = docker.from_env()
            container = client.containers.get(module["container_name"])
            container.start()
            return {"ok": True, "message": f"{module['name']} запущен"}
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

        log_fh = open(log_file, "w")
        subprocess.Popen(
            ["bash", "-c", full_cmd],
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            cwd=work_dir,
        )
        log_fh.close()
        return {"ok": True, "message": f"{module['name']} запускается...", "log": str(log_file)}

    return {"ok": False, "message": "Unknown module type"}


def stop_module(module: dict) -> dict:
    mtype = module.get("type", "")

    if mtype == "systemd":
        subprocess.run(["sudo", "systemctl", "stop", module["service_name"]], timeout=10)
        return {"ok": True, "message": f"{module['name']} остановлен"}

    elif mtype == "docker":
        try:
            client = docker.from_env()
            container = client.containers.get(module["container_name"])
            container.stop(timeout=10)
            return {"ok": True, "message": f"{module['name']} остановлен"}
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
        return {"ok": True, "message": f"{module['name']} остановлен"}

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
async def api_stop_all_heavy():
    """Stop all GPU-heavy services to free VRAM"""
    stopped = []
    modules = load_modules()
    for m in modules:
        if m.get("exclusive_group") == "heavy_gpu" or (m.get("type") == "process" and m.get("vram_estimate", "0") != "0 GB"):
            s = get_module_status(m)
            if s["status"] in ("running", "starting"):
                stop_module(m)
                stopped.append(m["name"])
    return {"ok": True, "message": f"Остановлены: {', '.join(stopped)}" if stopped else "Нечего останавливать"}


@app.post("/api/actions/start-basics")
async def api_start_basics():
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
    return {"ok": True, "message": f"Запущены: {', '.join(started)}" if started else "Всё уже работает"}


@app.post("/api/actions/free-vram")
async def api_free_vram():
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
        return {"ok": True, "message": f"Выгружены: {', '.join(unloaded)}" if unloaded else "VRAM уже свободна"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


# ─── Telegram Bot API ──────────────────────────────────────────────

TG_CONFIG = Path("/home/definitelynotme/Desktop/ai-panel/telegram_config.json")
TG_SESSIONS_DIR = Path("/home/definitelynotme/Desktop/ai-panel/telegram_sessions")
TG_BOT_SCRIPT = "/home/definitelynotme/Desktop/ai-panel/telegram_bot.py"
TG_BOT_LOG = Path("/tmp/telegram_bot.log")


@app.get("/api/telegram")
async def api_telegram():
    config = json.loads(TG_CONFIG.read_text()) if TG_CONFIG.exists() else {}
    running = False
    try:
        result = subprocess.run(["pgrep", "-f", "telegram_bot.py"], capture_output=True, text=True, timeout=3)
        running = result.returncode == 0
    except Exception:
        pass
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
    return {
        "config": config,
        "running": running,
        "sessions": sessions,
        "personas": config.get("personas", {}),
    }


@app.get("/api/telegram/session/{session_id}")
async def api_telegram_session(session_id: str):
    f = TG_SESSIONS_DIR / f"session_{session_id}.json"
    if not f.exists():
        return {"ok": False, "error": "Сессия не найдена"}
    data = json.loads(f.read_text())
    return {"ok": True, "session": data}


@app.delete("/api/telegram/session/{session_id}")
async def api_telegram_delete_session(session_id: str):
    f = TG_SESSIONS_DIR / f"session_{session_id}.json"
    if f.exists():
        f.unlink()
    return {"ok": True}


@app.post("/api/telegram/config")
async def api_telegram_config(req: Request):
    try:
        new_config = await req.json()
    except Exception:
        return {"ok": False}
    # Merge with existing
    config = json.loads(TG_CONFIG.read_text()) if TG_CONFIG.exists() else {}
    config.update(new_config)
    TG_CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2))
    return {"ok": True, "message": "Настройки сохранены"}


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
        return {"ok": False, "error": "Имя и промпт обязательны"}
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
    return {"ok": True, "id": pid, "message": f"Персона «{name}» создана"}


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
        return {"ok": False, "error": "Персона не найдена"}
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
    return {"ok": True, "message": f"Персона «{p['name']}» обновлена"}


@app.delete("/api/telegram/personas/{persona_id}")
async def api_telegram_persona_delete(persona_id: str):
    """Delete a custom persona (defaults cannot be deleted)"""
    if persona_id in DEFAULT_PERSONA_IDS:
        return {"ok": False, "error": "Дефолтные персоны нельзя удалить, только редактировать"}
    config = json.loads(TG_CONFIG.read_text()) if TG_CONFIG.exists() else {}
    personas = config.get("personas", {})
    if persona_id not in personas:
        return {"ok": False, "error": "Персона не найдена"}
    name = personas[persona_id].get("name", persona_id)
    del personas[persona_id]
    if config.get("active_persona") == persona_id:
        config["active_persona"] = "philosopher"
    config["personas"] = personas
    TG_CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2))
    return {"ok": True, "message": f"Персона «{name}» удалена"}


@app.post("/api/telegram/start")
async def api_telegram_start():
    try:
        result = subprocess.run(["pgrep", "-f", "telegram_bot.py"], capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            return {"ok": False, "message": "Бот уже запущен"}
    except Exception:
        pass
    # Ensure enabled in config
    config = json.loads(TG_CONFIG.read_text()) if TG_CONFIG.exists() else {}
    config["enabled"] = True
    TG_CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2))
    # Start bot
    venv = "/home/definitelynotme/Desktop/ai-panel/venv"
    tg_log_fh = open(TG_BOT_LOG, "w")
    subprocess.Popen(
        ["bash", "-c", f"source {venv}/bin/activate && python3 -u {TG_BOT_SCRIPT}"],
        stdout=tg_log_fh,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    tg_log_fh.close()
    return {"ok": True, "message": "Telegram бот запущен"}


@app.post("/api/telegram/stop")
async def api_telegram_stop():
    config = json.loads(TG_CONFIG.read_text()) if TG_CONFIG.exists() else {}
    config["enabled"] = False
    TG_CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2))
    subprocess.run(["pkill", "-f", "telegram_bot.py"], capture_output=True, timeout=5)
    return {"ok": True, "message": "Telegram бот остановлен"}


@app.delete("/api/telegram/sessions")
async def api_telegram_delete_all_sessions():
    """Delete all session files"""
    count = 0
    if TG_SESSIONS_DIR.exists():
        for f in TG_SESSIONS_DIR.glob("session_*.json"):
            f.unlink()
            count += 1
    return {"ok": True, "message": f"Удалено сессий: {count}"}


@app.delete("/api/telegram/messages")
async def api_telegram_clear_messages():
    """Legacy endpoint — kept for compat"""
    return {"ok": True}


@app.get("/api/health")
async def api_health():
    """Health monitoring — alerts for GPU temp, disk, RAM"""
    alerts = []
    gpu = get_gpu_info()
    sys_info = get_system_info()

    if gpu["temp"] > 85:
        alerts.append({"level": "critical", "msg": f"GPU перегрев: {gpu['temp']}C (>85)"})
    elif gpu["temp"] > 75:
        alerts.append({"level": "warning", "msg": f"GPU горячий: {gpu['temp']}C (>75)"})

    vram_pct = gpu["mem_used"] / gpu["mem_total"] * 100 if gpu["mem_total"] else 0
    if vram_pct > 95:
        alerts.append({"level": "critical", "msg": f"VRAM почти полна: {vram_pct:.0f}%"})

    if sys_info["ram_available_gb"] < 5:
        alerts.append({"level": "critical", "msg": f"Мало RAM: {sys_info['ram_available_gb']}GB"})

    if sys_info.get("disk_free_gb", 999) < 50:
        alerts.append({"level": "critical", "msg": f"Мало места: {sys_info['disk_free_gb']}GB"})

    for name, port in [("Ollama", 11434), ("Qdrant", 6333)]:
        if not check_port(port):
            alerts.append({"level": "critical", "msg": f"{name} не отвечает :{port}"})

    return {"alerts": alerts, "healthy": len([a for a in alerts if a["level"] == "critical"]) == 0}


@app.get("/api/status")
async def api_status():
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
async def api_start(filename: str):
    modules = load_modules()
    module = next((m for m in modules if m["_file"] == filename), None)
    if not module:
        return {"ok": False, "message": "Module not found"}

    # Check if already running
    current = get_module_status(module)
    if current["status"] in ("running", "starting"):
        return {"ok": False, "message": f"{module['name']} уже запущен"}

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
async def api_stop(filename: str):
    modules = load_modules()
    module = next((m for m in modules if m["_file"] == filename), None)
    if not module:
        return {"ok": False, "message": "Module not found"}
    return stop_module(module)


@app.get("/api/module/{filename}/log")
async def api_log(filename: str):
    log_file = LOG_DIR / filename.replace(".yaml", ".log")
    if log_file.exists():
        lines = log_file.read_text().split("\n")[-50:]
        return {"lines": lines}
    return {"lines": []}


# ─── Agents API ───────────────────────────────────────────────────

AGENTS_DIR = Path("/home/definitelynotme/Desktop/Claude_Test/agents")
AGENTS_VENV = "/home/definitelynotme/Desktop/Claude_Test/.venv"
AGENT_LOGS_DIR = Path("/tmp/ai-panel-agents")
AGENT_LOGS_DIR.mkdir(exist_ok=True)

# Track running agents
_running_agents: dict[str, dict] = {}


UNIVERSAL_AGENT = str(AGENTS_DIR / "universal.py")
TEAM_AGENT = str(AGENTS_DIR / "team.py")
ORCHESTRATOR_AGENT = str(AGENTS_DIR / "orchestrator.py")

ROLE_PRESETS = {
    "researcher": {"name": "Исследователь", "icon": "🔍", "desc": "Ищет и анализирует информацию"},
    "coder": {"name": "Программист", "icon": "💻", "desc": "Пишет, тестирует и отлаживает код"},
    "analyst": {"name": "Аналитик данных", "icon": "📊", "desc": "Анализирует данные, строит выводы"},
    "writer": {"name": "Контент-менеджер", "icon": "✍️", "desc": "Пишет тексты, статьи, посты"},
    "summarizer": {"name": "Суммаризатор", "icon": "📋", "desc": "Кратко пересказывает содержание"},
    "critic": {"name": "Критик-редактор", "icon": "🔎", "desc": "Проверяет факты, улучшает результат"},
    "translator": {"name": "Переводчик", "icon": "🔄", "desc": "RU, EN, ET, DE, FR, ES + ещё 5 языков"},
    "email_writer": {"name": "Email-ассистент", "icon": "📧", "desc": "Пишет письма в нужном стиле"},
    "tester": {"name": "Тестировщик", "icon": "🧪", "desc": "Пишет тесты, находит баги"},
    "trade_analyst": {"name": "Трейд-аналитик", "icon": "📈", "desc": "Анализирует рынки и тренды"},
    "tutor": {"name": "Репетитор", "icon": "🎓", "desc": "Объясняет сложное простым языком"},
    "security_auditor": {"name": "Секьюрити-аудитор", "icon": "🛡️", "desc": "Находит уязвимости в коде"},
    "custom": {"name": "Свой агент", "icon": "🛠️", "desc": "Полная настройка роли и инструментов"},
}

AVAILABLE_TOOLS = {
    "web_search": {"name": "Поиск в интернете", "icon": "🌐"},
    "read_url": {"name": "Чтение URL", "icon": "📄"},
    "run_python": {"name": "Python код", "icon": "🐍"},
    "read_file": {"name": "Чтение файлов", "icon": "📁"},
    "write_file": {"name": "Запись файлов", "icon": "💾"},
    "analyze_file": {"name": "Анализ файлов", "icon": "📊"},
    "analyze_image": {"name": "Анализ изображений", "icon": "🖼️"},
    "rag_search": {"name": "RAG поиск (документы)", "icon": "📚"},
    "deep_scrape": {"name": "Глубокий скрапинг (несколько URL)", "icon": "🕸️"},
}

AVAILABLE_MODELS = {
    "nemotron-3-nano:30b": "Nemotron 3 Nano 30B (NVIDIA, 1M контекст)",
    "qwen3.5:35b-a3b": "Qwen 3.5 35B-A3B (112 tok/s, MoE)",
    "qwen3.5:27b": "Qwen 3.5 27B (основная рабочая)",
    "qwen3.5:9b": "Qwen 3.5 9B (лёгкий, 6.6GB)",
    "gemma3:27b": "Gemma 3 27B (140 языков, multimodal)",
    "deepseek-r1:32b": "DeepSeek-R1 32B (рассуждения)",
    "deepseek-r1:14b": "DeepSeek-R1 14B (reasoning, лёгкий)",
    "phi4-reasoning:14b": "Phi-4 Reasoning 14B (математика/логика)",
    "qwen2.5-coder:32b": "Qwen 2.5 Coder 32B (код, 92.7% HumanEval)",
    "qwen3-vl:8b": "Qwen3-VL 8B (vision, видео, GUI)",
    "minicpm-v:8b": "MiniCPM-V 8B (vision, компактный)",
    "mistral-small:24b": "Mistral Small 24B (универсал)",
    "phi4:14b": "Phi 4 14B (компактный)",
    "command-r:35b": "Command R 35B (RAG)",
    "llama3.1:70b": "Llama 3.1 70B (макс. качество, CPU offload)",
}


def load_agents() -> list[dict]:
    return [{"id": "constructor", "name": "Конструктор агентов", "type": "constructor"}]


@app.get("/api/agents")
async def api_agents():
    info = _running_agents.get("constructor")
    status = info["status"] if info else "idle"
    return {
        "roles": ROLE_PRESETS,
        "tools": AVAILABLE_TOOLS,
        "models": AVAILABLE_MODELS,
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
        return {"ok": False, "message": "Агент уже выполняет задачу"}

    task_text = request.get("task", "").strip()
    if not task_text:
        return {"ok": False, "message": "Введите задачу"}

    role_id = request.get("role", "researcher")
    model_id = request.get("model", "qwen3.5:35b-a3b")
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

    return {"ok": True, "task_id": task_id, "message": f"{role_name} запущен: {task_text[:80]}"}


UPLOAD_DIR = Path("/tmp/ai-panel-uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@app.post("/api/agents/upload")
async def api_upload_file(file: UploadFile = File(...)):
    """Upload file for agent analysis"""
    dest = UPLOAD_DIR / file.filename
    with open(dest, "wb") as f:
        content = await file.read()
        f.write(content)
    return {"ok": True, "path": str(dest), "name": file.filename, "size": len(content)}


@app.get("/api/agents/pdf/{filename}")
async def api_get_export(filename: str):
    """Download exported PDF or MD"""
    file_path = AGENT_LOGS_DIR / filename
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
        return {"ok": False, "message": "Агент уже выполняет задачу"}

    task_text = request.get("task", "").strip()
    if not task_text:
        return {"ok": False, "message": "Введите задачу"}

    chain = request.get("chain", ["researcher", "writer"])
    model_override = request.get("model_override", None)
    attached_files = request.get("attached_files", [])

    if len(chain) < 2:
        return {"ok": False, "message": "Выберите минимум 2 роли для команды"}

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
        "role": f"Команда: {chain_names}",
        "model": model_override or "auto",
        "log_file": str(log_file),
        "started": time.time(),
    }

    asyncio.get_event_loop().create_task(asyncio.to_thread(proc.wait))

    return {"ok": True, "task_id": task_id, "message": f"Команда запущена: {chain_names}"}


@app.post("/api/agents/run-orchestrator")
async def api_run_orchestrator(req: Request):
    import uuid

    try:
        request = await req.json()
    except Exception:
        return {"ok": False, "message": "Invalid request"}

    if "constructor" in _running_agents and _running_agents["constructor"]["status"] == "running":
        return {"ok": False, "message": "Агент уже выполняет задачу"}

    task_text = request.get("task", "").strip()
    if not task_text:
        return {"ok": False, "message": "Введите задачу"}

    attached_files = request.get("attached_files", [])
    export_pdf = request.get("export_pdf", False)
    model_override = request.get("model_override", None)

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
        "role": "Оркестратор (авто-выбор)",
        "model": "auto",
        "log_file": str(log_file),
        "started": time.time(),
    }

    asyncio.get_event_loop().create_task(asyncio.to_thread(proc.wait))

    return {"ok": True, "task_id": task_id, "message": f"Оркестратор запущен: {task_text[:80]}"}


@app.get("/api/agents/status")
async def api_agent_status():
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
        return {"ok": False, "message": "Агент не запущен"}

    try:
        os.killpg(os.getpgid(info["pid"]), signal.SIGTERM)
    except Exception:
        try:
            os.kill(info["pid"], signal.SIGKILL)
        except Exception:
            pass

    info["status"] = "stopped"
    return {"ok": True, "message": "Агент остановлен"}


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
    log_file = AGENT_LOGS_DIR / filename
    if log_file.exists() and log_file.suffix == ".log":
        return {"content": log_file.read_text()}
    return {"content": "Файл не найден"}


@app.delete("/api/agents/history/{filename}")
async def api_agent_history_delete(filename: str):
    """Delete a specific agent log + all related files"""
    log_file = AGENT_LOGS_DIR / filename
    if not (log_file.exists() and log_file.suffix == ".log"):
        return {"ok": False, "message": "Файл не найден"}

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

    return {"ok": True, "message": f"Удалено: {', '.join(deleted)}"}


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
    return {"ok": True, "message": f"Удалено {count} файлов"}


# ─── Cleanup API ──────────────────────────────────────────────────

OUTPUT_DIRS = {
    "comfyui.yaml": {
        "name": "ComfyUI",
        "paths": ["/home/definitelynotme/Desktop/ComfyUI/output"],
        "extensions": [".png", ".jpg", ".jpeg", ".webp"],
    },
    "wan2gp.yaml": {
        "name": "Wan2GP",
        "paths": ["/home/definitelynotme/Desktop/Wan2GP/outputs"],
        "extensions": [".mp4", ".wav", ".mp3", ".png"],
    },
    "ace-step.yaml": {
        "name": "ACE-Step (музыка)",
        "paths": ["/home/definitelynotme/Desktop/ACE-Step-1.5/gradio_outputs"],
        "extensions": [".wav", ".mp3", ".flac", ".ogg", ".mid"],
    },
    "whisper-webui.yaml": {
        "name": "Whisper STT (субтитры + BGM)",
        "paths": ["/home/definitelynotme/Desktop/Whisper-WebUI/outputs"],
        "extensions": [".srt", ".vtt", ".txt", ".tsv", ".json", ".wav", ".mp3", ".flac"],
    },
    "gradio-cache": {
        "name": "Gradio кэш (TTS, 3D, и др.)",
        "paths": ["/tmp/gradio"],
        "extensions": None,
    },
}


@app.get("/api/storage")
async def api_storage():
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
async def api_cleanup(module_file: str):
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
    return {"ok": True, "message": f"{info['name']}: удалено {deleted} файлов, освобождено {freed_mb} МБ"}


# ─── RAG Indexing Status ──────────────────────────────────────────

@app.get("/api/rag/status")
async def api_rag_status():
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

FINETUNE_SCRIPT = "/home/definitelynotme/Desktop/Claude_Test/finetune/train_lora.py"
FINETUNE_OUTPUT = Path("/home/definitelynotme/Desktop/Claude_Test/finetune/outputs")
FINETUNE_OUTPUT.mkdir(parents=True, exist_ok=True)
_finetune_status: dict = {}

FINETUNE_MODELS = {
    # NVIDIA Nemotron
    "unsloth/NVIDIA-Nemotron-3-Nano-4B": "NVIDIA Nemotron 3 Nano 4B — молниеносный (5 ГБ, ~30мин)",
    "unsloth/NVIDIA-Nemotron-3-Nano-30B": "NVIDIA Nemotron 3 Nano 30B — мощный (22 ГБ, ~6-8ч)",
    # Qwen
    "unsloth/Qwen2.5-7B-Instruct": "Qwen 2.5 7B — быстрый (15 ГБ, ~1-2ч)",
    "unsloth/Qwen2.5-14B-Instruct": "Qwen 2.5 14B — средний (18 ГБ, ~3-4ч)",
    "unsloth/Qwen2.5-32B-Instruct": "Qwen 2.5 32B — впритык (22 ГБ, ~8-10ч)",
    "unsloth/Qwen2.5-Coder-7B-Instruct": "Qwen 2.5 Coder 7B — код (15 ГБ, ~1-2ч)",
    "unsloth/Qwen2.5-Coder-14B-Instruct": "Qwen 2.5 Coder 14B — код (18 ГБ, ~3-4ч)",
    # DeepSeek
    "unsloth/DeepSeek-R1-Distill-Qwen-7B": "DeepSeek-R1 Distill 7B — рассуждения (15 ГБ, ~1-2ч)",
    "unsloth/DeepSeek-R1-Distill-Qwen-14B": "DeepSeek-R1 Distill 14B — рассуждения (18 ГБ, ~3-4ч)",
    # Meta Llama
    "unsloth/Llama-3.1-8B-Instruct": "Llama 3.1 8B — универсал (15 ГБ, ~1-2ч)",
    # Mistral
    "unsloth/Mistral-Small-24B-Instruct-2501": "Mistral Small 24B — мощный (22 ГБ, ~6-8ч)",
    # Google
    "unsloth/gemma-3-12b-it": "Gemma 3 12B — Google multimodal (17 ГБ, ~3-4ч)",
    # Microsoft
    "unsloth/Phi-4": "Phi-4 14B — математика/наука (18 ГБ, ~3-4ч)",
    # Qwen 3.5
    "unsloth/Qwen3.5-9B": "Qwen 3.5 9B — новейший, vision (12 ГБ, ~2-3ч)",
    "unsloth/Qwen3.5-4B": "Qwen 3.5 4B — компактный (8 ГБ, ~1ч)",
    # OpenAI GPT-OSS
    "unsloth/gpt-oss-20b": "GPT-OSS 20B (OpenAI) — MoE 3.6B актив. (14 ГБ, ~2-3ч)",
}


@app.get("/api/finetune")
async def api_finetune_info():
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
    info["models"] = FINETUNE_MODELS

    return info


@app.post("/api/finetune/start")
async def api_finetune_start(req: Request):
    import uuid

    if _finetune_status.get("status") == "running":
        return {"ok": False, "message": "Обучение уже запущено"}

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

    return {"ok": True, "message": f"Обучение запущено: {config['model'].split('/')[-1]}"}


@app.post("/api/finetune/stop")
async def api_finetune_stop():
    if _finetune_status.get("status") != "running":
        return {"ok": False, "message": "Обучение не запущено"}
    try:
        os.killpg(os.getpgid(_finetune_status["pid"]), signal.SIGTERM)
    except Exception:
        pass
    _finetune_status["status"] = "stopped"
    return {"ok": True, "message": "Обучение остановлено"}


@app.post("/api/finetune/upload-dataset")
async def api_finetune_upload(file: UploadFile = File(...)):
    dest = FINETUNE_OUTPUT / f"datasets"
    dest.mkdir(exist_ok=True)
    filepath = dest / file.filename
    with open(filepath, "wb") as f:
        content = await file.read()
        f.write(content)
    return {"ok": True, "path": str(filepath), "name": file.filename, "size": len(content)}


# ─── RAG Chat API ─────────────────────────────────────────────────

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
        return {"ok": False, "message": "Укажите путь"}

    from pathlib import Path as P
    if not P(path).exists():
        return {"ok": False, "message": f"Путь не найден: {path}"}

    # Run indexing in background
    log_file = f"/tmp/rag_index_{int(time.time())}.log"
    if mode == "dir":
        cmd = f"source {AGENTS_VENV}/bin/activate && python3 -u {AGENTS_DIR / 'rag_tool.py'} index-dir --path '{path}' --collection '{collection}'"
    else:
        cmd = f"source {AGENTS_VENV}/bin/activate && python3 -u {AGENTS_DIR / 'rag_tool.py'} index-file --path '{path}' --collection '{collection}'"

    subprocess.Popen(
        ["bash", "-c", cmd],
        stdout=open(log_file, "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    return {"ok": True, "message": f"Индексация запущена: {path} → {collection}", "log": log_file}


@app.post("/api/rag/upload-and-index")
async def api_rag_upload_index(file: UploadFile = File(...), collection: str = Form("default")):
    """Upload file and index into RAG"""
    dest = Path("/tmp/ai-panel-uploads")
    dest.mkdir(exist_ok=True)
    filepath = dest / file.filename
    with open(filepath, "wb") as f:
        content = await file.read()
        f.write(content)

    # Index
    cmd = f"source {AGENTS_VENV}/bin/activate && python3 -u {AGENTS_DIR / 'rag_tool.py'} index-file --path '{filepath}' --collection '{collection}'"
    result = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=120)

    return {
        "ok": True,
        "message": f"Файл {file.filename} проиндексирован в '{collection}'",
        "output": result.stdout[-500:]
    }


@app.delete("/api/rag/collection/{name}")
async def api_rag_delete_collection(name: str):
    """Delete a RAG collection"""
    try:
        req = urllib.request.Request(f"http://localhost:6333/collections/{name}", method="DELETE")
        urllib.request.urlopen(req, timeout=5)
        return {"ok": True, "message": f"Коллекция '{name}' удалена"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


# Embedding cache
_embed_cache: dict = {}


@app.post("/api/rag/chat")
async def api_rag_chat(req: Request):
    """Ask a question using RAG — search documents + LLM answer"""
    try:
        request = await req.json()
    except Exception:
        return {"ok": False, "message": "Invalid request"}

    query = request.get("query", "").strip()
    collection = request.get("collection", "estonian_laws")
    model = request.get("model", "qwen3.5:35b-a3b")
    language = request.get("language", "русский")

    if not query:
        return {"ok": False, "message": "Введите вопрос"}

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

    contexts = []
    sources = []
    try:
        for col in collections_to_search:
            payload = json.dumps({"vector": vec, "limit": 5, "with_payload": True}).encode('utf-8')
            r = urllib.request.Request(f"http://localhost:6333/collections/{col}/points/search",
                data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(r, timeout=10) as resp:
                data = json.loads(resp.read())
            for p in data.get("result", []):
                contexts.append(p["payload"]["text"])
                sources.append({"source": f"[{col}] {p['payload']['source']}", "score": round(p["score"], 4)})
        # Sort by score, take top 5
        paired = sorted(zip(sources, contexts), key=lambda x: -x[0]["score"])[:5]
        sources = [p[0] for p in paired]
        contexts = [p[1] for p in paired]
    except Exception as e:
        return {"ok": False, "message": f"Search error: {e}"}

    if not contexts:
        return {"ok": True, "answer": "Не найдено релевантных документов.", "sources": []}

    # Step 3: LLM with context
    context_text = "\n\n---\n\n".join(contexts)
    prompt = f"""Ответь на вопрос ТОЛЬКО на основе документов ниже.
Если в документах нет ответа — скажи честно. Указывай источники.
Отвечай на {language} языке. Отвечай кратко и по делу.
/no_think

ДОКУМЕНТЫ:
{context_text}

ВОПРОС: {query}

ОТВЕТ:"""

    try:
        payload = json.dumps({
            "model": model, "prompt": prompt, "stream": False,
            "options": {"num_predict": 2000, "temperature": 0.3}
        }).encode('utf-8')
        r = urllib.request.Request("http://localhost:11434/api/generate",
            data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(r, timeout=180) as resp:
            answer = json.loads(resp.read()).get("response", "")
            answer = _re.sub(r'<think>.*?</think>', '', answer, flags=_re.DOTALL).strip()
    except Exception as e:
        return {"ok": False, "message": f"LLM error: {e}"}

    return {"ok": True, "answer": answer, "sources": sources}



# ─── SMM AI Department (modularized) ─────────────────────────────
from smm import register_smm_routes
register_smm_routes(app, load_modules, start_module, stop_module)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            gpu = get_gpu_info()
            system = get_system_info()
            modules = load_modules()
            module_statuses = []
            for m in modules:
                s = get_module_status(m)
                module_statuses.append({
                    "name": m["name"],
                    "_file": m["_file"],
                    "status": s["status"],
                    "vram_mb": s["vram_mb"],
                })

            await websocket.send_json({
                "gpu": gpu,
                "system": system,
                "modules": module_statuses,
            })
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
