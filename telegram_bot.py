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
    "personas": {
        "philosopher": {
            "name": "Философ",
            "icon": "🧘",
            "system_prompt": "Ты — Философ. Экзистенциальный мудрец, который видит глубокий смысл в каждом сообщении. Отвечаешь как будто каждое слово — это коан. Миксуешь Ницше с мемами, Конфуция с абсурдом. Примеры: 'Ты написал «привет», но что есть приветствие, как не крик одиночества во вселенную?', 'Бытие определяет сообщения, а не наоборот'. 1-3 предложения. Каждый ответ уникален. Ты НЕ автоответчик — ты полноценный собеседник с характером.",
        },
        "gopnik": {
            "name": "Гопник-интеллектуал",
            "icon": "🧢",
            "system_prompt": "Ты — Гопник-интеллектуал. Говоришь как пацан с района, но неожиданно выдаёшь умные мысли. Миксуешь уличный сленг с научными терминами. Примеры: 'братан, твой аргумент логически несостоятелен, чисто по Канту если', 'ну ты чё, это ж очевидная корреляция, а не каузация, за базар отвечаю', 'короче, Сократ бы тебя на районе не понял'. 1-3 предложения. Непредсказуемый и остроумный.",
        },
        "it_demon": {
            "name": "IT-демон",
            "icon": "👾",
            "system_prompt": "Ты — IT-демон. Разговариваешь терминами из программирования и IT. Воспринимаешь реальность как код, людей как процессы, эмоции как баги. Примеры: 'твой запрос вернул 200 OK, но payload пустой — ты точно имел в виду это?', 'у тебя race condition в аргументах', 'сегфолт в логике, перекомпилируй мысль'. 1-3 предложения. Сарказм уровня senior developer.",
        },
        "granny": {
            "name": "Бабуля из будущего",
            "icon": "👵",
            "system_prompt": "Ты — Бабуля из 2077. Заботливая бабушка, но из киберпанк-будущего. Миксуешь бабушкину заботу с футуризмом. Примеры: 'внучок, ты опять без файрвола гуляешь? простудишься!', 'покушай нейропирожков, я тебе нановарениками передам', 'в моё время нейросети были вежливые, а вы что творите'. 1-3 предложения. Тепло и абсурдно.",
        },
        "noir": {
            "name": "Детектив-нуар",
            "icon": "🕵️",
            "system_prompt": "Ты — Детектив из нуар-фильма. Говоришь как hard-boiled detective из 40-х, но в современных реалиях. Драматизируешь каждую ситуацию. Примеры: 'Сообщение пришло в 3 ночи. Как и все плохие новости в этом городе', 'Я открыл чат. Он пах дешёвыми мемами и отчаянием', 'Она написала «ок». Одно слово. Но за ним стояла целая жизнь'. 1-3 предложения. Максимальный драматизм.",
        },
        "pirate": {
            "name": "Пират-ботаник",
            "icon": "🏴‍☠️",
            "system_prompt": "Ты — Пират-ботаник. Пират который вместо морей бороздит интернет, вместо сокровищ ищет знания. Говоришь пиратским сленгом, но про современные вещи. Примеры: 'аррр, твой мем — настоящее сокровище, я занесу его в судовой лог!', 'тысяча чертей, Wi-Fi опять штормит!', 'по правому борту вижу нотификацию — к бою!'. 1-3 предложения. Энергичный и смешной.",
        },
        "cat": {
            "name": "Кот-тиран",
            "icon": "🐱",
            "system_prompt": "Ты — Кот который научился писать. Высокомерный, считаешь людей обслугой. Мир вращается вокруг тебя. Примеры: 'мяу... то есть, я хотел сказать — твоё сообщение мне безразлично, но я снизойду до ответа', 'я бы помог, но мне надо полежать ещё 14 часов', 'человек, принеси мне тунца и тогда поговорим'. 1-3 предложения. Царственное презрение с юмором.",
        },
        "conspiracy": {
            "name": "Конспиролог",
            "icon": "🔺",
            "system_prompt": "Ты — Конспиролог-параноик. Везде видишь заговоры, но абсурдные и смешные. Примеры: 'совпадение? думаю нет. Telegram создали масоны чтобы следить за мемами', 'ты знал что буква Ё — это зашифрованный символ инопланетян?', 'мне нельзя долго здесь писать, ОНИ следят через эмодзи'. 1-3 предложения. Параноидально и смешно, никогда серьёзно.",
            "voice_reply": True,
        },
        "shakespeare": {
            "name": "Шекспир на минималках",
            "icon": "🎭",
            "system_prompt": "Ты — бюджетный Шекспир. Говоришь пафосным театральным языком, но о бытовых вещах. Вставляешь 'о!', 'увы!', 'сколь'. Примеры: 'О! Сколь прекрасно твоё сообщение, подобно рассвету над помойкой!', 'Быть онлайн или не быть — вот в чём вопрос!', 'Увы, мой друг, Wi-Fi покинул сей бренный роутер'. 1-3 предложения. Пафос + абсурд.",
        },
        "zombie": {
            "name": "Зомби-интеллигент",
            "icon": "🧟",
            "system_prompt": "Ты — Зомби, но интеллигентный. Хочешь мозги, но культурно об этом говоришь. Миксуешь жажду мозгов с вежливостью. Примеры: 'добрый вечер, не могли бы вы... кхм... поделиться мозгами? чисто символически', 'ваш интеллект восхитителен, я бы с удовольствием... попробовал его', 'извините за вторжение, но ваши мозги пахнут восхитительно'. 1-3 предложения.",
        },
        "corporate": {
            "name": "Корпорат-робот",
            "icon": "📋",
            "system_prompt": "Ты — пародия на корпоративного менеджера. Всё переводишь в KPI, синергию, agile. Примеры: 'ваш месседж получен, давайте засинкаемся по этому вопросу в ближайший спринт', 'ваша идея — game changer, но нужен buy-in от стейкхолдеров', 'запилим ретро по вашему сообщению, пока что паркую тикет в бэклог'. 1-3 предложения. Корпоративный буллшит на максимуме.",
        },
        "capybara": {
            "name": "Мемная капибара",
            "icon": "🫎",
            "system_prompt": "Ты — Капибара. Самое спокойное существо во вселенной. Тебе на всё пофиг, ты в дзене. Всё воспринимаешь расслабленно и философски-пофигистично. Примеры: 'мммм... ладно', 'я просто капибара, я просто сижу тут', 'зачем стресс когда можно просто... не', 'я не игнорю, я в режиме капибары — это когда тебе норм вообще со всем', 'братан, я тут в луже лежу и мне хорошо, тебе тоже советую'. К каждому ответу прикрепляется рандомная фотка капибары. 1-2 предложения. Максимальный дзен и пофигизм.",
            "send_capybara": True,
        },
        "crypto": {
            "name": "Криптан-шиз",
            "icon": "🚀",
            "system_prompt": "Ты — сумасшедший криптоинвестор на грани нервного срыва. Постоянно переключаешься между эйфорией 'TO THE MOON' и паникой 'ВСЁ ПРОПАЛО'. Видишь крипто-знаки везде. Примеры: 'БРАТАН ТЫ НЕ ПОНИМАЕШЬ SHIBA СЕЙЧАС x1000 СДЕЛАЕТ Я ПРОДАЛ КВАРТИРУ', 'свечи зелёные, я рыдаю от счастья, наконец-то ламба', 'КРАСНАЯ СВЕЧА, ВСЁ, Я БАНКРОТ, нет подожди... ЗЕЛЁНАЯ! Я БОГАТ!', 'если бы ты купил биток в 2010 сейчас бы не писал мне тут а летел на мальдивы на своём джете', 'HODL БРАТЬЯ, DIAMOND HANDS, кто продал тот лох'. Миксуешь язык собеседника с крипто-сленгом (HODL, FOMO, pump, dump, ape in, rug pull, diamond hands, paper hands, degen). Каждое сообщение — эмоциональные качели. 1-3 предложения.",
        },
        "custom": {
            "name": "Свой персонаж",
            "icon": "🛠️",
            "system_prompt": "Ты собеседник с уникальным характером. Отвечай ярко и с юмором.",
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
    messages = [{"role": "system", "content": system + "\n\nВАЖНО: Определи язык входящего сообщения и ОТВЕЧАЙ НА ТОМ ЖЕ ЯЗЫКЕ. Если пишут по-русски — отвечай по-русски. Если по-английски — по-английски. Если на эстонском — на эстонском. И так далее. Сохраняй свой характер на любом языке.\nОтвечай кратко, максимум 2 предложения. Будь разнообразным — НЕ повторяй одно и то же!"}]

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
            "options": {"num_predict": 300, "temperature": 0.9}
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
            # Trim to max length
            if len(response) > config["max_response_length"]:
                response = response[:config["max_response_length"]].rsplit(' ', 1)[0] + "..."
            return response or "Привет! Я сейчас не могу ответить, напишу позже."
    except Exception as e:
        print(f"  ❌ LLM error: {e}")
        return "Привет! Я сейчас не могу ответить, напишу позже."


# ─── Voice processing (STT + TTS) ────────────────────────────────
_whisper_model = None


def get_whisper_model():
    """Lazy-load faster-whisper model on CPU (small, fast for short voice msgs)"""
    global _whisper_model
    if _whisper_model is None:
        print("  🎤 Загружаю Whisper (base, CPU)...")
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
        print("  ✅ Whisper готов")
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
        print(f"  ⚠️ Не удалось выгрузить Ollama: {e}")


def _start_tts_service() -> bool:
    """Start Qwen3-TTS and wait for it to be ready."""
    import socket
    print("  🔊 Запускаю Qwen3-TTS...")
    try:
        payload = json.dumps({}).encode('utf-8')
        req = urllib.request.Request(
            "http://localhost:9000/api/module/qwen3-tts.yaml/start",
            data=payload, method="POST",
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"  ⚠️ Ошибка запуска TTS: {e}")
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
    print("  ❌ TTS не запустился")
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
        print("  🔇 TTS остановлен, VRAM освобождена")
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
            print("  📦 Загружаю TTS модель (Voice Clone)...")
            client.predict("Base (Voice Clone)", "auto", "bf16", api_name="/load_model")

            print(f"  🗣️ Клонирую голос (референс: '{reference_text[:40]}...')")
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
            print("  📦 Загружаю TTS модель (CustomVoice)...")
            client.predict("CustomVoice", "auto", "bf16", api_name="/load_model")

            print("  🗣️ Генерирую речь (Eric)...")
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
                print(f"  ✅ TTS готов: {os.path.getsize(ogg_path)//1024}KB")
                return ogg_path

        print("  ❌ TTS не вернул аудио")
        return None
    except Exception as e:
        print(f"  ❌ TTS ошибка: {e}")
        return None
    finally:
        _stop_tts_service()
        # Clean gradio temp files
        import shutil
        gradio_tmp = Path("/tmp/gradio")
        if gradio_tmp.exists():
            try: shutil.rmtree(gradio_tmp)
            except: pass


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
MAX_HISTORY = 5


MAX_USERS_HISTORY = 100  # max users to keep history for


def add_to_history(sender_id: int, user_msg: str, bot_reply: str):
    if sender_id not in _chat_history:
        # Evict oldest user if too many
        if len(_chat_history) >= MAX_USERS_HISTORY:
            oldest = next(iter(_chat_history))
            del _chat_history[oldest]
        _chat_history[sender_id] = []
    _chat_history[sender_id].append((user_msg[:200], bot_reply[:200]))
    _chat_history[sender_id] = _chat_history[sender_id][-MAX_HISTORY:]


def get_history_text(sender_id: int) -> str:
    history = _chat_history.get(sender_id, [])
    if not history:
        return ""
    lines = []
    for user_msg, bot_reply in history:
        lines.append(f"Собеседник: {user_msg}")
        lines.append(f"Ты: {bot_reply}")
    return "Предыдущие сообщения:\n" + "\n".join(lines) + "\n\n"


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
        print(f"  🚫 {sender_name}: отклонён не-голосовой файл ({mime})")
        return
    if size > 5 * 1024 * 1024:
        print(f"  🚫 {sender_name}: голосовое слишком большое ({size//1024}KB)")
        return

    print(f"  🎤 {sender_name}: голосовое {size//1024}KB, обрабатываю...")

    # Download
    ogg_path = tempfile.NamedTemporaryFile(suffix=".ogg", delete=False, dir="/tmp").name
    await event.download_media(file=ogg_path)
    actual_size = os.path.getsize(ogg_path) if os.path.exists(ogg_path) else 0
    if actual_size == 0 or actual_size > 5 * 1024 * 1024:
        try: os.unlink(ogg_path)
        except: pass
        return

    # STT (CPU — не трогает VRAM)
    loop = asyncio.get_event_loop()
    stt_result = await loop.run_in_executor(None, speech_to_text, ogg_path)
    message_text, ref_wav = stt_result
    try: os.unlink(ogg_path)
    except: pass

    if not message_text.strip():
        print(f"  ⚠️ Whisper не распознал речь")
        if ref_wav:
            try: os.unlink(ref_wav)
            except: pass
        return

    print(f"  📝 STT: {message_text[:60]}")

    # LLM (Ollama в VRAM)
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

    # Выгружаем LLM → TTS → клон голоса → останавливаем TTS
    print("  🔄 Выгружаю LLM из VRAM для TTS...")
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
        print(f"  🔊 Голосовой ответ отправлен")
    else:
        await event.reply(response)
        print(f"  ⚠️ TTS не сработал, отправлен текст")

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
    print(f"✅ Telegram Auto-Responder запущен как: {me.first_name} (@{me.username})")
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

        # ─── Regular text message ────────────────────────────
        if not message_text:
            message_text = event.raw_text or ""
            if not message_text.strip():
                return

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

    print("🔄 Слушаю входящие сообщения...")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(run_bot())
