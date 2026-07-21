"""Lightweight observability for the NeuralForge panel.

Records two things into a standalone SQLite DB (metrics.db):
  * llm_calls   — one row per LLM request (model, latency, tokens, source)
  * gpu_samples — periodic GPU/VRAM/loaded-model snapshots
  * svc_samples — periodic per-service up/down snapshots

Everything is best-effort: logging never raises into the caller and the
background sampler is a daemon thread, so this module can never take the
panel down.
"""
import json
import socket
import sqlite3
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

DB_PATH = str(Path(__file__).parent / "metrics.db")
_write_lock = threading.Lock()

# name -> port; used only for up/down sampling
SERVICE_PORTS = {
    "ollama": 11434,
    "open-webui": 8080,
    "perplexica": 3000,
    "qdrant": 6333,
    "searxng": 8888,
    "reranker": 7997,
    "comfyui": 8188,
    "ace-step": 7880,
    "hunyuan3d": 7870,
    "qwen3-tts": 7890,
    "wan2gp": 7860,
    "whisper": 7895,
    "panel": 9000,
}


def _conn():
    c = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
    c.execute("PRAGMA journal_mode=WAL")
    return c


def init_db():
    with _write_lock, _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS llm_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL, source TEXT, model TEXT,
            latency_ms INTEGER, prompt_tokens INTEGER, eval_tokens INTEGER,
            ok INTEGER, extra TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS gpu_samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL, gpu_util INTEGER, vram_used INTEGER, vram_total INTEGER,
            temp INTEGER, loaded_model TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS svc_samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL, name TEXT, up INTEGER)""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_calls_ts ON llm_calls(ts)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_gpu_ts ON gpu_samples(ts)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_svc_ts ON svc_samples(ts)")


# ── logging ────────────────────────────────────────────────────────────
def log_call(source, model, latency_ms, prompt_tokens=0, eval_tokens=0,
             ok=True, extra=""):
    """Record a single LLM call. Never raises."""
    try:
        with _write_lock, _conn() as c:
            c.execute(
                "INSERT INTO llm_calls(ts,source,model,latency_ms,prompt_tokens,eval_tokens,ok,extra)"
                " VALUES(?,?,?,?,?,?,?,?)",
                (time.time(), source, model or "?", int(latency_ms or 0),
                 int(prompt_tokens or 0), int(eval_tokens or 0),
                 1 if ok else 0, str(extra)[:200]))
    except Exception:
        pass


def log_ollama(source, model, resp, started_at, ok=True, extra=""):
    """Convenience: pull token/latency stats straight out of an Ollama
    /api/generate|chat JSON response and log them.

    `resp` is the parsed dict; `started_at` is a time.monotonic() taken
    right before the request."""
    latency_ms = (time.monotonic() - started_at) * 1000 if started_at else 0
    p = e = 0
    try:
        p = resp.get("prompt_eval_count", 0)
        e = resp.get("eval_count", 0)
        # Ollama reports total_duration in ns — prefer it when present
        if resp.get("total_duration"):
            latency_ms = resp["total_duration"] / 1e6
    except Exception:
        pass
    log_call(source, model, latency_ms, p, e, ok, extra)


# ── sampling ───────────────────────────────────────────────────────────
def _gpu_stats():
    try:
        out = subprocess.check_output(
            ["nvidia-smi",
             "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
             "--format=csv,noheader,nounits"],
            timeout=5).decode().strip().splitlines()[0]
        util, used, total, temp = [int(x.strip()) for x in out.split(",")]
        return util, used, total, temp
    except Exception:
        return None


def _loaded_model():
    try:
        with urllib.request.urlopen("http://localhost:11434/api/ps", timeout=3) as r:
            models = json.loads(r.read()).get("models", [])
            return models[0]["name"] if models else ""
    except Exception:
        return ""


def _port_up(port):
    try:
        with socket.create_connection(("localhost", port), timeout=1):
            return True
    except Exception:
        return False


def sample_once():
    ts = time.time()
    g = _gpu_stats()
    lm = _loaded_model()
    try:
        with _write_lock, _conn() as c:
            if g:
                c.execute("INSERT INTO gpu_samples(ts,gpu_util,vram_used,vram_total,temp,loaded_model)"
                          " VALUES(?,?,?,?,?,?)", (ts, g[0], g[1], g[2], g[3], lm))
            for name, port in SERVICE_PORTS.items():
                c.execute("INSERT INTO svc_samples(ts,name,up) VALUES(?,?,?)",
                          (ts, name, 1 if _port_up(port) else 0))
    except Exception:
        pass


