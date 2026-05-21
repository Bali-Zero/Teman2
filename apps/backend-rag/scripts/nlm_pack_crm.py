"""nlm_pack_crm — WhatsApp → NotebookLM client dossier compiler.

Reads CRM-resolved WhatsApp conversations from Fly Postgres
(`whatsapp_message_context_enriched`), synthesizes per-client 3-layer dossiers
via local Ollama (qwen3.5:9b, temperature=0, seed=42, deterministic), merges
with approved `crm_workspace_ai_snapshots` facts, and compiles markdown
mega-files (≤400k words each) ready for NotebookLM ingestion.

Dry-run is default. `--push` opt-in pushes via `nlm source add --file`.

Usage:
    cd apps/backend-rag && source .venv/bin/activate
    PYTHONPATH=. python scripts/nlm_pack_crm.py --window-days 180

    # then to actually push to NB:
    PYTHONPATH=. python scripts/nlm_pack_crm.py --push \\
        --notebook-id 5c2c3d90-eed2-4755-86b1-269e637e51e1

Constraints (CLAUDE.md):
- Async + httpx (already done in synthesizer).
- No hardcoded secrets — DATABASE_URL via env (.env or shell export).
- Logger only, never print().
- PYTHONPATH=. required.
- Ollama local only (UU PDP / Symbiosis Law 2 — no PII to cloud LLM).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import asyncpg

from backend.services.crm.nlm_dossier_synthesizer import (
    ClientDossier,
    fetch_clients_with_wa_messages,
    fetch_messages_for_client,
    fetch_workspace_facts_for_client,
    synthesize_client_dossier,
)

logger = logging.getLogger("nlm_pack_crm")

DEFAULT_OUTPUT_DIR = Path.home() / "Desktop" / "nuzantara" / "research" / "crm"
DEFAULT_MAX_WORDS_PER_FILE = 400_000
DEFAULT_NOTEBOOK_ID = "5c2c3d90-eed2-4755-86b1-269e637e51e1"
NLM_CLI = "/Users/nuzantara/.local/bin/nlm"


def render_dossier_markdown(dossier: ClientDossier) -> str:
    """Render one dossier as a markdown section.

    Format is stable so NotebookLM can locate fields. Avoid emojis (constitution).
    """
    lines: list[str] = [
        f"## Client: {dossier.display_name} (id={dossier.client_id})",
        f"**Window**: {dossier.period_start} → {dossier.period_end} · "
        f"**Messages**: {dossier.msg_count}",
        "",
        "### Hard Facts",
    ]

    hf = dossier.hard_facts
    if hf.decisions:
        lines.append("#### Decisions")
        for d in hf.decisions:
            lines.append(f"- {d.date}: [{d.who}] {d.what}")
    if hf.documents_delivered:
        lines.append("#### Documents delivered")
        for doc in hf.documents_delivered:
            lines.append(f"- {doc.ref_date}: {doc.kind}")
    if hf.declared_deadlines:
        lines.append("#### Declared deadlines")
        for dl in hf.declared_deadlines:
            lines.append(f"- {dl.date}: {dl.what}")
    if hf.quotes_approved:
        lines.append("#### Quotes approved")
        for q in hf.quotes_approved:
            amt = f"IDR {q.amount_idr:,}".replace(",", ".") if q.amount_idr else "amount unspecified"
            lines.append(f"- {q.date}: {q.service} — {amt}")
    if not any([hf.decisions, hf.documents_delivered, hf.declared_deadlines, hf.quotes_approved]):
        lines.append("- (none extracted)")

    lines.extend(["", "### Soft Facts"])
    sf = dossier.soft_facts
    if sf.client_business_goals:
        lines.append("#### Client business goals")
        for g in sf.client_business_goals:
            lines.append(f"- {g}")
    if sf.warnings_given:
        lines.append("#### Warnings / disclaimers given to client")
        for w in sf.warnings_given:
            lines.append(f"- {w.date} [{w.topic}]: {w.note}")
    if sf.promises_sla:
        lines.append("#### Promises / SLA")
        for p in sf.promises_sla:
            lines.append(f"- {p.date} by {p.by}: {p.what}")
    if not any([sf.client_business_goals, sf.warnings_given, sf.promises_sla]):
        lines.append("- (none extracted)")

    lines.extend(["", "### Human Layer"])
    hl = dossier.human_layer
    lines.append(f"**Sentiment trend**: {hl.sentiment_trend}")
    if hl.frustration_episodes:
        lines.append("#### Frustration episodes")
        for e in hl.frustration_episodes:
            lines.append(f"- {e.date}: {e.note}")
    if hl.operator_handoffs:
        lines.append("#### Operator handoffs")
        for h in hl.operator_handoffs:
            reason = f" — {h.reason}" if h.reason else ""
            lines.append(f"- {h.date}: {h.from_operator} → {h.to_operator}{reason}")

    if dossier.workspace_facts:
        lines.extend(["", "### Workspace AI facts (CRM-approved)"])
        for f in dossier.workspace_facts:
            cat = f.get("category", "fact")
            label = f.get("label", "")
            detail = f.get("detail", "")
            lines.append(f"- [{cat}] {label}: {detail}")

    lines.extend(["", "---", ""])
    return "\n".join(lines)


def chunk_dossiers_by_word_count(
    dossiers: list[ClientDossier],
    max_words: int,
) -> list[list[ClientDossier]]:
    """Group dossiers into chunks each ≤ max_words. One dossier never split."""
    chunks: list[list[ClientDossier]] = []
    current: list[ClientDossier] = []
    current_words = 0

    for d in dossiers:
        rendered = render_dossier_markdown(d)
        word_count = len(rendered.split())

        if current and current_words + word_count > max_words:
            chunks.append(current)
            current = []
            current_words = 0

        current.append(d)
        current_words += word_count

    if current:
        chunks.append(current)
    return chunks


def write_mega_file(
    dossiers: list[ClientDossier],
    *,
    output_path: Path,
    batch_num: int,
    total_batches: int,
    window_days: int,
) -> None:
    """Compile one mega-file from a list of dossiers."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    total_msgs = sum(d.msg_count for d in dossiers)

    header = "\n".join([
        f"# Bali Zero CRM WhatsApp Dossier — batch {batch_num:02d}/{total_batches:02d}",
        f"# Generated: {today} (UTC)",
        f"# Window: last {window_days} days",
        f"# Clients in this batch: {len(dossiers)}",
        f"# Total messages synthesized: {total_msgs:,}".replace(",", "."),
        "# Source: whatsapp_message_context_enriched (CRM-resolved phone matches only)",
        "# Synthesis: Ollama qwen3.5:9b (local, temperature=0, seed=42, deterministic)",
        "# PII: NPWP/passport/NIK/NIB/full-phone/email/EFIN masked pre-LLM",
        "",
        "---",
        "",
    ])

    body = "\n".join(render_dossier_markdown(d) for d in dossiers)
    output_path.write_text(header + body, encoding="utf-8")
    logger.info(
        "Wrote %s (%d clients, %.1fKB)",
        output_path,
        len(dossiers),
        output_path.stat().st_size / 1024,
    )


