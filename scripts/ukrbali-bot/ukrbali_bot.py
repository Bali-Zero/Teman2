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

# --- in-memory per-chat conversation history (survives only while the daemon runs) ---
# chat_id -> list[{"role": "user"|"assistant", "content": str}]
HISTORY: dict[int, list] = {}
HISTORY_MAX_TURNS = 8        # keep last 8 messages (4 exchanges) per chat
HISTORY_MAX_CHATS = 500      # cap distinct chats to bound memory

HANDOFF = ("Не маю достатньо інформації, щоб відповісти впевнено 🤔\n"
           "Краще напишіть команді Bali Zero — вони допоможуть із вашим конкретним випадком.")

START = ("Вітаю! Я асистент Bali Zero з питань віз та переїзду на Балі 🇮🇩\n"
         "Відповідаю на основі офіційної бази Bali Zero. Запитайте про візи "
         "(eVOA, KITAS, KITAP), продовження, бізнес чи нерухомість.\n"
         "Я памʼятаю контекст розмови — /reset очищає його.")


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
        out = subprocess.run([CLAUDE_BIN, "-p", prompt],
                             capture_output=True, text=True, timeout=120, cwd="/tmp")
        return (out.stdout or "").strip() or rag_answer
    except Exception as e:
        print("[bot] rewrite error:", e, flush=True)
        return rag_answer


def handle(chat_id, text):
    history = HISTORY.get(chat_id, [])
    answer, _conf = rag_ask(f"tg-{chat_id}", text, history=history)
    if answer is None:
        # don't pollute memory with non-answers
        return HANDOFF
    reply = to_ukrainian(answer)
    # remember this turn (bound size + chat count)
    if chat_id not in HISTORY and len(HISTORY) >= HISTORY_MAX_CHATS:
        HISTORY.pop(next(iter(HISTORY)), None)  # evict oldest chat
    turns = HISTORY.setdefault(chat_id, [])
    turns.append({"role": "user", "content": text})
    turns.append({"role": "assistant", "content": reply})
    del turns[:-HISTORY_MAX_TURNS]  # keep only the last N
    return reply


def main():
    print("[bot] starting (RAG-backed), draining old updates...", flush=True)
    offset = 0
    try:
        for u in tg("getUpdates", timeout=0).get("result", []):
            offset = max(offset, u["update_id"] + 1)
    except Exception as e:
        print("[bot] drain error:", e, flush=True)
    print(f"[bot] live (Nuzantara RAG). offset={offset}", flush=True)

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
