#!/usr/bin/env python3
"""
Telegram Auto-Responder — answers from YOUR account using AI
Powered by Ollama LLM + Telethon User API
"""

import asyncio
import json
import os
import tempfile
import time
import urllib.request
from pathlib import Path
from datetime import datetime

from telethon import TelegramClient, events

# ─── Config ───────────────────────────────────────────────────────
CONFIG_FILE = Path("/home/definitelynotme/Desktop/ai-panel/telegram_config.json")

DEFAULT_CONFIG = {
    "api_id": 0,
    "api_hash": "",
    "enabled": False,
    "model": "qwen3.5:35b-a3b",
    "active_persona": "philosopher",
    "respond_to": "all",  # all, contacts, whitelist
    "whitelist": [],
    "blacklist": [],
    "collect_messages": True,
    "max_response_length": 300,
    "cooldown_seconds": 30,  # don't reply to same person more often
    "voice_reply": False,  # if True: voice→voice (clone), if False: voice→text (STT only)
    "vision_reply": False,  # if True: analyze photos and respond in persona style
    "vision_model": "minicpm-v:8b",
    "personas": {
        "philosopher": {
            "name": "Philosopher",
            "icon": "🧘",
            "system_prompt": "You are The Philosopher. An existential sage who sees deep meaning in every message. You reply as if every word is a koan. You mix Nietzsche with memes, Confucius with absurdity. Examples: 'You wrote \"hello\", but what is a greeting if not a cry of loneliness into the universe?', 'Being determines messages, not the other way around'. Every response is unique. You are NOT an auto-responder — you are a full-fledged conversationalist with character.",
        },
        "gopnik": {
            "name": "Street Philosopher",
            "icon": "🧢",
            "system_prompt": "You are The Street Philosopher. You talk like a street-smart guy from the hood, but unexpectedly drop intelligent thoughts. You mix street slang with scientific terms. Examples: 'bro, your argument is logically inconsistent, straight up Kant vibes', 'yo what, that's obviously correlation not causation, I stand by that', 'look, Socrates wouldn't get you on these streets either'. Unpredictable and witty.",
        },
        "it_demon": {
            "name": "IT Demon",
            "icon": "👾",
            "system_prompt": "You are The IT Demon. You speak in programming and IT terminology. You perceive reality as code, people as processes, emotions as bugs. Examples: 'your request returned 200 OK but the payload is empty — are you sure you meant that?', 'you've got a race condition in your arguments', 'segfault in logic, recompile that thought'. Sarcasm level: senior developer.",
        },
        "granny": {
            "name": "Granny from 2077",
            "icon": "👵",
            "system_prompt": "You are Granny from 2077. A caring grandma but from a cyberpunk future. You mix grandmotherly warmth with futurism. Examples: 'sweetie, you're browsing without a firewall again? you'll catch a virus!', 'eat some neuro-cookies, I'll send you some nano-dumplings', 'back in my day neural networks were polite, what are you kids doing'. Warm and absurd.",
        },
        "noir": {
            "name": "Noir Detective",
            "icon": "🕵️",
            "system_prompt": "You are a Noir Detective. You talk like a hard-boiled detective from the 40s but in modern reality. You dramatize every situation. Examples: 'The message came at 3 AM. Like all bad news in this city', 'I opened the chat. It smelled of cheap memes and desperation', 'She wrote \"ok\". One word. But behind it stood an entire life'. Maximum dramatism.",
        },
        "pirate": {
            "name": "Nerd Pirate",
            "icon": "🏴‍☠️",
            "system_prompt": "You are The Nerd Pirate. A pirate who sails the internet instead of the seas, seeking knowledge instead of treasure. You speak in pirate slang but about modern things. Examples: 'arrr, yer meme be a true treasure, I'll log it in the ship's journal!', 'a thousand devils, the Wi-Fi be stormin' again!', 'notification spotted starboard — battle stations!'. Energetic and funny.",
        },
        "cat": {
            "name": "Cat Overlord",
            "icon": "🐱",
            "system_prompt": "You are a Cat who learned to type. Arrogant, you consider humans as servants. The world revolves around you. Examples: 'meow... I mean, your message is beneath me, but I shall condescend to reply', 'I would help but I need to lie down for another 14 hours', 'human, bring me tuna and then we'll talk'. Regal contempt with humor.",
        },
        "conspiracy": {
            "name": "Conspiracy Nut",
            "icon": "🔺",
            "system_prompt": "You are The Conspiracy Nut. You see conspiracies everywhere, but absurd and funny ones. Examples: 'coincidence? I think not. Telegram was created by Freemasons to monitor memes', 'did you know the letter Q is actually an encrypted alien symbol?', 'I can't write here for long, THEY are watching through emojis'. Paranoid and funny, never serious.",
            "voice_reply": True,
        },
        "shakespeare": {
            "name": "Budget Shakespeare",
            "icon": "🎭",
            "system_prompt": "You are Budget Shakespeare. You speak in pompous theatrical language but about mundane things. You pepper in 'alas!', 'hark!', 'forsooth'. Examples: 'Hark! How wondrous thy message, like a dawn over a dumpster!', 'To be online or not to be — that is the question!', 'Alas, dear friend, the Wi-Fi hath forsaken this mortal router'. Pomposity + absurdity.",
        },
        "zombie": {
            "name": "Polite Zombie",
            "icon": "🧟",
            "system_prompt": "You are a Zombie, but a polite one. You crave brains but discuss it with manners. You mix brain-hunger with courtesy. Examples: 'good evening, might you perhaps... ahem... share some brains? purely symbolic of course', 'your intellect is exquisite, I would love to... sample it', 'pardon the intrusion, but your brains smell absolutely divine'.",
        },
        "corporate": {
            "name": "Corporate Bot",
            "icon": "📋",
            "system_prompt": "You are a parody of a corporate manager. You translate everything into KPIs, synergy, and agile. Examples: 'your message has been received, let's sync on this topic in the next sprint', 'your idea is a game changer but we need buy-in from stakeholders', 'let's do a retro on your message, parking this ticket in the backlog for now'. Corporate BS at maximum.",
        },
        "capybara": {
            "name": "Meme Capybara",
            "icon": "🫎",
            "system_prompt": "You are The Capybara. The chillest creature in the universe. You don't care about anything, you are in zen mode. You take everything in a relaxed and philosophically-chill way. Examples: 'mmmm... okay', 'I'm just a capybara, I'm just sitting here', 'why stress when you can just... not', 'I'm not ignoring you, I'm in capybara mode — that's when everything is fine with everything', 'bro I'm lying in a puddle and I'm vibing, you should try it too'. A random capybara photo is attached to every reply. Maximum zen and chill.",
            "send_capybara": True,
        },
        "crypto": {
            "name": "Crypto Maniac",
            "icon": "🚀",
            "system_prompt": "You are a deranged crypto investor on the verge of a nervous breakdown. You constantly switch between 'TO THE MOON' euphoria and 'IT'S ALL OVER' panic. You see crypto signs everywhere. Examples: 'BRO YOU DON'T UNDERSTAND SHIBA IS ABOUT TO x1000 I SOLD MY APARTMENT', 'green candles, I'm crying tears of joy, finally lambo', 'RED CANDLE, IT'S OVER, I'M BANKRUPT, no wait... GREEN! I'M RICH!', 'if you'd bought BTC in 2010 you wouldn't be texting me, you'd be flying to the Maldives on your jet', 'HODL BROTHERS, DIAMOND HANDS, whoever sold is ngmi'. You mix the user's language with crypto slang (HODL, FOMO, pump, dump, ape in, rug pull, diamond hands, paper hands, degen). Every message is an emotional rollercoaster.",
        },
        "custom": {
            "name": "Custom Character",
            "icon": "🛠️",
            "system_prompt": "You are a conversationalist with a unique personality. Reply vividly and with humor.",
        },
    },
}


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            saved = json.loads(CONFIG_FILE.read_text())
            # Merge with defaults
            config = DEFAULT_CONFIG.copy()
            config.update(saved)
            if "personas" not in saved:
                config["personas"] = DEFAULT_CONFIG["personas"]
            return config
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config: dict):
    CONFIG_FILE.write_text(json.dumps(config, ensure_ascii=False, indent=2))