def push_file_to_notebooklm(
    file_path: Path,
    *,
    notebook_id: str,
    title: str,
) -> bool:
    """Push one mega-file to NotebookLM via nlm CLI. Returns True on success."""
    cmd = [
        NLM_CLI, "source", "add", notebook_id,
        "--file", str(file_path),
        "--title", title,
        "--wait",
        "--wait-timeout", "600",
    ]
    logger.info("nlm push: %s → notebook %s", file_path.name, notebook_id)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        if result.returncode != 0:
            logger.error(
                "nlm push failed (exit %d): stderr=%s",
                result.returncode,
                result.stderr.strip(),
            )
            return False
        logger.info("nlm push OK: %s", result.stdout.strip()[:200])
        return True
    except subprocess.TimeoutExpired:
        logger.error("nlm push timed out after 900s")
        return False
    except FileNotFoundError:
        logger.error("nlm CLI not found at %s", NLM_CLI)
        return False


def _resolve_database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        logger.error(
            "DATABASE_URL not set. Export it before running, e.g.:\n"
            "  export DATABASE_URL=postgres://USER:PASS@localhost:15432/nuzantara_rag?sslmode=disable"
        )
        sys.exit(2)
    return url


async def build_all_dossiers(
    conn: asyncpg.Connection,
    *,
    window_days: int,
    limit_clients: int | None,
    model: str,
    timing_log_path: Path | None = None,
    claude_fallback: bool = False,
) -> list[ClientDossier]:
    """For each CRM-resolved client with WA activity, synthesize a dossier."""
    import time
    clients = await fetch_clients_with_wa_messages(conn, window_days=window_days)
    if limit_clients is not None:
        clients = clients[:limit_clients]
    logger.info("Found %d CRM-resolved clients with WA activity in last %dd",
                len(clients), window_days)

    dossiers: list[ClientDossier] = []
    timings: list[dict[str, Any]] = []
    for idx, c in enumerate(clients, 1):
        client_id = int(c["client_id"])
        display = c["display_name"] or f"client_{client_id}"
        logger.info("[%d/%d] synthesizing client_id=%s (%s) msgs~%d model=%s",
                    idx, len(clients), client_id, display, c["msg_count"], model)

        messages = await fetch_messages_for_client(
            conn, client_id=client_id, window_days=window_days
        )
        if not messages:
            logger.info("  → 0 messages after fetch, skipping")
            continue

        workspace = await fetch_workspace_facts_for_client(conn, client_id=client_id)

        t0 = time.perf_counter()
        dossier = await synthesize_client_dossier(
            client_id=client_id,
            display_name=display,
            messages=messages,
            workspace_facts=workspace,
            model=model,
            claude_fallback=claude_fallback,
        )
        elapsed = time.perf_counter() - t0
        timings.append({
            "client_id": client_id,
            "display_name": display,
            "msg_count": len(messages),
            "elapsed_s": round(elapsed, 2),
            "ok": dossier is not None,
        })
        logger.info("  → elapsed=%.2fs ok=%s", elapsed, dossier is not None)
        if dossier is None:
            continue
        dossiers.append(dossier)

    if timing_log_path:
        import json as _json
        timing_log_path.parent.mkdir(parents=True, exist_ok=True)
        timing_log_path.write_text(
            _json.dumps({"model": model, "results": timings}, indent=2),
            encoding="utf-8",
        )
        logger.info("Timing log written to %s", timing_log_path)

    return dossiers


