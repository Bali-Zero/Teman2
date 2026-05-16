#!/usr/bin/env python3
"""
WA Linked Devices Audit Bot — Bali Zero
Ogni lunedì:
  09:00 WITA → reminder a tutti i dipendenti (DM individuale)
  10:05 WITA → check chi non ha risposto → alert management
Dipendenti inviano screenshot Linked Devices nel DM con il bot.
Bot salva screenshot + log su disco, notifica management.
"""

import json
import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from telegram import Bot, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ─── CONFIG ────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
MANAGEMENT_CHAT_ID = int(os.environ["WA_AUDIT_MANAGEMENT_CHAT_ID"])  # gruppo management
AUDIT_LOG_DIR = Path(os.environ.get("WA_AUDIT_LOG_DIR", "/Users/nuzantara/var/wa-audit"))
WITA = ZoneInfo("Asia/Makassar")

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("wa-audit-bot")

# Roster dipendenti: chat_id Telegram → nome
# Popolato via /register o manualmente in wa-audit-roster.json
ROSTER_FILE = AUDIT_LOG_DIR / "wa-audit-roster.json"


def load_roster() -> dict[str, str]:
    if ROSTER_FILE.exists():
        return json.loads(ROSTER_FILE.read_text())
    return {}


def save_roster(roster: dict[str, str]) -> None:
    ROSTER_FILE.parent.mkdir(parents=True, exist_ok=True)
    ROSTER_FILE.write_text(json.dumps(roster, indent=2, ensure_ascii=False))


def submission_file(week: date, chat_id: int) -> Path:
    return AUDIT_LOG_DIR / f"{week.isoformat()}" / f"{chat_id}.done"


def screenshot_dir(week: date) -> Path:
    return AUDIT_LOG_DIR / f"{week.isoformat()}"


def current_week_monday() -> date:
    today = datetime.now(WITA).date()
    return today - timedelta(days=today.weekday())


# ─── HANDLERS ──────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Halo! Ini adalah bot audit WhatsApp Linked Devices Bali Zero.\n\n"
        "Setiap Senin pagi kamu akan mendapat pengingat untuk kirim screenshot.\n"
        "Gunakan /register untuk mendaftarkan akunmu."
    )


