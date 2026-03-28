#!/usr/bin/env python3
"""
RAGAS Eval Pipeline — Valutazione qualità RAG con metriche oggettive.

Modalità 1 (DEFAULT): Metriche proxy da rag_canary (cosine similarity, collection coverage).
  Funziona senza dipendenze extra. Usato per il cron domenicale.

Modalità 2 (--ragas): RAGAS completo (faithfulness, answer_relevancy, context_precision).
  Richiede ragas + anthropic installati. Richiede BACKEND_URL + BACKEND_API_KEY.

Cron OpenClaw Air: 0 6 * * 0  (domenica 06:00 WITA)

Usage:
    python3 scripts/ragas_eval.py              # Proxy metrics (default)
    python3 scripts/ragas_eval.py --ragas      # Full RAGAS (se disponibile)
    python3 scripts/ragas_eval.py --dry-run    # No Telegram alert
    python3 scripts/ragas_eval.py --verbose    # Debug output
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

WITA = timezone(timedelta(hours=8))
PROJECT_ROOT = Path(__file__).parent.parent
CANARY_DIR = PROJECT_ROOT / "scripts" / ".rag_canary"
LAST_RUN_FILE = CANARY_DIR / "last_run.json"
EVAL_OUTPUT_DIR = CANARY_DIR / "ragas_history"

# Soglie di alert
FAITHFULNESS_THRESHOLD = 0.80    # Soglia RAGAS faithfulness
RELEVANCY_THRESHOLD = 0.70       # Soglia answer_relevancy
PROXY_SCORE_THRESHOLD = 0.45     # Soglia cosine similarity proxy
COVERAGE_THRESHOLD = 90.0        # % golden queries che trovano le collection attese

# Telegram config
TELEGRAM_OWNER_CHAT_ID = "413539912"

VERBOSE = False
DRY_RUN = False
USE_RAGAS = False


def log(msg: str) -> None:
    if VERBOSE:
        print(f"[ragas-eval] {msg}", file=sys.stderr)


def _load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    backend_env = PROJECT_ROOT / "apps" / "backend-rag" / ".env"
    if backend_env.exists():
        for line in backend_env.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def _send_telegram(text: str, bot_token: str) -> bool:
    if DRY_RUN:
        print(f"[DRY RUN] Telegram: {text[:200]}")
        return True
    if not bot_token:
        log("TELEGRAM_BOT_TOKEN mancante")
        return False
    try:
        data = urllib.parse.urlencode({
            "chat_id": TELEGRAM_OWNER_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
        }).encode()
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data, timeout=10,
        )
        return True
    except Exception as e:
        log(f"Telegram fallito: {e}")
        return False


def _load_canary_data() -> dict | None:
    """Carica dati dell'ultimo rag_canary run."""
    if not LAST_RUN_FILE.exists():
        log(f"last_run.json non trovato: {LAST_RUN_FILE}")
        return None
    try:
        data = json.loads(LAST_RUN_FILE.read_text())
        return data
    except Exception as e:
        log(f"Errore parsing last_run.json: {e}")
        return None


def _compute_proxy_metrics(canary_data: dict) -> dict[str, float]:
    """
    Calcola metriche proxy da dati rag_canary esistenti.

    Mappa:
    - avg_best_score → proxy per "answer quality" (cosine similarity)
    - pass_rate → proxy per "context recall" (% query con collection giuste)
    - score variance → indicatore stabilità
    """
    golden = canary_data.get("golden_queries", {})
    results = golden.get("results", [])

    if not results:
        return {}

    scores = [r.get("best_score", 0.0) for r in results]
    pass_rate = golden.get("pass_rate_pct", 0.0)
    avg_score = sum(scores) / len(scores) if scores else 0.0

    # Varianza (bassa = stabile, alta = inconsistente)
    variance = sum((s - avg_score) ** 2 for s in scores) / len(scores) if scores else 0.0
    std_dev = math.sqrt(variance)

    # Worst query (bottleneck)
    worst = min(results, key=lambda r: r.get("best_score", 0.0)) if results else {}

    return {
        "avg_similarity": round(avg_score, 4),
        "std_dev": round(std_dev, 4),
        "collection_coverage_pct": round(pass_rate, 1),
        "total_queries": len(results),
        "worst_score": round(worst.get("best_score", 0.0), 4),
        "worst_query": worst.get("query", ""),
    }