async def main_async(args: argparse.Namespace) -> int:
    db_url = _resolve_database_url()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    model_slug = args.model.replace(":", "_")

    timing_log = output_dir / f"{today}-timing-{model_slug}.json"
    conn = await asyncpg.connect(db_url)
    try:
        dossiers = await build_all_dossiers(
            conn,
            window_days=args.window_days,
            limit_clients=args.limit_clients,
            model=args.model,
            timing_log_path=timing_log,
            claude_fallback=args.claude_fallback,
        )
    finally:
        await conn.close()

    if not dossiers:
        logger.warning("Zero dossiers produced — nothing to write")
        return 1

    chunks = chunk_dossiers_by_word_count(dossiers, args.max_words_per_file)
    total_batches = len(chunks)
    logger.info("Compiled %d dossier(s) into %d batch file(s)", len(dossiers), total_batches)

    written: list[Path] = []
    for i, chunk in enumerate(chunks, 1):
        fname = f"{today}-wa-dossier-{model_slug}-batch-{i:02d}.txt"
        path = output_dir / fname
        write_mega_file(
            chunk,
            output_path=path,
            batch_num=i,
            total_batches=total_batches,
            window_days=args.window_days,
        )
        if not path.exists():
            logger.error("anti-hallucination check failed: %s missing after write", path)
            return 2
        written.append(path)

    if args.push:
        logger.info("Push mode: uploading %d file(s) to notebook %s",
                    len(written), args.notebook_id)
        ok = 0
        for path in written:
            title = path.stem
            if push_file_to_notebooklm(path, notebook_id=args.notebook_id, title=title):
                ok += 1
        logger.info("Pushed %d/%d files to NotebookLM", ok, len(written))
        if ok != len(written):
            return 3
    else:
        logger.info(
            "Dry-run complete. To push: rerun with --push --notebook-id %s",
            args.notebook_id,
        )

    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="WhatsApp → NotebookLM client dossier compiler")
    p.add_argument("--window-days", type=int, default=180,
                   help="Look-back window in days (default 180 = 6 months)")
    p.add_argument("--max-words-per-file", type=int, default=DEFAULT_MAX_WORDS_PER_FILE,
                   help=f"Max words per mega-file (default {DEFAULT_MAX_WORDS_PER_FILE})")
    p.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR),
                   help=f"Output directory (default {DEFAULT_OUTPUT_DIR})")
    p.add_argument("--limit-clients", type=int, default=None,
                   help="Process at most N clients (debugging)")
    p.add_argument("--model", type=str, default="qwen3.5:9b",
                   help="Ollama model tag (e.g. qwen3.5:9b, qwen3.6:27b)")
    p.add_argument("--claude-fallback", action="store_true",
                   help="Use Claude Haiku 4.5 OAuth CLI fallback when Ollama times out "
                        "(extra PII-strip applied — Symbiosis Law 2 partial compliance)")
    p.add_argument("--push", action="store_true",
                   help="Push compiled files to NotebookLM (default: dry-run)")
    p.add_argument("--notebook-id", type=str, default=DEFAULT_NOTEBOOK_ID,
                   help="NotebookLM notebook UUID")
    p.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    return p


def main() -> int:
    args = build_arg_parser().parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
