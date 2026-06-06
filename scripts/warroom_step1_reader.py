#!/usr/bin/env python3
"""War Room — Step 1: legge i candidati freschi da intel_items (Intel Lake A),
li giudica con un LLM (Claude a quota MAX via SDK auth_token), produce una shortlist.

Design + verdetto panel 3-LLM: research/marketing/2026-06-06-warroom-step1-intel-lake-reader.md

Catena:
  intel_items (Fly) ─SELECT finestra DATE-WITA, NOT probe, tutti i producer, NULL→first_seen
    → pre-score (intel_prescore, SOLO ordinamento; circuit-breaker solo se volume anomalo)
    → giudizio LLM a CHUNK 8 con RUBRICA ASSOLUTA, temperature=0, cache per content_hash
    → shortlist (relevance>=THRESHOLD + dedup canonical_url + discarded[] audit)
    → scrittura ATOMICA (tmp+rename) + lock file

NON scrive war_room_drafts (è lo Step 2). NON pubblica nulla (Legge 5). Legge solo
news pubbliche (title/summary) → cloud LLM OK (Law 2: nessun dato cliente).

LLM: anthropic.Anthropic(auth_token=<keychain accessToken>) — header Bearer = MAX, $0.
     MAI api_key (X-Api-Key = paid, bandito). instructor per JSON validato + retry.

Uso:
    python scripts/warroom_step1_reader.py [--window-days 3] [--dry-run] [--limit N]
                                           [--no-llm] [--out DIR] [--chunk 8]
    --dry-run : esegue fetch+prescore+LLM ma stampa la shortlist su stdout, non scrive file.
    --no-llm  : solo fetch+prescore (debug del SELECT/ordinamento, zero chiamate LLM).
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "lib"))

import asyncpg  # noqa: E402
import intel_prescore  # noqa: E402  (modulo condiviso)

logger = logging.getLogger("warroom.step1")

# ---- Parametri (panel-fissati) ---------------------------------------------
DEFAULT_WINDOW_DAYS = 3
MAX_ITEMS = int(os.environ.get("WR_STEP1_MAX_ITEMS", "42"))   # circuit-breaker volume (media×2.5)
DEFAULT_CHUNK = 8                                              # chunk LLM (panel: 8-10)
RELEVANCE_THRESHOLD = int(os.environ.get("WR_STEP1_RELEVANCE_MIN", "6"))
WITA = timezone.utc  # placeholder; la finestra DATE-WITA è in SQL via AT TIME ZONE
SERVICE_LINES = ("visa", "company", "tax", "property", "regulatory", "none")
LLM_MODEL = os.environ.get("WR_STEP1_MODEL", "claude-sonnet-4-5-20250929")
OUT_DIR_DEFAULT = Path.home() / "Desktop" / "nuzantara" / "var" / "war_room"


# ---- Token MAX dal Keychain (auto-refresh dal CLI), fallback env ------------
def load_oauth_token() -> str:
    """accessToken OAuth dal Keychain del CLI claude. MAI loggato. Fallback env var."""
    try:
        raw = subprocess.run(
            ["security", "find-generic-password",
             "-s", "Claude Code-credentials", "-a", os.environ.get("USER", ""), "-w"],
            capture_output=True, text=True, check=True, timeout=10,
        ).stdout.strip()
        tok = json.loads(raw)["claudeAiOauth"]["accessToken"]
        if tok:
            return tok
    except Exception as exc:  # noqa: BLE001
        logger.debug("keychain token read failed (%s), trying env", type(exc).__name__)
    tok = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
    if not tok:
        raise RuntimeError("nessun token MAX: né Keychain 'Claude Code-credentials' né CLAUDE_CODE_OAUTH_TOKEN")
    return tok


# ---- DSN (proxy Fly), mai loggato ------------------------------------------
def load_dsn() -> str:
    env_path = _REPO_ROOT / "apps" / "backend-rag" / ".env"
    for line in env_path.read_text().splitlines():
        if line.startswith("DATABASE_URL="):
            url = line.split("=", 1)[1].strip().strip('"').strip("'")
            # punta al proxy locale flyctl
            return re.sub(r"@[^/]+/", "@127.0.0.1:15432/", url)
    raise RuntimeError(f"DATABASE_URL non trovato in {env_path}")


# ---- STADIO 1: FETCH (finestra DATE-WITA + fallback NULL→first_seen) --------
FETCH_SQL = """
SELECT id, canonical_url, content_hash, title, summary, source_domain,
       language, jurisdiction, topic_tags, routing_status, confidence_score,
       published_at, first_seen_at