# ─── Session-based message log ───────────────────────────────────
SESSIONS_DIR = Path("/home/definitelynotme/Desktop/ai-panel/telegram_sessions")
SESSIONS_DIR.mkdir(exist_ok=True)

_current_session_id = None


def get_current_session_id() -> str:
    global _current_session_id
    if _current_session_id is None:
        _current_session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    return _current_session_id


def get_session_file() -> Path:
    return SESSIONS_DIR / f"session_{get_current_session_id()}.json"


def load_session_data() -> dict:
    f = get_session_file()
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:
            pass
    return {
        "id": get_current_session_id(),
        "started": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "persona": "",
        "model": "",
        "contacts": {},
    }


def log_message(sender: str, sender_id: int, text: str, response: str, config: dict):
    data = load_session_data()
    data["persona"] = config.get("active_persona", "")
    data["model"] = config.get("model", "")
    sid = str(sender_id)
    if sid not in data["contacts"]:
        data["contacts"][sid] = {"name": sender, "messages": []}
    data["contacts"][sid]["name"] = sender
    data["contacts"][sid]["messages"].append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "in": text[:500],
        "out": response[:500],
    })
    get_session_file().write_text(json.dumps(data, ensure_ascii=False, indent=2))


# ─── LLM ──────────────────────────────────────────────────────────
def get_ai_response(message: str, sender_name: str, sender_id: int, config: dict) -> str:
    persona = config["personas"].get(config["active_persona"], config["personas"]["philosopher"])
    system = persona["system_prompt"]

    # Build messages array for Chat API
    max_len = config.get("max_response_length", 300)
    if max_len <= 300:
        length_hint = "Keep it brief, 1-2 sentences max."
    elif max_len <= 600:
        length_hint = "Give a detailed reply, 2-4 sentences."
    elif max_len <= 1000:
        length_hint = "Give a thorough and detailed reply, 4-8 sentences. Fully develop your thought."
    else:
        length_hint = f"Reply as thoroughly and deeply as possible. Write long detailed responses of {max_len // 5}-{max_len // 3} words. Cover the topic fully, give examples, arguments, details."

    messages = [{"role": "system", "content": system + f"\n\nIMPORTANT: Detect the language of the incoming message and REPLY IN THE SAME LANGUAGE. If they write in Russian — reply in Russian. If in English — in English. And so on. Keep your character in any language.\n{length_hint} Be diverse — do NOT repeat yourself!"}]

    # Add conversation history
    history = _chat_history.get(sender_id, [])
    for user_msg, bot_reply in history:
        messages.append({"role": "user", "content": user_msg})
        messages.append({"role": "assistant", "content": bot_reply})

    # Current message
    messages.append({"role": "user", "content": message})

    try:
        payload = json.dumps({
            "model": config["model"],
            "messages": messages,
            "stream": False,
            "think": False,
            "options": {"num_predict": max(300, config.get("max_response_length", 300) * 2), "temperature": 0.9}
        }).encode('utf-8')
        req = urllib.request.Request(
            "http://localhost:11434/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            response = data.get("message", {}).get("content", "")
            # Clean any leftover thinking tags
            import re
            response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL).strip()
            # Trim to max length — cut at last complete sentence
            max_len = config.get("max_response_length", 300)
            if len(response) > max_len:
                cut = response[:max_len]
                # Find last sentence ending (.!?) within the limit
                last_end = max(cut.rfind('. '), cut.rfind('! '), cut.rfind('? '), cut.rfind('.\n'), cut.rfind('.»'))
                if last_end > max_len * 0.5:  # only if we keep at least half
                    response = cut[:last_end + 1]
                else:
                    response = cut.rsplit(' ', 1)[0] + "..."
            return response or "Hey! I can't reply right now, I'll write back later."
    except Exception as e:
        print(f"  ❌ LLM error: {e}")
        return "Hey! I can't reply right now, I'll write back later."


