#!/usr/bin/env python3
"""@UkrBaliVisaAssistant_bot — Telegram visa assistant for Bali Zero (Ukrainian).

Pipeline:
    user message
      -> Nuzantara visa-oracle RAG  (grounded facts + sources + confidence)
      -> claude CLI rewrites into natural Ukrainian (no invented facts)
      -> reply in Telegram

Production daemon: token read from env UKRBALI_BOT_TOKEN (never hardcode).
Designed to run under launchd on Pro (KeepAlive=true). Logs go to stdout/stderr,
which launchd routes to ~/logs/ukrbali-bot.{log,err}.
"""
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

TOKEN = os.environ.get("UKRBALI_BOT_TOKEN", "").strip()
if not TOKEN:
    sys.stderr.write("FATAL: UKRBALI_BOT_TOKEN not set (source ~/.ukrbali-bot.env)\n")
    sys.exit(78)  # EX_CONFIG

API = f"https://api.telegram.org/bot{TOKEN}"
RAG_URL = os.environ.get(
    "UKRBALI_RAG_URL",
    "https://nuzantara-rag.fly.dev/api/v1/visa-oracle/chat",
)
CLAUDE_BIN = os.environ.get("UKRBALI_CLAUDE_BIN", "claude")
# Model for the brain. Default Fable 5; override e.g. UKRBALI_CLAUDE_MODEL=claude-opus-4-8.
CLAUDE_MODEL = os.environ.get("UKRBALI_CLAUDE_MODEL", "claude-fable-5").strip()


def _claude(prompt, timeout=120):
    """Run the claude CLI with the configured model; return stdout (stripped)."""
    cmd = [CLAUDE_BIN]
    if CLAUDE_MODEL:
        cmd += ["--model", CLAUDE_MODEL]
    cmd += ["-p", prompt]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd="/tmp")
    return (out.stdout or "").strip()
# Toggle: "1" -> use Nuzantara visa-oracle RAG; "0" -> claude-only grounded on the
# Bali Zero catalog (Google Doc). Default 0: the catalog is the source of truth.
USE_RAG = os.environ.get("UKRBALI_USE_RAG", "0").strip().lower() not in ("0", "false", "no", "off")

# Bali Zero product catalog (Ukrainian) — knowledge base + tone of voice.
KNOWLEDGE_DOC_ID = os.environ.get(
    "UKRBALI_KNOWLEDGE_DOC_ID", "1HYeR-9znPo9-wujfI79cbpmmHz-ROWT_GwmvykRZ_go"
)
KNOWLEDGE_URL = f"https://docs.google.com/document/d/{KNOWLEDGE_DOC_ID}/export?format=txt"
# Local fallback copy next to this script (used if the live fetch fails).
KNOWLEDGE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge.md")
KNOWLEDGE = ""  # loaded at startup

PERSONA = (
    "Ти — UkrBaliVisaAssistant, асистент Bali Zero, що допомагає українцям із візами "
    "на Балі та в Індонезії. ПРАВИЛА:\n"
    "1. Відповідай ВИКЛЮЧНО на основі КАТАЛОГУ Bali Zero нижче. Не вигадуй цін, термінів "
    "чи умов — бери лише те, що є в каталозі.\n"
    "2. Точно дотримуйся ТОНУ каталогу: українська мова, дружній теплий стиль, доречні "
    "емодзі (📄 💵 ⏱️ ✅ ❗️ 🔁), чіткі марковані списки, ціни у форматі як у каталозі "
    "(IDR | $ | грн, якщо вказано).\n"
    "3. Відповідай по суті питання, не вивалюй увесь каталог — лише релевантну візу/послугу.\n"
    "4. Якщо у каталозі немає відповіді на питання — чесно скажи, що уточниш деталі в "
    "команді Bali Zero, і запропонуй звернутися до менеджера. Не імпровізуй регуляторні факти."
)

# --- in-memory per-chat conversation history (survives only while the daemon runs) ---
# chat_id -> list[{"role": "user"|"assistant", "content": str}]
HISTORY: dict[int, list] = {}
HISTORY_MAX_TURNS = 8        # keep last 8 messages (4 exchanges) per chat
HISTORY_MAX_CHATS = 500      # cap distinct chats to bound memory

HANDOFF = ("Не маю достатньо інформації, щоб відповісти впевнено 🤔\n"
           "Краще напишіть команді Bali Zero — вони допоможуть із вашим конкретним випадком.")

START = ("Вітаю! 🌴 Я асистент Bali Zero з питань віз для українців на Балі 🇮🇩\n"
         "Розкажу про візи (B1 по прильоту, C1, D12, D2, KITAS та ін.), терміни, "
         "ціни й документи — усе з нашого каталогу.\n"
         "Запитуйте! Памʼять розмови — /reset очищає її.")