FROM intel_items
WHERE is_probe_sandbox = false
  AND COALESCE(published_at, first_seen_at)
      >= ((now() AT TIME ZONE 'Asia/Makassar')::date - ($1::int) * interval '1 day')
ORDER BY COALESCE(published_at, first_seen_at) DESC
"""


async def fetch_candidates(conn: asyncpg.Connection, window_days: int) -> list[dict[str, Any]]:
    rows = await conn.fetch(FETCH_SQL, window_days)
    out: list[dict[str, Any]] = []
    null_pub = 0
    for r in rows:
        d = dict(r)
        if d.get("published_at") is None:
            null_pub += 1
        # serializza datetime per il JSON downstream
        for k in ("published_at", "first_seen_at"):
            if isinstance(d.get(k), datetime):
                d[k] = d[k].astimezone(timezone.utc).isoformat()
        out.append(d)
    logger.info("fetch: %d candidati freschi (%d con published_at NULL → fallback first_seen)",
                len(out), null_pub)
    return out


# ---- STADIO 2: GIUDIZIO LLM (chunk, rubrica assoluta, temp=0, cache) --------
RUBRIC = (
    "Sei l'editor di una War Room che produce caroselli Instagram per Bali Zero "
    "(agenzia immigration/company/tax/property in Indonesia). Valuta OGNI articolo "
    "INDIPENDENTEMENTE dagli altri del lotto, con questa rubrica ASSOLUTA di relevance:\n"
    "  0-3 = fuori-scope Bali Zero (sport, cronaca generica, turismo non-regolatorio)\n"
    "  4-6 = tangenziale (tocca l'Indonesia/Bali ma non un servizio BZ diretto)\n"
    "  7-8 = core service-line (visa/KITAS, PT PMA/KBLI, tax, property: azionabile per clienti)\n"
    "  9-10 = breaking + azionabile (nuova norma, scadenza, enforcement che i clienti DEVONO sapere)\n"
    "service_line ∈ {visa, company, tax, property, regulatory, none}. "
    "audience = a chi parla (es. 'foreign investors', 'KITAS holders', 'PT PMA owners'). "
    "rationale = UNA riga sul perché quel punteggio. "
    "Un titolo regolatorio asciutto (es. 'PMK 131/2024') può valere 9 anche senza keyword Bali."
)


def _item_for_llm(it: dict[str, Any]) -> dict[str, str]:
    return {
        "id": str(it["id"]),
        "title": it.get("title") or "",
        "summary": (it.get("summary") or "")[:1200],
        "source_domain": it.get("source_domain") or "",
        "language": it.get("language") or "",
    }


def _cache_key(it: dict[str, Any]) -> str:
    """Cache per content_hash se presente, altrimenti canonical_url, altrimenti title-hash."""
    base = it.get("content_hash") or it.get("canonical_url") or it.get("title") or ""
    return f"{base}|{RELEVANCE_THRESHOLD}|{LLM_MODEL}|rubric-v1"


def _build_client(token: str):
    """anthropic.Anthropic(auth_token=...) — client RAW (header Bearer = MAX). MAI api_key.

    NB: usiamo sempre il client anthropic PURO perché il path di giudizio implementato
    è `_judge_chunk_raw` (prompt→JSON-array→parse), che chiama `messages.create` standard.
    instructor.from_anthropic() ritornerebbe un client il cui `messages.create` ESIGE
    `response_model=` → `_judge_chunk_raw` (che non lo passa) fallirebbe ogni chunk
    (bug collaudo 2026-06-06: instructor installato → judged:0). Per adottare instructor
    in futuro serve un path dedicato `_judge_chunk_instructor(client, chunk, response_model=ChunkVerdicts)`
    con un BaseModel Pydantic — non riusare _judge_chunk_raw con un client patchato.
    """
    os.environ.pop("ANTHROPIC_API_KEY", None)  # defense-in-depth (Golden Rule)
    import anthropic
    return ("raw", anthropic.Anthropic(auth_token=token))


def _judge_chunk_raw(client, chunk: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Giudizio a chunk: prompt JSON + parse robusto (client anthropic puro)."""
    payload = json.dumps(chunk, ensure_ascii=False, indent=1)
    prompt = (
        f"{RUBRIC}\n\nValuta questi {len(chunk)} articoli. Rispondi SOLO con un array JSON, "
        f"un oggetto per articolo, nello stesso ordine, con chiavi esatte: "
        f'{{"id","relevance","service_line","audience","rationale"}}. '
        f"relevance intero 0-10. NESSUN testo fuori dal JSON.\n\nARTICOLI:\n{payload}"
    )
    resp = client.messages.create(
        model=LLM_MODEL, max_tokens=2000, temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if not m:
        raise ValueError(f"LLM non ha prodotto JSON array: {text[:120]}")
    return json.loads(m.group(0))


def judge_items(items: list[dict[str, Any]], token: str, chunk_size: int,
                cache: dict[str, dict]) -> dict[str, dict[str, Any]]:
    """Ritorna {item_id: {relevance, service_line, audience, rationale}}. Usa cache."""
    mode, client = _build_client(token)
    logger.info("LLM client mode=%s model=%s chunk=%d", mode, LLM_MODEL, chunk_size)
    verdicts: dict[str, dict[str, Any]] = {}

    # split tra cached e da-giudicare
    to_judge = []
    for it in items:
        ck = _cache_key(it)
        if ck in cache:
            verdicts[str(it["id"])] = cache[ck]
        else:
            to_judge.append(it)
    logger.info("LLM: %d da cache, %d da giudicare", len(items) - len(to_judge), len(to_judge))

    for i in range(0, len(to_judge), chunk_size):
        batch = to_judge[i:i + chunk_size]
        llm_in = [_item_for_llm(it) for it in batch]
        try:
            raw = _judge_chunk_raw(client, llm_in)
        except Exception as exc:  # noqa: BLE001
            logger.error("chunk %d-%d LLM fallito: %s", i, i + len(batch), exc)
            continue
        by_id = {str(r.get("id")): r for r in raw if isinstance(r, dict)}
        for it in batch:
            iid = str(it["id"])
            r = by_id.get(iid)
            if not r:
                continue
            v = {
                "relevance": _clamp_int(r.get("relevance"), 0, 10),
                "service_line": r.get("service_line") if r.get("service_line") in SERVICE_LINES else "none",
                "audience": str(r.get("audience") or "")[:120],
                "rationale": str(r.get("rationale") or "")[:240],
            }
            verdicts[iid] = v
            cache[_cache_key(it)] = v
    return verdicts


def _clamp_int(v: Any, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(round(float(v)))))
    except (TypeError, ValueError):
        return lo