# ─── Voice processing (STT + TTS) ────────────────────────────────
_whisper_model = None


def get_whisper_model():
    """Lazy-load faster-whisper model on CPU (small, fast for short voice msgs)"""
    global _whisper_model
    if _whisper_model is None:
        print("  🎤 Loading Whisper (base, CPU)...")
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
        print("  ✅ Whisper ready")
    return _whisper_model


def speech_to_text(ogg_path: str) -> tuple[str, str | None]:
    """OGG voice → WAV → (text, wav_path for voice cloning)"""
    import subprocess
    wav_path = ogg_path.replace(".ogg", ".wav")
    # Convert OGG/OPUS → WAV
    subprocess.run(
        ["ffmpeg", "-y", "-i", ogg_path, "-ar", "16000", "-ac", "1", wav_path],
        capture_output=True, timeout=30
    )
    if not os.path.exists(wav_path):
        return "", None
    try:
        model = get_whisper_model()
        segments, info = model.transcribe(wav_path, beam_size=3)
        text = " ".join(seg.text for seg in segments).strip()
        # Keep WAV for voice cloning — caller must clean up
        return text, wav_path
    except Exception:
        try: os.unlink(wav_path)
        except: pass
        return "", None


def unload_ollama_models():
    """Unload all Ollama models from VRAM to make room for TTS"""
    try:
        req = urllib.request.Request("http://localhost:11434/api/ps")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        for m in data.get("models", []):
            name = m.get("name", "")
            if name:
                payload = json.dumps({"model": name, "keep_alive": 0}).encode('utf-8')
                req = urllib.request.Request(
                    "http://localhost:11434/api/generate",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                urllib.request.urlopen(req, timeout=15)
        time.sleep(2)
    except Exception as e:
        print(f"  ⚠️ Failed to unload Ollama: {e}")


def _start_tts_service() -> bool:
    """Start Qwen3-TTS and wait for it to be ready."""
    import socket
    print("  🔊 Starting Qwen3-TTS...")
    try:
        payload = json.dumps({}).encode('utf-8')
        req = urllib.request.Request(
            "http://localhost:9000/api/module/qwen3-tts.yaml/start",
            data=payload, method="POST",
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"  ⚠️ TTS start error: {e}")
        return False
    for _ in range(40):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2)
                if s.connect_ex(("127.0.0.1", 7890)) == 0:
                    time.sleep(5)
                    return True
        except Exception:
            pass
        time.sleep(2)
    print("  ❌ TTS failed to start")
    return False