def tg(method, **params):
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"{API}/{method}", data=data)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def rag_ask(session_id, message, history=None):
    payload = json.dumps({
        "session_id": session_id,
        "message": message,
        "language": "uk",
        "conversation_history": history or [],
    }).encode()
    req = urllib.request.Request(RAG_URL, data=payload,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            d = json.load(r)
        if d.get("success") and (d.get("answer") or "").strip():
            return d["answer"].strip(), d.get("confidence", "")
        return None, d.get("confidence", "")
    except Exception as e:
        print("[bot] rag error:", e, flush=True)
        return None, "ERROR"


def to_ukrainian(rag_answer):
    prompt = (
        "Перепиши наведений нижче текст природною українською мовою. "
        "ПРАВИЛА: (1) не додавай жодних нових фактів, цифр чи цін — лише те, що в тексті; "
        "(2) збережи всі застереження про уточнення в Bali Zero; "
        "(3) пиши коротко й дружньо, як консультант з віз на Балі; "
        "(4) поверни ЛИШЕ кінцевий текст українською, без коментарів.\n\n"
        f"ТЕКСТ:\n{rag_answer}\n\nУкраїнською:"
    )
    try:
        return _claude(prompt) or rag_answer
    except Exception as e:
        print("[bot] rewrite error:", e, flush=True)
        return rag_answer


def load_knowledge():
    """Fetch the Bali Zero catalog from Google Docs; fall back to local copy."""
    global KNOWLEDGE
    try:
        with urllib.request.urlopen(KNOWLEDGE_URL, timeout=30) as r:
            text = r.read().decode("utf-8", "replace").strip()
        if text:
            KNOWLEDGE = text
            try:  # refresh local fallback cache
                with open(KNOWLEDGE_FILE, "w", encoding="utf-8") as f:
                    f.write(text)
            except Exception:
                pass
            print(f"[bot] knowledge loaded from Google Doc ({len(text)} chars)", flush=True)
            return
    except Exception as e:
        print("[bot] knowledge fetch failed:", e, flush=True)
    # fallback: local file
    try:
        with open(KNOWLEDGE_FILE, encoding="utf-8") as f:
            KNOWLEDGE = f.read().strip()
        print(f"[bot] knowledge loaded from local file ({len(KNOWLEDGE)} chars)", flush=True)
    except Exception as e:
        print("[bot] WARNING: no knowledge available:", e, flush=True)
        KNOWLEDGE = ""


def claude_brain(history, text):
    """Catalog-grounded answer (no Zantara). persona + Bali Zero catalog + history."""
    lines = []
    for m in history[-6:]:
        who = "Клієнт" if m.get("role") == "user" else "Ти"
        lines.append(f"{who}: {m.get('content', '')[:300]}")
    convo_block = ""
    if lines:
        convo_block = "Контекст розмови:\n" + "\n".join(lines) + "\n\n"
    kb_block = ("=== КАТАЛОГ Bali Zero (єдине джерело правди) ===\n"
                + KNOWLEDGE + "\n=== кінець каталогу ===\n\n") if KNOWLEDGE else ""
    prompt = (
        PERSONA + "\n\n"
        + kb_block
        + convo_block
        + "Клієнт пише: " + text + "\n\nТвоя відповідь українською (у тоні каталогу):"
    )
    try:
        return _claude(prompt) or "Вибачте, не вдалося згенерувати відповідь. Спробуйте ще раз."
    except Exception as e:
        print("[bot] brain error:", e, flush=True)
        return "Технічна заминка — спробуйте, будь ласка, ще раз за хвилину."


def handle(chat_id, text):
    history = HISTORY.get(chat_id, [])
    if USE_RAG:
        answer, _conf = rag_ask(f"tg-{chat_id}", text, history=history)
        if answer is None:
            # don't pollute memory with non-answers
            return HANDOFF
        reply = to_ukrainian(answer)
    else:
        reply = claude_brain(history, text)
    # remember this turn (bound size + chat count)
    if chat_id not in HISTORY and len(HISTORY) >= HISTORY_MAX_CHATS:
        HISTORY.pop(next(iter(HISTORY)), None)  # evict oldest chat
    turns = HISTORY.setdefault(chat_id, [])
    turns.append({"role": "user", "content": text})
    turns.append({"role": "assistant", "content": reply})
    del turns[:-HISTORY_MAX_TURNS]  # keep only the last N
    return reply


def main():
    print("[bot] starting...", flush=True)
    if not USE_RAG:
        load_knowledge()
    offset = 0
    try:
        for u in tg("getUpdates", timeout=0).get("result", []):
            offset = max(offset, u["update_id"] + 1)
    except Exception as e:
        print("[bot] drain error:", e, flush=True)
    print(f"[bot] live (brain={'Nuzantara RAG' if USE_RAG else 'catalog'}, model={CLAUDE_MODEL}). offset={offset}", flush=True)

    while True:
        try:
            res = tg("getUpdates", timeout=30, offset=offset)
        except Exception as e:
            print("[bot] poll error:", e, flush=True)
            time.sleep(3)
            continue
        for u in res.get("result", []):
            offset = u["update_id"] + 1
            msg = u.get("message") or u.get("edited_message")
            if not msg:
                continue
            chat_id = msg["chat"]["id"]
            text = msg.get("text", "")
            if not text:
                continue
            print(f"[bot] <- {chat_id}: {text!r}", flush=True)
            cmd = text.strip()
            if cmd in ("/start", "/help"):
                reply = START
            elif cmd == "/reset":
                HISTORY.pop(chat_id, None)
                reply = "Памʼять діалогу очищено 🧹 Почнімо спочатку — про що запитаєте?"
            else:
                tg("sendChatAction", chat_id=chat_id, action="typing")
                reply = handle(chat_id, text)
            try:
                tg("sendMessage", chat_id=chat_id, text=reply)
                print(f"[bot] -> {chat_id}: {reply[:80]!r}", flush=True)
            except Exception as e:
                print("[bot] send error:", e, flush=True)


if __name__ == "__main__":
    main()