# ---- STADIO 3: SHORTLIST + scrittura atomica + lock ------------------------
def build_shortlist(candidates: list[dict[str, Any]],
                    verdicts: dict[str, dict[str, Any]],
                    prescores: dict[str, float]) -> dict[str, Any]:
    shortlist, discarded = [], []
    seen_urls: set[str] = set()
    for it in candidates:
        iid = str(it["id"])
        v = verdicts.get(iid)
        if not v:
            continue
        rec = {
            "item_id": iid,
            "title": it.get("title"),
            "canonical_url": it.get("canonical_url"),
            "source_domain": it.get("source_domain"),
            "published_at": it.get("published_at"),
            "prescore": round(prescores.get(iid, 0.0), 1),
            "llm": v,
        }
        if v["relevance"] >= RELEVANCE_THRESHOLD:
            url = it.get("canonical_url") or iid
            if url in seen_urls:      # dedup (verificato 64/64 popolato, 0 dup, ma difensivo)
                continue
            seen_urls.add(url)
            shortlist.append(rec)
        else:
            discarded.append(rec)
    shortlist.sort(key=lambda r: r["llm"]["relevance"], reverse=True)
    return {
        "shortlist": shortlist,
        "discarded_below_threshold": discarded,
        "relevance_threshold": RELEVANCE_THRESHOLD,
    }