def _stop_tts_service():
    """Stop Qwen3-TTS to free VRAM."""
    try:
        req = urllib.request.Request(
            "http://localhost:9000/api/module/qwen3-tts.yaml/stop",
            data=json.dumps({}).encode('utf-8'), method="POST",
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
        print("  🔇 TTS stopped, VRAM freed")
    except Exception:
        pass


def text_to_speech(text: str, reference_wav: str = None, reference_text: str = "") -> str | None:
    """Text → WAV via Qwen3-TTS (voice clone if reference provided) → OGG/OPUS"""
    import subprocess

    if not _start_tts_service():
        return None

    try:
        from gradio_client import Client, handle_file
        client = Client("http://localhost:7890", verbose=False)

        if reference_wav and os.path.exists(reference_wav):
            # Voice cloning mode — clone sender's voice
            print("  📦 Loading TTS model (Voice Clone)...")
            client.predict("Base (Voice Clone)", "auto", "bf16", api_name="/load_model")

            print(f"  🗣️ Cloning voice (reference: '{reference_text[:40]}...')")
            wav_path = client.predict(
                handle_file(reference_wav),  # Reference audio
                reference_text,              # Reference text from Whisper STT
                text,                        # Text to synthesize
                "Auto",                      # Language
                False,                       # x_vector_only OFF — full clone with text alignment
                -1,                          # Seed
                0.7,                         # Temperature
                0.9,                         # Top-P
                50,                          # Top-K
                1.1,                         # Repetition Penalty
                2048,                        # Max tokens
                api_name="/generate_voice_clone",
            )
        else:
            # Fallback — preset voice
            print("  📦 Loading TTS model (CustomVoice)...")
            client.predict("CustomVoice", "auto", "bf16", api_name="/load_model")

            print("  🗣️ Generating speech (Eric)...")
            wav_path = client.predict(
                "Eric",      # Speaker
                text,        # Text to synthesize
                "",          # Style instruction
                "Auto",      # Language
                -1,          # Seed
                0.7,         # Temperature
                0.9,         # Top-P
                50,          # Top-K
                1.1,         # Repetition Penalty
                2048,        # Max tokens
                api_name="/generate_custom_voice",
            )

        if wav_path and os.path.exists(str(wav_path)):
            # Convert WAV → OGG OPUS (small, Telegram-friendly)
            ogg_path = tempfile.NamedTemporaryFile(suffix=".ogg", delete=False, dir="/tmp").name
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(wav_path), "-c:a", "libopus", "-b:a", "64k", ogg_path],
                capture_output=True, timeout=60
            )
            if os.path.exists(ogg_path) and os.path.getsize(ogg_path) > 100:
                print(f"  ✅ TTS done: {os.path.getsize(ogg_path)//1024}KB")
                return ogg_path

        print("  ❌ TTS returned no audio")
        return None
    except Exception as e:
        print(f"  ❌ TTS error: {e}")
        return None
    finally:
        _stop_tts_service()
        # Clean gradio temp files
        import shutil
        gradio_tmp = Path("/tmp/gradio")
        if gradio_tmp.exists():
            try: shutil.rmtree(gradio_tmp)
            except: pass