def _run_proxy_eval(bot_token: str) -> int:
    """
    Eval proxy (no RAGAS, no LLM) — usa dati rag_canary esistenti.
    Ritorna 0 se OK, 1 se alert.
    """
    canary_data = _load_canary_data()
    if canary_data is None:
        msg = (
            "⚠️ <b>RAGAS Eval</b> domenicale\n\n"
            "Impossibile caricare last_run.json — rag_canary non ha girato?\n"
            f"Atteso: <code>{LAST_RUN_FILE}</code>"
        )
        _send_telegram(msg, bot_token)
        return 1

    # Controlla età dati (se last_run è > 7 giorni, i dati sono stale)
    ts_str = canary_data.get("golden_queries", {}).get("timestamp", "")
    if ts_str:
        try:
            ts = datetime.fromisoformat(ts_str)
            age_days = (datetime.now(ts.tzinfo) - ts).days
            if age_days > 7:
                log(f"Dati rag_canary stale ({age_days} giorni)")
        except Exception:
            pass

    metrics = _compute_proxy_metrics(canary_data)
    if not metrics:
        return 1

    today = str(date.today())
    now_wita = datetime.now(WITA).strftime("%Y-%m-%d %H:%M WITA")

    # Salva storico
    EVAL_OUTPUT_DIR.mkdir(exist_ok=True)
    output_file = EVAL_OUTPUT_DIR / f"proxy_{today}.json"
    output = {"date": today, "mode": "proxy", "metrics": metrics, "source": "rag_canary"}
    output_file.write_text(json.dumps(output, indent=2))
    log(f"Salvato: {output_file}")

    # Analisi trend (ultime 4 domeniche)
    trend_note = _compute_trend(metrics["avg_similarity"])

    # Determina se alert necessario
    alerts: list[str] = []
    if metrics["avg_similarity"] < PROXY_SCORE_THRESHOLD:
        alerts.append(
            f"⚠️ Similarity media: <b>{metrics['avg_similarity']:.3f}</b> "
            f"(soglia: {PROXY_SCORE_THRESHOLD})"
        )
    if metrics["collection_coverage_pct"] < COVERAGE_THRESHOLD:
        alerts.append(
            f"⚠️ Collection coverage: <b>{metrics['collection_coverage_pct']:.1f}%</b> "
            f"(soglia: {COVERAGE_THRESHOLD}%)"
        )
    if metrics["std_dev"] > 0.15:
        alerts.append(
            f"⚠️ Instabilità elevata: std_dev={metrics['std_dev']:.3f} "
            "(query molto diverse tra loro)"
        )

    # Componi messaggio
    status_emoji = "⚠️" if alerts else "✅"
    worst_q = metrics["worst_query"][:60] + "..." if len(metrics["worst_query"]) > 60 else metrics["worst_query"]

    msg_lines = [
        f"📊 <b>RAG Eval Domenicale</b> — {now_wita}",
        "",
        f"{status_emoji} <b>Metriche Proxy</b> (similarity-based):",
        f"• Similarity media: <b>{metrics['avg_similarity']:.3f}</b>{trend_note}",
        f"• Coverage collection: <b>{metrics['collection_coverage_pct']:.1f}%</b>",
        f"• Stabilità: std_dev={metrics['std_dev']:.3f}",
        f"• Query peggiore: {metrics['worst_score']:.3f} — <i>{worst_q}</i>",
        f"• Totale queries: {metrics['total_queries']}",
    ]

    if alerts:
        msg_lines.append("")
        msg_lines.append("⚠️ <b>Attenzione:</b>")
        msg_lines.extend(alerts)
        msg_lines.append("")
        msg_lines.append("Azione: esegui <code>python3 scripts/rag_canary.py --verbose</code>")
    else:
        msg_lines.append("")
        msg_lines.append("Nessun intervento necessario.")

    _send_telegram("\n".join(msg_lines), bot_token)
    print(f"[ragas-eval] {now_wita} — similarity={metrics['avg_similarity']:.3f}, "
          f"coverage={metrics['collection_coverage_pct']:.1f}%, alerts={len(alerts)}")
    return 1 if alerts else 0


def _compute_trend(current_score: float) -> str:
    """Confronta con le ultime settimane per indicare trend."""
    if not EVAL_OUTPUT_DIR.exists():
        return ""
    history_files = sorted(EVAL_OUTPUT_DIR.glob("proxy_*.json"))[-4:]  # ultime 4 domeniche
    if len(history_files) < 2:
        return ""
    try:
        scores = []
        for f in history_files[:-1]:  # escludi quella appena salvata
            data = json.loads(f.read_text())
            scores.append(data.get("metrics", {}).get("avg_similarity", 0.0))
        if not scores:
            return ""
        avg_prev = sum(scores) / len(scores)
        delta = current_score - avg_prev
        if delta > 0.01:
            return f" (↑+{delta:.3f})"
        if delta < -0.01:
            return f" (↓{delta:.3f})"
        return " (→ stabile)"
    except Exception:
        return ""


def _run_ragas_eval(bot_token: str) -> int:
    """
    Full RAGAS eval — richiede ragas installato e backend accessibile.
    Interroga il backend per ogni golden query, poi valuta con RAGAS.
    """
    try:
        import ragas  # noqa: F401
        log(f"ragas version: {ragas.__version__}")
    except ImportError:
        log("ragas non installato — fallback a proxy eval")
        print("[ragas-eval] WARN: ragas non disponibile, uso proxy metrics")
        return _run_proxy_eval(bot_token)

    # TODO: implementare full RAGAS quando backend ha endpoint pubblico o service account
    # 1. Per ogni golden query: POST /api/v1/rag/query con JWT
    # 2. Raccogli answer + contexts dalla risposta
    # 3. Crea dataset RAGAS con question/answer/contexts/reference
    # 4. Esegui evaluate(dataset, metrics=[faithfulness, answer_relevancy, context_precision])
    # 5. Alert se faithfulness < FAITHFULNESS_THRESHOLD

    # Per ora: proxy eval + nota che RAGAS non è configurato
    now_wita = datetime.now(WITA).strftime("%Y-%m-%d %H:%M WITA")
    _send_telegram(
        f"ℹ️ <b>RAGAS Eval</b> — {now_wita}\n\n"
        "RAGAS installato ma backend API key non configurata.\n"
        "Esecuzione proxy eval...",
        bot_token,
    )
    return _run_proxy_eval(bot_token)


def main() -> int:
    env = _load_env()
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN") or env.get("TELEGRAM_BOT_TOKEN", "")

    if USE_RAGAS:
        return _run_ragas_eval(bot_token)
    return _run_proxy_eval(bot_token)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAGAS Eval Pipeline")
    parser.add_argument("--ragas", action="store_true", help="Full RAGAS eval (richiede ragas)")
    parser.add_argument("--dry-run", action="store_true", help="No Telegram, solo preview")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug output")
    args = parser.parse_args()
    VERBOSE = args.verbose
    DRY_RUN = args.dry_run
    USE_RAGAS = args.ragas
    sys.exit(main())