def write_atomic(out_dir: Path, day: str, doc: dict[str, Any]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"shortlist-{day}.json"
    fd, tmp = tempfile.mkstemp(dir=str(out_dir), prefix=".shortlist-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
        os.replace(tmp, target)   # rename atomico (last-write-wins deterministico)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return target


def load_existing_cache(out_dir: Path, day: str) -> dict[str, dict]:
    """Riusa i verdetti LLM già scritti oggi (idempotenza: doppio-run converge)."""
    f = out_dir / f"shortlist-{day}.json"
    cache: dict[str, dict] = {}
    if not f.exists():
        return cache
    try:
        prev = json.loads(f.read_text())
        for rec in prev.get("shortlist", []) + prev.get("discarded_below_threshold", []):
            # ricostruiamo la chiave dal canonical_url (content_hash non è nel file output)
            url = rec.get("canonical_url") or rec.get("item_id")
            cache[f"{url}|{RELEVANCE_THRESHOLD}|{LLM_MODEL}|rubric-v1"] = rec["llm"]
    except Exception:  # noqa: BLE001
        pass
    return cache


# ---- Orchestrazione ---------------------------------------------------------
async def run(args: argparse.Namespace) -> int:
    run_ts = datetime.now(timezone.utc)             # congelato una volta (panel #6)
    day = run_ts.astimezone().strftime("%Y-%m-%d")  # giorno locale per il nome file
    out_dir = Path(args.out) if args.out else OUT_DIR_DEFAULT

    # lock file (evita due run concorrenti che si sovrascrivono)
    lock = out_dir / ".step1.lock"
    out_dir.mkdir(parents=True, exist_ok=True)
    if lock.exists() and not args.dry_run:
        age = run_ts.timestamp() - lock.stat().st_mtime
        if age < 1800:  # 30 min
            logger.error("lock attivo (%ds), un'altra run è in corso — esco", int(age))
            return 1
    if not args.dry_run:
        lock.write_text(str(os.getpid()))

    try:
        conn = await asyncio.wait_for(asyncpg.connect(load_dsn()), timeout=20)
        try:
            candidates = await fetch_candidates(conn, args.window_days)
        finally:
            await conn.close()

        if args.limit:
            candidates = candidates[:args.limit]
        if not candidates:
            logger.warning("zero candidati freschi — niente shortlist")
            return 0

        # STADIO 1: pre-score (ordinamento, NON gate) + circuit-breaker solo su volume
        scored = intel_prescore.order_candidates(candidates, now=run_ts)
        scored = intel_prescore.circuit_break_by_volume(scored, max_items=MAX_ITEMS)
        ordered = [it for (it, _s, _d) in scored]
        prescores = {str(it["id"]): s for (it, s, _d) in scored}
        # fresh+tier = criterio effettivo di selezione quando il circuit-breaker scatta
        fresh_tier = {
            str(it["id"]): round(d["rules"]["freshness_points"] + d["rules"]["tier_points"], 1)
            for (it, _s, d) in scored
        }
        logger.info("pre-score: %d candidati passano all'LLM (MAX_ITEMS=%d)", len(ordered), MAX_ITEMS)

        if args.no_llm:
            doc = {
                "generated_at": run_ts.isoformat(), "window_days": args.window_days,
                "candidates_considered": len(candidates), "judged": 0,
                "note": "--no-llm: solo fetch+prescore. 'prescore'=score totale (keyword inclusa); "
                        "'fresh_tier'=freshness+tier = criterio di selezione quando >MAX_ITEMS.",
                "prescored": [{"item_id": str(it["id"]), "title": it.get("title"),
                               "prescore": round(prescores[str(it["id"])], 1),
                               "fresh_tier": fresh_tier[str(it["id"])]} for it in ordered],
            }
        else:
            cache = load_existing_cache(out_dir, day)
            token = load_oauth_token()
            verdicts = judge_items(ordered, token, args.chunk, cache)
            sl = build_shortlist(ordered, verdicts, prescores)
            doc = {
                "generated_at": run_ts.isoformat(),
                "window_days": args.window_days,
                "candidates_considered": len(candidates),
                "judged": len(verdicts),
                "model": LLM_MODEL,
                **sl,
            }

        if args.dry_run:
            print(json.dumps(doc, ensure_ascii=False, indent=2))
            logger.info("dry-run: shortlist su stdout, nessun file scritto")
            return 0

        target = write_atomic(out_dir, day, doc)
        n = len(doc.get("shortlist", doc.get("prescored", [])))
        logger.info("shortlist scritta: %s (%d item)", target, n)
        return 0
    finally:
        if not args.dry_run and lock.exists():
            lock.unlink()


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler()],
    )


def main() -> int:
    _configure_logging()
    ap = argparse.ArgumentParser(description="War Room Step 1 — intel_items → shortlist LLM")
    ap.add_argument("--window-days", type=int, default=DEFAULT_WINDOW_DAYS)
    ap.add_argument("--chunk", type=int, default=DEFAULT_CHUNK)
    ap.add_argument("--limit", type=int, default=0, help="limita i candidati (debug)")
    ap.add_argument("--dry-run", action="store_true", help="stampa su stdout, non scrive file")
    ap.add_argument("--no-llm", action="store_true", help="solo fetch+prescore, zero LLM")
    ap.add_argument("--out", type=str, default="", help="dir output (default ~/Desktop/.../var/war_room)")
    args = ap.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