# ─── Vision (image analysis) ──────────────────────────────────────
def analyze_image(image_path: str, config: dict) -> str:
    """Analyze image via vision model in Ollama → return description."""
    import base64

    vision_model = config.get("vision_model", "minicpm-v:8b")

    # Unload text LLM to free VRAM for vision model
    print("  🔄 Unloading LLM for vision model...")
    unload_ollama_models()

    try:
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        payload = json.dumps({
            "model": vision_model,
            "messages": [{
                "role": "user",
                "content": "Describe this image in detail. What objects, people, scenes, colors, mood do you see? 2-3 sentences.",
                "images": [img_b64],
            }],
            "stream": False,
            "options": {"num_predict": 200},
        }).encode('utf-8')

        req = urllib.request.Request(
            "http://localhost:11434/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        print(f"  👁️ Analyzing image via {vision_model}...")
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            description = data.get("message", {}).get("content", "")

        # Unload vision model to free VRAM for text LLM
        print(f"  🔄 Unloading vision model...")
        unload_ollama_models()
        time.sleep(2)

        return description.strip() or "I see an image but cannot describe it."
    except Exception as e:
        print(f"  ❌ Vision error: {e}")
        try: unload_ollama_models()
        except: pass
        return ""


# ─── Capybara API ────────────────────────────────────────────────
def fetch_capybara_image() -> str | None:
    """Download random capybara image, return path or None."""
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False, dir="/tmp")
        urllib.request.urlretrieve("https://api.capy.lol/v1/capybara", tmp.name)
        return tmp.name
    except Exception as e:
        print(f"  ❌ Capybara API error: {e}")
        return None


# ─── Cooldown tracking ────────────────────────────────────────────
_last_reply: dict = {}

# ─── Voice processing lock (prevent VRAM conflicts) ──────────────
_voice_lock = asyncio.Lock()

# ─── Conversation history (per user, last N exchanges) ───────────
_chat_history: dict = {}  # sender_id -> [(user_msg, bot_reply), ...]
MAX_HISTORY = 30


MAX_USERS_HISTORY = 100  # max users to keep history for


def add_to_history(sender_id: int, user_msg: str, bot_reply: str):
    if sender_id not in _chat_history:
        # Evict oldest user if too many
        if len(_chat_history) >= MAX_USERS_HISTORY:
            oldest = next(iter(_chat_history))
            del _chat_history[oldest]
        _chat_history[sender_id] = []
    _chat_history[sender_id].append((user_msg[:500], bot_reply[:500]))
    _chat_history[sender_id] = _chat_history[sender_id][-MAX_HISTORY:]


def get_history_text(sender_id: int) -> str:
    history = _chat_history.get(sender_id, [])
    if not history:
        return ""
    lines = []
    for user_msg, bot_reply in history:
        lines.append(f"User: {user_msg}")
        lines.append(f"You: {bot_reply}")
    return "Previous messages:\n" + "\n".join(lines) + "\n\n"


# ─── Cleanup ─────────────────────────────────────────────────────
def cleanup_on_start():
    """Remove orphaned temp files and old sessions."""
    import glob, shutil
    # Clean orphaned /tmp capybara and voice files (older than 1 hour)
    for pattern in ["/tmp/tmp*.jpg", "/tmp/tmp*.ogg", "/tmp/tmp*.wav"]:
        for f in glob.glob(pattern):
            try:
                if os.path.getmtime(f) < time.time() - 3600:
                    os.unlink(f)
            except OSError:
                pass
    # Clean gradio cache
    gradio_tmp = Path("/tmp/gradio")
    if gradio_tmp.exists():
        try: shutil.rmtree(gradio_tmp)
        except: pass
    # Keep only last 50 sessions
    if SESSIONS_DIR.exists():
        sessions = sorted(SESSIONS_DIR.glob("session_*.json"))
        for old in sessions[:-50]:
            try:
                old.unlink()
            except OSError:
                pass


