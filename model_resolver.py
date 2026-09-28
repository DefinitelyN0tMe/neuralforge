"""Pick an installed Ollama model when the configured one is missing.

Every place that calls a model (panel, SMM, Telegram bot, agents) passes its
configured model through resolve_model(). If that model is installed it is
returned unchanged; if it was deleted, the closest installed model of the same
kind is used instead, so removing a model never breaks a feature.

Stdlib only — the agents import this from their own virtualenv.
"""
import json
import re
import threading
import time
import urllib.request

OLLAMA_URL = "http://localhost:11434"

# Fallback order per kind of task. Only consulted when the requested model is
# not installed; the first installed entry wins. Edit here to change priorities.
PREFERENCES = {
    "general": ["qwen3.6:35b-a3b", "qwen3.8:27b", "qwen3.6:27b", "gemma4:26b",
                "mistral-small:24b", "nemotron-3-nano:30b", "qwen3.5:9b"],
    "light": ["qwen3.5:9b", "qwen3.6:35b-a3b", "gemma4:26b", "qwen3.6:27b", "qwen3.8:27b"],
    "code": ["qwen3-coder:30b", "qwen3.6:35b-a3b", "qwen3.8:27b", "qwen3.6:27b"],
    "reasoning": ["deepseek-r1:32b", "deepseek-r1:14b", "phi4-reasoning:14b",
                  "qwen3.8:27b", "qwen3.6:27b", "qwen3.6:35b-a3b"],
    "vision": ["qwen3-vl:8b", "minicpm-v:8b", "qwen3.6:27b", "gemma4:26b",
               "qwen3.6:35b-a3b", "qwen3.8:27b", "qwen3.5:9b"],
}

_CACHE_TTL = 30
_lock = threading.Lock()
_cache: dict = {"ts": 0.0, "models": None}
_caps: dict = {}  # "name@digest" -> capabilities (fixed for a given digest)
_warned: set = set()  # substitutions already logged


def _post(path: str, body: dict, timeout: float = 5):
    req = urllib.request.Request(f"{OLLAMA_URL}{path}", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _capabilities(name: str, digest: str) -> list:
    key = f"{name}@{digest}"
    if key not in _caps:
        try:
            _caps[key] = _post("/api/show", {"model": name}).get("capabilities", [])
        except Exception:
            return []
    return _caps[key]


def installed_models(force: bool = False):
    """[{id, size, details, capabilities}] from Ollama, cached 30s.
    Returns None if Ollama can't be reached (callers then leave models untouched)."""
    with _lock:
        if not force and _cache["models"] is not None and time.monotonic() - _cache["ts"] < _CACHE_TTL:
            return _cache["models"]
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=5) as resp:
            tags = json.loads(resp.read()).get("models", [])
    except Exception:
        return _cache["models"]  # stale list (or None) beats failing
    models = [{
        "id": t.get("name", ""),
        "size": t.get("size", 0),
        "details": t.get("details", {}) or {},
        "capabilities": _capabilities(t.get("name", ""), t.get("digest", "")),
    } for t in tags]
    with _lock:
        _cache.update(ts=time.monotonic(), models=models)
    return models


def is_chat(m: dict) -> bool:
    # OCR models report "completion" but can only transcribe images
    return "completion" in m["capabilities"] and "ocr" not in m["id"]


def guess_kind(model: str) -> str:
    """Infer what a (possibly deleted) model was used for from its name."""
    name = (model or "").lower()
    if "coder" in name or "codestral" in name:
        return "code"
    if "-r1" in name or "reasoning" in name or re.search(r"\bqwq\b", name):
        return "reasoning"
    if re.search(r"-vl\b|-vl:|minicpm-v|llava|vision", name):
        return "vision"
    size = re.search(r":(\d+(?:\.\d+)?)b", name)
    if size and float(size.group(1)) <= 12:
        return "light"
    return "general"


def _normalize(model: str) -> str:
    return (model or "").removeprefix("ollama_chat/").removeprefix("ollama/").strip()


def resolve_model(model: str, kind: str = None, log=print) -> str:
    """Return `model` if installed, otherwise the best installed substitute.

    kind: general | light | code | reasoning | vision — defaults to a guess from
    the model name. If Ollama is unreachable the model is returned unchanged.
    """
    model = _normalize(model)
    models = installed_models()
    if not models:
        return model
    ids = {m["id"] for m in models}
    if model in ids:
        return model
    if f"{model}:latest" in ids:
        return f"{model}:latest"

    kind = kind or guess_kind(model)
    need_vision = kind == "vision"
    usable = [m for m in models if is_chat(m) and (not need_vision or "vision" in m["capabilities"])]
    usable_ids = {m["id"] for m in usable}
    chosen = next((p for p in PREFERENCES.get(kind, PREFERENCES["general"]) if p in usable_ids), None)
    if not chosen:
        chosen = next((p for p in PREFERENCES["general"] if p in usable_ids), None)
    if not chosen and usable:
        # Unknown lineup — largest usable model is the safest guess for quality
        chosen = max(usable, key=lambda m: m["size"])["id"]
    if not chosen:
        return model
    if log and model and (model, chosen) not in _warned:
        _warned.add((model, chosen))
        log(f"⚠️ Model {model} is not installed — using {chosen} ({kind})")
    return chosen