def _sampler_loop(interval):
    while True:
        sample_once()
        _prune()
        time.sleep(interval)


def _prune(days=14):
    """Keep the DB small — drop samples/calls older than `days`."""
    try:
        cutoff = time.time() - days * 86400
        with _write_lock, _conn() as c:
            for t in ("llm_calls", "gpu_samples", "svc_samples"):
                c.execute(f"DELETE FROM {t} WHERE ts < ?", (cutoff,))
    except Exception:
        pass


SAMPLER_NAME = "nf-metrics-sampler"


def start_sampler(interval=60):
    """Start the background sampler exactly once per process. The guard keys
    on a live thread name (not a module global) so it survives module reloads
    and repeated calls — no duplicate sampler threads can accumulate."""
    init_db()
    for t in threading.enumerate():
        if t.name == SAMPLER_NAME and t.is_alive():
            return
    threading.Thread(target=_sampler_loop, args=(interval,),
                     name=SAMPLER_NAME, daemon=True).start()


# ── queries (for the API) ──────────────────────────────────────────────
def summary(hours=24):
    since = time.time() - hours * 3600
    with _conn() as c:
        rows = c.execute(
            "SELECT model, COUNT(*), AVG(latency_ms), SUM(prompt_tokens), SUM(eval_tokens),"
            " SUM(ok) FROM llm_calls WHERE ts>=? GROUP BY model ORDER BY COUNT(*) DESC",
            (since,)).fetchall()
        by_model = [{
            "model": r[0], "calls": r[1], "avg_latency_ms": round(r[2] or 0),
            "prompt_tokens": r[3] or 0, "eval_tokens": r[4] or 0,
            "success_rate": round((r[5] or 0) / r[1] * 100) if r[1] else 0,
        } for r in rows]
        by_source = c.execute(
            "SELECT source, COUNT(*) FROM llm_calls WHERE ts>=? GROUP BY source ORDER BY COUNT(*) DESC",
            (since,)).fetchall()
        total = sum(m["calls"] for m in by_model)
        tok = sum(m["eval_tokens"] for m in by_model)
    return {"hours": hours, "total_calls": total, "total_eval_tokens": tok,
            "by_model": by_model,
            "by_source": [{"source": s, "calls": n} for s, n in by_source]}


def timeseries(hours=24, buckets=120):
    since = time.time() - hours * 3600
    with _conn() as c:
        rows = c.execute(
            "SELECT ts,gpu_util,vram_used,vram_total,temp,loaded_model"
            " FROM gpu_samples WHERE ts>=? ORDER BY ts", (since,)).fetchall()
    # thin to at most `buckets` points for the chart
    step = max(1, len(rows) // buckets)
    pts = [{"ts": int(r[0]), "gpu": r[1], "vram_used": r[2], "vram_total": r[3],
            "temp": r[4], "model": r[5]} for r in rows[::step]]
    return {"hours": hours, "points": pts}


def services(hours=24):
    since = time.time() - hours * 3600
    with _conn() as c:
        rows = c.execute(
            "SELECT name, AVG(up)*100, MAX(ts) FROM svc_samples WHERE ts>=? GROUP BY name",
            (since,)).fetchall()
        latest = {}
        for name in SERVICE_PORTS:
            r = c.execute("SELECT up FROM svc_samples WHERE name=? ORDER BY ts DESC LIMIT 1",
                          (name,)).fetchone()
            latest[name] = bool(r[0]) if r else False
    return {"hours": hours, "services": [
        {"name": n, "uptime_pct": round(u or 0, 1), "up_now": latest.get(n, False)}
        for n, u, _ in sorted(rows)]}


def recent(limit=50):
    with _conn() as c:
        rows = c.execute(
            "SELECT ts,source,model,latency_ms,prompt_tokens,eval_tokens,ok"
            " FROM llm_calls ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
    return [{"ts": int(r[0]), "source": r[1], "model": r[2], "latency_ms": r[3],
             "prompt_tokens": r[4], "eval_tokens": r[5], "ok": bool(r[6])} for r in rows]