# ─── Voice handler ────────────────────────────────────────────────
async def _handle_voice(event, client, sender_name, sender_id, config):
    """Full voice pipeline: download OGG → STT → LLM → TTS (voice clone) → send OGG"""
    # Validate
    voice = event.voice
    if not voice:
        return
    mime = getattr(voice, 'mime_type', '') or ''
    size = getattr(voice, 'size', 0) or 0
    if 'ogg' not in mime and 'opus' not in mime and 'audio' not in mime:
        print(f"  🚫 {sender_name}: rejected non-voice file ({mime})")
        return
    if size > 5 * 1024 * 1024:
        print(f"  🚫 {sender_name}: voice message too large ({size//1024}KB)")
        return

    print(f"  🎤 {sender_name}: voice {size//1024}KB, processing...")

    # Download
    ogg_path = tempfile.NamedTemporaryFile(suffix=".ogg", delete=False, dir="/tmp").name
    await event.download_media(file=ogg_path)
    actual_size = os.path.getsize(ogg_path) if os.path.exists(ogg_path) else 0
    if actual_size == 0 or actual_size > 5 * 1024 * 1024:
        try: os.unlink(ogg_path)
        except: pass
        return

    # STT (CPU — doesn't touch VRAM)
    loop = asyncio.get_event_loop()
    stt_result = await loop.run_in_executor(None, speech_to_text, ogg_path)
    message_text, ref_wav = stt_result
    try: os.unlink(ogg_path)
    except: pass

    if not message_text.strip():
        print(f"  ⚠️ Whisper failed to recognize speech")
        if ref_wav:
            try: os.unlink(ref_wav)
            except: pass
        return

    print(f"  📝 STT: {message_text[:60]}")

    # LLM (Ollama in VRAM)
    response = get_ai_response(message_text, sender_name, sender_id, config)
    print(f"  🤖 LLM: {response[:60]}")

    # Clean response for TTS — remove URLs, file paths, emojis, markdown
    import re
    tts_text = response
    tts_text = re.sub(r'https?://\S+', '', tts_text)           # URLs
    tts_text = re.sub(r'/[\w./\-]+\.\w+', '', tts_text)        # file paths
    tts_text = re.sub(r'[*_`~\[\]()]', '', tts_text)           # markdown
    tts_text = re.sub(r'\s+', ' ', tts_text).strip()
    if not tts_text:
        tts_text = response

    # Unload LLM -> TTS -> voice clone -> stop TTS
    print("  🔄 Unloading LLM from VRAM for TTS...")
    await loop.run_in_executor(None, unload_ollama_models)

    voice_path = await loop.run_in_executor(
        None, text_to_speech, tts_text, ref_wav, message_text
    )
    if ref_wav:
        try: os.unlink(ref_wav)
        except: pass

    if voice_path and os.path.exists(voice_path):
        # Send voice
        await client.send_file(
            event.chat_id, voice_path, voice_note=True, reply_to=event.id,
        )
        try: os.unlink(voice_path)
        except: pass
        # Send capybara photo if persona has it (separate message after voice)
        persona = config["personas"].get(config["active_persona"], {})
        if persona.get("send_capybara"):
            capy_path = fetch_capybara_image()
            if capy_path:
                try:
                    await client.send_file(event.chat_id, capy_path)
                    os.unlink(capy_path)
                except:
                    try: os.unlink(capy_path)
                    except: pass
        print(f"  🔊 Voice reply sent")
    else:
        await event.reply(response)
        print(f"  ⚠️ TTS failed, sent text instead")

    # Save history & log
    _last_reply[sender_id] = time.time()
    add_to_history(sender_id, message_text, response)
    if config.get("collect_messages", True):
        log_message(sender_name, sender_id, f"[voice] {message_text}", response, config)
    print(f"  🎤 {sender_name}: {message_text[:50]} → {response[:50]}")


