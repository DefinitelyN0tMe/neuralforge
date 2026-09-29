#!/usr/bin/env python3
"""Keep Open WebUI and Perplexica in sync with the models installed in Ollama.

Checks every place those apps can reference an Ollama model and reports (or,
with --fix, repairs) references to models that are no longer installed.
Idempotent and stdlib only. Never prints credentials.

  python3 scripts/sync_app_models.py            # report only
  python3 scripts/sync_app_models.py --fix      # repair what is safe to repair
  python3 scripts/sync_app_models.py --json     # machine-readable (for the panel)

Exit code: 0 = all good (or everything fixed), 1 = problems remain,
2 = Ollama unreachable (nothing checked).

Perplexica (no auth): model lists come live from Ollama /api/tags, so removed
models vanish automatically. The only server-side references are custom models
a user added by hand under the Ollama provider; stale ones are deleted via
DELETE /api/providers/{id}/models. The chosen chat/embedding model lives in the
browser (localStorage); if it disappears Perplexica silently falls back to the
first model Ollama lists, which the report shows.

Open WebUI (needs an admin API key): checks default/pinned models, model order,
task model, RAG embedding model and workspace models whose base model is gone.
--fix replaces missing default/task models with the closest installed model
(via ../model_resolver.py) and drops missing ones from pinned/order lists.
Embedding model and workspace models are only reported: changing the embedding
model requires re-indexing, and workspace presets are user content.
Token: env OPENWEBUI_API_KEY, or the file ~/.config/ai-panel/openwebui_api_key
(chmod 600). Without it the Open WebUI part is limited to health/reachability.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
PERPLEXICA_URL = os.environ.get("PERPLEXICA_URL", "http://localhost:3000")
OPENWEBUI_URL = os.environ.get("OPENWEBUI_URL", "http://localhost:8080")
TOKEN_FILE = os.path.expanduser("~/.config/ai-panel/openwebui_api_key")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import model_resolver
except Exception:  # still usable standalone
    model_resolver = None


def http(method, url, body=None, token=None, timeout=15):
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return json.loads(raw) if raw else None


def ollama_models():
    tags = http("GET", f"{OLLAMA_URL}/api/tags")["models"]
    return [t["name"] for t in tags]


def is_installed(name, installed):
    name = (name or "").strip()
    return name in installed or f"{name}:latest" in installed


def substitute(name, installed, embedding=False):
    """Closest installed model for a missing one (None if nothing suitable)."""
    if embedding:
        for cand in ("bge-m3:latest", "nomic-embed-text:latest"):
            if cand in installed:
                return cand
        return None
    if model_resolver:
        sub = model_resolver.resolve_model(name, log=lambda *_: None)
        if sub in installed:
            return sub
    for cand in ("qwen3.6:35b-a3b", "qwen3.8:27b", "qwen3.6:27b", "gemma4:26b"):
        if cand in installed:
            return cand
    return None


# --------------------------------------------------------------------------- Perplexica

def check_perplexica(installed, fix):
    out = {"app": "perplexica", "reachable": False, "issues": [], "fixed": [], "info": []}
    try:
        providers = http("GET", f"{PERPLEXICA_URL}/api/providers")["providers"]
    except Exception as e:
        out["issues"].append(f"API unreachable: {type(e).__name__}")
        return out
    out["reachable"] = True
    try:
        cfg = http("GET", f"{PERPLEXICA_URL}/api/config")["values"]
        types = {p["id"]: p.get("type") for p in cfg.get("modelProviders", [])}
    except Exception:
        types = {}

    ollama_providers = [p for p in providers if types.get(p["id"]) == "ollama" or "ollama" in p["name"].lower()]
    if not ollama_providers:
        out["issues"].append("no Ollama provider configured (Settings -> Models -> add Ollama, "
                             "base URL http://host.docker.internal:11434)")
    for p in ollama_providers:
        chat = [m["key"] for m in p.get("chatModels", [])]
        if not chat:
            out["issues"].append(f"provider '{p['name']}' lists no models (Ollama unreachable from the container?)")
            continue
        # Live models always match /api/tags; anything else is a stale custom entry.
        for kind, field in (("chat", "chatModels"), ("embedding", "embeddingModels")):
            for m in p.get(field, []):
                if is_installed(m["key"], installed):
                    continue
                msg = f"provider '{p['name']}': custom {kind} model '{m['key']}' is not installed"
                if fix:
                    try:
                        http("DELETE", f"{PERPLEXICA_URL}/api/providers/{p['id']}/models",
                             {"type": kind, "key": m["key"]})
                        out["fixed"].append(msg + " -> removed")
                        continue
                    except Exception as e:
                        msg += f" (remove failed: {type(e).__name__})"
                out["issues"].append(msg)
        out["info"].append(f"provider '{p['name']}' ({p['id']}): {len(chat)} chat models; "
                           f"browser fallback if the selected model is removed = '{chat[0]}'")
    return out


# --------------------------------------------------------------------------- Open WebUI

def read_token():
    tok = os.environ.get("OPENWEBUI_API_KEY", "").strip()
    if not tok and os.path.isfile(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            tok = f.read().strip()
    return tok or None


def check_openwebui(installed, fix):
    out = {"app": "open-webui", "reachable": False, "issues": [], "fixed": [], "info": []}
    try:
        out["reachable"] = bool(http("GET", f"{OPENWEBUI_URL}/health").get("status"))
    except Exception as e:
        out["issues"].append(f"health check failed: {type(e).__name__}")
        return out
    token = read_token()
    if not token:
        out["info"].append("no admin API key (OPENWEBUI_API_KEY or ~/.config/ai-panel/openwebui_api_key): "
                           "settings not checked. Chat model list is live from Ollama; a missing task "
                           "model falls back to the chat model automatically.")
        return out

    def get(path):
        return http("GET", f"{OPENWEBUI_URL}{path}", token=token)

    try:
        get("/api/v1/configs/models")
    except urllib.error.HTTPError as e:
        out["issues"].append(f"API key rejected (HTTP {e.code}); it must belong to an admin and "
                             "'Enable API Keys' must be on")
        return out

    # Default / pinned models and model order
    mc = get("/api/v1/configs/models")
    changed = False
    defaults = [m for m in (mc.get("DEFAULT_MODELS") or "").split(",") if m.strip()]
    new_defaults = []
    for m in defaults:
        if is_installed(m, installed) or ":" not in m:  # no tag = workspace/custom model id, leave it
            new_defaults.append(m)
            continue
        sub = substitute(m, installed)
        msg = f"default model '{m}' is not installed"
        if fix and sub:
            out["fixed"].append(f"{msg} -> '{sub}'")
            new_defaults.append(sub)
            changed = True
        else:
            out["issues"].append(msg + (f" (suggest '{sub}')" if sub else ""))
            new_defaults.append(m)
    pinned = [m for m in (mc.get("DEFAULT_PINNED_MODELS") or "").split(",") if m.strip()]
    order = [m for m in (mc.get("MODEL_ORDER_LIST") or []) if m]
    stale_pinned = [m for m in pinned if ":" in m and not is_installed(m, installed)]
    stale_order = [m for m in order if ":" in m and not is_installed(m, installed)]
    for lst, stale, label in ((pinned, stale_pinned, "pinned"), (order, stale_order, "model order")):
        if stale:
            msg = f"{label} list references missing models: {', '.join(stale)}"
            if fix:
                out["fixed"].append(msg + " -> dropped")
                changed = True
            else:
                out["issues"].append(msg)
    if fix and changed:
        body = dict(mc)
        body["DEFAULT_MODELS"] = ",".join(new_defaults)
        body["DEFAULT_PINNED_MODELS"] = ",".join(m for m in pinned if m not in stale_pinned)
        body["MODEL_ORDER_LIST"] = [m for m in order if m not in stale_order]
        http("POST", f"{OPENWEBUI_URL}/api/v1/configs/models", body, token=token)
    out["info"].append(f"default models: {','.join(new_defaults) or '(none)'}")

    # Task model (title/tags/follow-up/query generation)
    tc = get("/api/v1/tasks/config")
    tm = (tc.get("TASK_MODEL") or "").strip()
    if tm and ":" in tm and not is_installed(tm, installed):
        sub = substitute(tm, installed)
        msg = f"task model '{tm}' is not installed (Open WebUI silently uses the chat model instead)"
        if fix:
            tc["TASK_MODEL"] = sub or ""
            http("POST", f"{OPENWEBUI_URL}/api/v1/tasks/config/update", tc, token=token)
            out["fixed"].append(f"{msg} -> '{sub or 'current chat model'}'")
        else:
            out["issues"].append(msg + (f" (suggest '{sub}')" if sub else ""))
    out["info"].append(f"task model: {tc.get('TASK_MODEL') or '(current chat model)'}")

    # RAG embedding model (report only: changing it means re-indexing documents)
    ec = get("/api/v1/retrieval/embedding")
    engine, emodel = ec.get("RAG_EMBEDDING_ENGINE") or "", ec.get("RAG_EMBEDDING_MODEL") or ""
    out["info"].append(f"RAG embedding: engine={engine or 'sentence-transformers (built-in)'} model={emodel}")
    if engine == "ollama" and not is_installed(emodel, installed):
        sub = substitute(emodel, installed, embedding=True)
        out["issues"].append(f"RAG embedding model '{emodel}' (ollama) is not installed; set it in "
                             f"Admin -> Settings -> Documents{f' (e.g. {sub})' if sub else ''} and re-index")

    # Workspace models (presets) built on a removed base model
    page, seen = 1, 0
    while True:
        res = get(f"/api/v1/models/list?page={page}")
        items = res.get("items") or []
        for it in items:
            base = it.get("base_model_id")
            if base and ":" in base and not is_installed(base, installed):
                sub = substitute(base, installed)
                out["issues"].append(f"workspace model '{it.get('name') or it.get('id')}' uses missing base "
                                     f"'{base}' (Workspace -> Models -> edit{f', e.g. {sub}' if sub else ''})")
        seen += len(items)
        if not items or seen >= (res.get("total") or 0):
            break
        page += 1
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--fix", action="store_true", help="repair what is safe to repair")
    ap.add_argument("--json", action="store_true", help="print JSON")
    args = ap.parse_args()

    try:
        installed = set(ollama_models())
    except Exception as e:
        print(json.dumps({"error": f"Ollama unreachable: {type(e).__name__}"}) if args.json
              else f"Ollama unreachable at {OLLAMA_URL}: {type(e).__name__}")
        return 2

    results = [check_perplexica(installed, args.fix), check_openwebui(installed, args.fix)]
    if args.json:
        print(json.dumps({"installed": sorted(installed), "apps": results}, indent=1))
    else:
        print(f"Ollama: {len(installed)} models installed")
        for r in results:
            print(f"\n[{r['app']}] reachable={r['reachable']}")
            for line in r["info"]:
                print(f"  - {line}")
            for line in r["fixed"]:
                print(f"  FIXED {line}")
            for line in r["issues"]:
                print(f"  ISSUE {line}")
    return 1 if any(r["issues"] for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