async def cmd_register(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    roster = load_roster()
    roster[str(user.id)] = user.full_name
    save_roster(roster)
    logger.info("Registered: %s (%s)", user.full_name, user.id)
    await update.message.reply_text(
        f"✅ Terdaftar: {user.full_name} (ID: {user.id})\n"
        "Kamu akan dapat reminder setiap Senin pukul 09:00 WITA."
    )
    # Notify management
    bot: Bot = ctx.bot
    await bot.send_message(
        MANAGEMENT_CHAT_ID,
        f"📋 Registrasi baru: {user.full_name} (ID: {user.id})",
    )


async def cmd_roster(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Solo management: mostra roster attuale."""
    if update.effective_chat.id != MANAGEMENT_CHAT_ID:
        return
    roster = load_roster()
    if not roster:
        await update.message.reply_text("Roster vuoto — nessun dipendente registrato.")
        return
    lines = [f"• {name} (ID: {cid})" for cid, name in roster.items()]
    await update.message.reply_text("👥 Roster dipendenti:\n" + "\n".join(lines))


async def handle_screenshot(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Riceve foto/documento — conta come submission."""
    user = update.effective_user
    roster = load_roster()
    if str(user.id) not in roster:
        await update.message.reply_text(
            "Non sei registrato. Usa /register prima di inviare."
        )
        return

    week = current_week_monday()
    done_file = submission_file(week, user.id)

    # Evita doppio conteggio
    if done_file.exists():
        await update.message.reply_text("✅ Screenshot già ricevuto per questa settimana. Grazie!")
        return

    # Salva screenshot su disco
    sdir = screenshot_dir(week)
    sdir.mkdir(parents=True, exist_ok=True)

    if update.message.photo:
        photo = update.message.photo[-1]  # massima risoluzione
        file = await ctx.bot.get_file(photo.file_id)
        img_path = sdir / f"{user.id}.jpg"
        await file.download_to_drive(img_path)
    elif update.message.document:
        doc = update.message.document
        file = await ctx.bot.get_file(doc.file_id)
        ext = Path(doc.file_name or "file").suffix or ".bin"
        img_path = sdir / f"{user.id}{ext}"
        await file.download_to_drive(img_path)
    else:
        await update.message.reply_text(
            "Kirim sebagai foto atau file. Teks saja tidak diterima."
        )
        return

    done_file.touch()
    nome = roster[str(user.id)]
    logger.info("Screenshot received: %s week=%s", nome, week)

    await update.message.reply_text(
        f"✅ Screenshot diterima! Terima kasih, {nome.split()[0]}."
    )

    # Forward a management con nome
    await ctx.bot.send_message(
        MANAGEMENT_CHAT_ID,
        f"📸 Screenshot WA Linked Devices ricevuto: **{nome}** — settimana {week}",
        parse_mode="Markdown",
    )
    await ctx.bot.forward_message(
        chat_id=MANAGEMENT_CHAT_ID,
        from_chat_id=update.effective_chat.id,
        message_id=update.message.message_id,
    )


# ─── JOBS SCHEDULATI ───────────────────────────────────────────────────

async def job_send_reminders(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """09:00 WITA lunedì — reminder a tutti i dipendenti."""
    roster = load_roster()
    week = current_week_monday()
    logger.info("Sending reminders for week %s to %d employees", week, len(roster))

    for chat_id_str, nome in roster.items():
        chat_id = int(chat_id_str)
        try:
            done = submission_file(week, chat_id).exists()
            if done:
                continue
            await ctx.bot.send_message(
                chat_id,
                f"🔔 *Audit WA Mingguan — {week.strftime('%d %B %Y')}*\n\n"
                f"Halo {nome.split()[0]}! Tolong kirim screenshot menu *Linked Devices* "
                f"WhatsApp Business Bali Zero kamu sebelum pukul *10:00 WITA*.\n\n"
                f"Cara: WA Business → ⋮ → Linked Devices → screenshot seluruh layar.\n\n"
                f"Terima kasih 🙏",
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.warning("Failed to send reminder to %s (%s): %s", nome, chat_id, e)


async def job_check_missing(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """10:05 WITA lunedì — controlla chi manca e avvisa management."""
    roster = load_roster()
    week = current_week_monday()

    missing = []
    submitted = []
    for chat_id_str, nome in roster.items():
        if submission_file(week, int(chat_id_str)).exists():
            submitted.append(nome)
        else:
            missing.append(nome)

    logger.info("Audit check week=%s: submitted=%d missing=%d", week, len(submitted), len(missing))

    if not missing:
        await ctx.bot.send_message(
            MANAGEMENT_CHAT_ID,
            f"✅ *Audit WA {week}* — tutti i dipendenti hanno inviato lo screenshot ({len(submitted)}/{len(roster)}).",
            parse_mode="Markdown",
        )
        return

    lines_missing = "\n".join(f"  ❌ {n}" for n in missing)
    lines_ok = "\n".join(f"  ✅ {n}" for n in submitted)
    await ctx.bot.send_message(
        MANAGEMENT_CHAT_ID,
        f"⚠️ *Audit WA {week} — {len(missing)} dipendente non ha inviato screenshot:*\n\n"
        f"{lines_missing}\n\n"
        f"Inviato:\n{lines_ok}\n\n"
        f"Penale contrattuale: Rp 2.000.000 per settimana per ogni dipendente (Lampiran V).",
        parse_mode="Markdown",
    )

    # Sollecito individuale
    for chat_id_str, nome in roster.items():
        if not submission_file(week, int(chat_id_str)).exists():
            try:
                await ctx.bot.send_message(
                    int(chat_id_str),
                    f"⚠️ {nome.split()[0]}, screenshot Linked Devices belum diterima.\n"
                    f"Harap kirim sekarang. Keterlambatan dikenai penalti sesuai kontrak.",
                )
            except Exception as e:
                logger.warning("Failed to send late-reminder to %s: %s", nome, e)


# ─── MAIN ──────────────────────────────────────────────────────────────

def main() -> None:
    AUDIT_LOG_DIR.mkdir(parents=True, exist_ok=True)

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("register", cmd_register))
    app.add_handler(CommandHandler("roster", cmd_roster))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_screenshot))

    jq = app.job_queue

    now_wita = datetime.now(WITA)

    # Calcola prossimo lunedì 09:00 WITA
    def next_weekday_time(weekday: int, hour: int, minute: int) -> datetime:
        d = now_wita.date()
        days_ahead = weekday - d.weekday()
        if days_ahead < 0 or (days_ahead == 0 and now_wita.hour * 60 + now_wita.minute >= hour * 60 + minute):
            days_ahead += 7
        next_dt = datetime(d.year, d.month, d.day, hour, minute, tzinfo=WITA) + timedelta(days=days_ahead)
        return next_dt

    reminder_dt = next_weekday_time(0, 9, 0)   # lunedì 09:00
    check_dt    = next_weekday_time(0, 10, 5)  # lunedì 10:05

    jq.run_repeating(job_send_reminders, interval=timedelta(weeks=1), first=reminder_dt, name="reminder")
    jq.run_repeating(job_check_missing,  interval=timedelta(weeks=1), first=check_dt,    name="check_missing")

    logger.info(
        "Bot avviato. Prossimo reminder: %s, prossimo check: %s",
        reminder_dt.strftime("%Y-%m-%d %H:%M WITA"),
        check_dt.strftime("%Y-%m-%d %H:%M WITA"),
    )

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