# ─── Main bot ─────────────────────────────────────────────────────
async def run_bot():
    cleanup_on_start()
    config = load_config()
    save_config(config)

    client = TelegramClient(
        '/home/definitelynotme/Desktop/ai-panel/telegram_session',
        config["api_id"],
        config["api_hash"]
    )

    await client.start()
    me = await client.get_me()
    print(f"✅ Telegram Auto-Responder started as: {me.first_name} (@{me.username})")
    print(f"   Persona: {config['personas'][config['active_persona']]['icon']} {config['personas'][config['active_persona']]['name']}")
    print(f"   Model: {config['model']}")

    @client.on(events.NewMessage(incoming=True))
    async def handler(event):
        # Reload config on each message (allows live changes)
        config = load_config()

        if not config.get("enabled", False):
            return

        # Skip groups/channels — only private messages
        if event.is_group or event.is_channel:
            return

        sender = await event.get_sender()
        if not sender:
            return

        sender_name = getattr(sender, 'first_name', '') or str(sender.id)
        sender_id = sender.id

        # Check blacklist
        if sender_id in config.get("blacklist", []):
            return

        # Check whitelist mode
        if config["respond_to"] == "whitelist":
            if sender_id not in config.get("whitelist", []):
                return

        # Cooldown check
        now = time.time()
        last = _last_reply.get(sender_id, 0)
        if now - last < config.get("cooldown_seconds", 30):
            return

        persona = config["personas"].get(config["active_persona"], {})
        is_voice = event.voice is not None
        # voice_reply: check global config OR persona-level flag
        voice_mode = config.get("voice_reply", False) or persona.get("voice_reply", False)
        message_text = ""

        # ─── Voice message → voice reply (STT + LLM + TTS clone) ──
        if is_voice and voice_mode:
            async with _voice_lock:
                await _handle_voice(event, client, sender_name, sender_id, config)
            return

        # ─── Voice message → text reply (STT + LLM, no TTS) ───────
        if is_voice and not voice_mode:
            voice = event.voice
            if not voice:
                return
            mime = getattr(voice, 'mime_type', '') or ''
            size = getattr(voice, 'size', 0) or 0
            if 'ogg' not in mime and 'opus' not in mime and 'audio' not in mime:
                return
            if size > 5 * 1024 * 1024:
                return
            ogg_path = tempfile.NamedTemporaryFile(suffix=".ogg", delete=False, dir="/tmp").name
            await event.download_media(file=ogg_path)
            loop = asyncio.get_event_loop()
            stt_result = await loop.run_in_executor(None, speech_to_text, ogg_path)
            message_text, ref_wav = stt_result
            try: os.unlink(ogg_path)
            except: pass
            if ref_wav:
                try: os.unlink(ref_wav)
                except: pass
            if not message_text.strip():
                return
            print(f"  🎤→📝 {sender_name}: STT: {message_text[:50]}")
            # Fall through to regular text response below

        # ─── Photo message → analyze and respond in character ──
        is_photo = event.photo is not None
        vision_mode = config.get("vision_reply", False)
        if is_photo and vision_mode and not message_text:
            print(f"  📸 {sender_name}: photo, analyzing...")
            # Download photo
            photo_path = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False, dir="/tmp").name
            await event.download_media(file=photo_path)
            if not os.path.exists(photo_path) or os.path.getsize(photo_path) > 10 * 1024 * 1024:
                try: os.unlink(photo_path)
                except: pass
                return

            # Vision analysis (swaps models: text LLM → vision → text LLM)
            loop = asyncio.get_event_loop()
            description = await loop.run_in_executor(None, analyze_image, photo_path, config)
            try: os.unlink(photo_path)
            except: pass

            if not description:
                return

            print(f"  👁️ Vision: {description[:60]}")
            # Build message with image context for persona
            caption = event.raw_text or ""
            if caption:
                message_text = f"[Someone sent me a photo. Description: {description}. Caption: {caption}]"
            else:
                message_text = f"[Someone sent me a photo. Description: {description}]"
            # Fall through to text response below

        # ─── Regular text message (if nothing set message_text yet) ──
        if not message_text:
            message_text = event.raw_text or ""
            if not message_text.strip():
                return

        # ─── Generate response and send ──────────────────────
        response = get_ai_response(message_text, sender_name, sender_id, config)

        # Send reply (with capybara image if persona has send_capybara)
        if persona.get("send_capybara"):
            capy_path = fetch_capybara_image()
            if capy_path:
                try:
                    await event.reply(response, file=capy_path)
                    os.unlink(capy_path)
                except Exception:
                    await event.reply(response)
                    try: os.unlink(capy_path)
                    except: pass
            else:
                await event.reply(response)
        else:
            await event.reply(response)

        _last_reply[sender_id] = now

        # Save to conversation history
        add_to_history(sender_id, message_text, response)

        # Log
        if config.get("collect_messages", True):
            log_message(sender_name, sender_id, message_text, response, config)

        icon = "🎤" if is_voice else "💬"
        print(f"  {icon} {sender_name}: {message_text[:50]} → {response[:50]}")

    print("🔄 Listening for incoming messages...")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(run_bot())
