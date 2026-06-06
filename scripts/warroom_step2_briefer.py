#!/usr/bin/env python3
"""War Room — Step 2: shortlist → draft briefato (B-FUSIONE).

Prende un item della shortlist (Step 1, già APPROVATO da umano — gate §8.7), lo arricchisce
fondendo i FATTI FRESCHI della news col GROUNDING VERBATIM di NotebookLM, e scrive un
`brief_json` esteso in `war_room_drafts`.

Design + verdetto panel 4-LLM (2026-06-06):
  research/marketing/2026-06-06-warroom-step2-design.md  (§7 verdetto, §8 7 decisioni chiuse)

Le 7 decisioni implementate qui:
  D1 (Q1) FUSIONE IBRIDA — l'LLM scrive SOLO la prosa narrativa (the_facts/bali_zero_take/...).
          Provenienza, scelta news-vs-NB, freshness_override e i campi-safety (taboo/lexicon/
          citations/numbers) sono COPIATI VERBATIM da NB con codice deterministico. L'LLM non
          tocca mai una citazione o un numero strutturale.
  D2 (Q2) NEWS-CORRECTOR — la news fresca corregge i fatti datati NB stale; mai bloccare sull'NB;
          emette fusion_meta.nb_staleness_days + freshness_overrides[].
  D3 (Q3) CONFLITTO → BLOCCA — conflitto sostanziale ⇒ status='needs_review_conflict' (il drafter
          cron lo salta). Solo i puliti diventano 'briefed'.
  D4 (Q4) 1-BY-1 + CAP + STOP-PULITO — processa in ordine di rilevanza, cap WR2_BRIEF_MAX_PER_RUN
          (default 3), stop pulito su quota (mai mezza coda di brief falliti).
  D5 (Q5) IDEMPOTENZA + RE-BRIEF — skip se canonical_url già briefato in QUALSIASI data, MA se il
          contenuto è mutato (content_hash o published_at cambiati) ⇒ re-brief UPSERT (bump revision).
          Risolve il caso PP 20/2026 (stesso URL, "in attesa firma" → "emanata").
  D6 (Q6) RAIL DENTRO ENRICHMENT — oltre a persistere i campi ricchi, INIETTA taboo/citazioni/numeri
          DENTRO `enrichment` (il canale che il drafter GIA legge): the_facts incorpora le citazioni
          verbatim, una riga 'NON usare: <taboo>', i numeri chiave nel testo. Zero modifiche al drafter.
  D7 (Q6) GATE UMANO PRIMA — gira solo su item APPROVATI (--approved / --item-id), non auto su tutta
          la shortlist.

Vincoli (hard, vedi design §6):
  - Claude quota MAX via SDK auth_token (HTTP Bearer), MAI api_key (pay-as-you-go). Riusa il client
    RAW dello Step 1. ⚠️ Il CLAUDE.md di progetto §5 dice ancora "SDK BANNED" — conflitto da
    riconciliare pre-merge (auth_token=MAX OAuth OK; api_key=bandito). Vedi design §6.
  - Law 2: news pubblica + NB conoscenza operativa (non PII) → cloud OK.
  - Legge 5: scrive un draft, NON pubblica. Drafter + review-gate restano a valle.
  - Anti-allucinazione: conflitto news/NB ⇒ NON inventare la sintesi, status needs_review_conflict.

Reuse-first (design §5):
  - load_oauth_token / load_dsn / _build_client  ← [RIUSA] da warroom_step1_reader.py (pattern identico)
  - forma brief_json + INSERT war_room_drafts     ← [FORKA-E-ADATTA] da wr2_topic_selector.py:605
  - wr2-brief-interpreter (NB ground-truth)        ← [INVOCA] — qui via stub iniettabile (vedi §brief)

NB SULL'INVOCAZIONE brief-interpreter: questo script è un processo Python, NON una sessione Claude
con l'Agent tool. NON può dispatchare il subagent wr2-brief-interpreter da solo. Due modalità:
  (a) --nb-brief <file.json>  : il grounding NB è prodotto a monte (dall'orchestratore Claude che
      invoca il subagent) e passato come file. Modalità di produzione.
  (b) --no-nb                  : salta il grounding NB (fusione degradata = solo news). Per collaudo
      della pipeline DB/fusione-prosa senza NB.
Così la responsabilità "interrogare NotebookLM" resta dell'orchestratore (Contract NB), e questo
script resta un puro fonditore+persister deterministico+1-LLM-call-prosa.
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("warroom.step2")

_REPO_ROOT = Path(__file__).resolve().parents[1]

# --- Costanti (panel-derived) ------------------------------------------------
MAX_PER_RUN = int(os.environ.get("WR2_BRIEF_MAX_PER_RUN", "3"))  # D4 cap
LLM_MODEL = os.environ.get("WR2_BRIEF_MODEL", "claude-sonnet-4-5-20250929")
OUT_DIR_DEFAULT = _REPO_ROOT / "var" / "war_room"

# status separati (D3 — separazione storage/readiness)
STATUS_READY = "briefed"               # il drafter cron consuma SOLO questo
STATUS_CONFLICT = "needs_review_conflict"  # bloccato, attende revisione umana

# Stadio 3: SQL per leggere il summary COMPLETO dal DB (lo shortlist ha summary troncato)
FETCH_FULL_SQL = """
SELECT id, canonical_url, content_hash, title, summary, source_domain,
       published_at, first_seen_at, topic_tags
FROM intel_items
WHERE id = $1::uuid
"""

# D5: esiste già un draft per questo canonical_url? in QUALSIASI data.
DEDUP_SQL = """
SELECT id, status,
       brief_json->>'content_hash'  AS prev_hash,
       brief_json->>'published_at'  AS prev_published,
       COALESCE((brief_json->>'revision')::int, 1) AS revision
FROM war_room_drafts
WHERE brief_json->>'canonical_url' = $1
ORDER BY created_at DESC
LIMIT 1
"""

INSERT_SQL = """
INSERT INTO war_room_drafts (topic, register, status, brief_json)
VALUES ($1, NULL, $2, $3::jsonb)
RETURNING id
"""

# D5 re-brief: aggiorna la riga esistente (UPSERT manuale) bump revision
UPDATE_SQL = """
UPDATE war_room_drafts
SET status = $2, brief_json = $3::jsonb, updated_at = now()
WHERE id = $1
RETURNING id
"""


# ============================================================================
# RIUSO da Step 1 — token / DSN / client (pattern identico, vedi warroom_step1_reader.py)
# ============================================================================
def load_oauth_token() -> str:
    """accessToken OAuth MAX. MAI loggato. Ordine: Keychain → ~/.claude/.credentials.json → env.

    Sul Pro (SSH headless) il Keychain è bloccato: il token vive nel file
    ~/.claude/.credentials.json (cicatrice 'keychain SSH-locked sul Pro'). Per questo proviamo
    il file PRIMA della env var. MAI stampare il token.
    """
    # 1) Keychain (macchina interactive)
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
        logger.debug("keychain token read failed (%s), trying credentials file", type(exc).__name__)
    # 2) ~/.claude/.credentials.json (Pro headless — Keychain SSH-locked)
    try:
        cred = Path.home() / ".claude" / ".credentials.json"
        if cred.exists():
            tok = json.loads(cred.read_text())["claudeAiOauth"]["accessToken"]
            if tok:
                return tok
    except Exception as exc:  # noqa: BLE001
        logger.debug("credentials file read failed (%s), trying env", type(exc).__name__)
    # 3) env var
    tok = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
    if not tok:
        raise RuntimeError("nessun token MAX: né Keychain, né ~/.claude/.credentials.json, né CLAUDE_CODE_OAUTH_TOKEN")
    return tok


def load_dsn() -> str:
    env_path = _REPO_ROOT / "apps" / "backend-rag" / ".env"
    for line in env_path.read_text().splitlines():
        if line.startswith("DATABASE_URL="):
            url = line.split("=", 1)[1].strip().strip('"').strip("'")
            return re.sub(r"@[^/]+/", "@127.0.0.1:15432/", url)
    raise RuntimeError(f"DATABASE_URL non trovato in {env_path}")


def _build_client(token: str):
    """anthropic.Anthropic(auth_token=...) — client RAW (header Bearer = MAX). MAI api_key.

    Identico allo Step 1: client PURO, path prompt→testo via messages.create. NON instructor
    (richiederebbe response_model). Vedi warroom_step1_reader._build_client per la cicatrice.
    """
    os.environ.pop("ANTHROPIC_API_KEY", None)  # defense-in-depth (Golden Rule #6)
    import anthropic
    return anthropic.Anthropic(auth_token=token)


# ============================================================================
# Helpers deterministici (D1 — niente LLM qui)
# ============================================================================
def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _content_hash(title: str, summary: str) -> str:
    """Hash deterministico del contenuto news (D5 — discrimina 'contenuto mutato')."""
    h = hashlib.sha256()
    h.update((title or "").strip().encode("utf-8"))
    h.update(b"\x00")
    h.update((summary or "").strip().encode("utf-8"))
    return h.hexdigest()


def _nb_staleness_days(nb_brief: dict[str, Any], news_published: Optional[datetime]) -> Optional[int]:
    """D2: delta giorni tra la data-snapshot più recente delle source NB e la pubblicazione news.

    Il brief-interpreter può fornire `nb_snapshot_date` (la data più recente delle sue source).
    Se assente, ritorna None (staleness ignota, non bloccante).
    """
    snap = _parse_dt(nb_brief.get("nb_snapshot_date"))
    if not snap or not news_published:
        return None
    return max(0, (news_published - snap).days)


def load_nb_brief(path: Optional[str]) -> dict[str, Any]:
    """Carica il grounding NB prodotto a monte dal subagent wr2-brief-interpreter (modalità a).

    Schema atteso (campi tutti opzionali — degrada, mai eccezione):
      key_facts[], regulatory_citations_verbatim[], key_numbers[], bilingual_lexicon[],
      taboo_check[], archetype, tone_register, hook_angle, nb_sources[], nb_snapshot_date
    """
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        raise RuntimeError(f"--nb-brief file non trovato: {path}")
    data = json.loads(p.read_text())
    if not isinstance(data, dict):
        raise RuntimeError(f"--nb-brief deve essere un oggetto JSON, trovato {type(data).__name__}")
    return data


# ============================================================================
# D6 — iniezione rail dentro enrichment (deterministica)
# ============================================================================
def _inject_rails_into_facts(prose_facts: str, nb_brief: dict[str, Any]) -> str:
    """Incorpora citazioni verbatim + numeri chiave + taboo DENTRO the_facts (il drafter li vede).

    Il drafter legge solo `enrichment.the_facts` (oltre ad altri campi enrichment); NON legge
    i campi ricchi top-level. Quindi i guardrail DEVONO arrivare qui dentro o sono invisibili.
    """
    parts = [prose_facts.strip()] if prose_facts and prose_facts.strip() else []

    cites = [c for c in (nb_brief.get("regulatory_citations_verbatim") or []) if str(c).strip()]
    if cites:
        parts.append("Riferimenti normativi (verbatim, citare senza parafrasare): "
                      + " · ".join(str(c).strip() for c in cites[:8]))

    nums = [str(n).strip() for n in (nb_brief.get("key_numbers") or []) if str(n).strip()]
    if nums:
        parts.append("Numeri chiave (riportare esatti): " + ", ".join(nums[:12]))

    taboos = [str(t).strip() for t in (nb_brief.get("taboo_check") or []) if str(t).strip()]
    if taboos:
        parts.append("NON usare / evitare: " + " ; ".join(taboos[:8]))

    return "\n\n".join(parts)


# ============================================================================
# STADIO 3 — fusione (1 sola LLM call: SOLO prosa; resto deterministico)
# ============================================================================
FUSION_PROMPT = """Sei l'analista editoriale di Bali Zero (consulenza immigrazione/società/tax/property in Indonesia).
Devi scrivere la PROSA di un brief per un carosello Instagram, fondendo due fonti su uno stesso tema.

FONTE A — NOTIZIA FRESCA (fatti aggiornati, può avere lo stato corrente di una norma):
Titolo: {news_title}
Testo: {news_summary}
Data pubblicazione: {news_published}

FONTE B — GROUND TRUTH NotebookLM (profondità normativa, può essere DATATA):
Fatti chiave: {nb_key_facts}
Snapshot NB: {nb_snapshot}

REGOLE DI FUSIONE (vincolanti):
1. Per FATTI DATATI/PROCEDURALI (stato di una norma, se è emanata, numeri, scadenze): la NOTIZIA
   FRESCA vince se più recente del ground-truth NB. Non ripetere lo stato vecchio dell'NB se la news lo aggiorna.
2. NON inventare. Se news e NB si contraddicono su un FATTO SOSTANZIALE (es. una norma è emanata
   oppure no), NON scegliere a caso e NON sintetizzare: scrivi che le fonti sono discordi e imposta
   il campo "conflict" a true nel JSON di output.
3. Tono: analitico, asciutto, mai sensazionalista. Niente promesse, niente "risparmia tasse",
   niente claim regolatori che non sono nelle fonti.

Scrivi SOLO un oggetto JSON (nessun testo fuori dal JSON) con ESATTAMENTE queste chiavi:
{{
  "the_facts": "<2-4 frasi sui fatti fusi, privilegiando lo stato corrente dalla news>",
  "bali_zero_take": "<2-3 frasi: cosa significa concretamente per i clienti Bali Zero>",
  "thirty_second_brief": {{"what":"<1 frase>","why_it_matters":"<1 frase>","who":"<chi è toccato>","risk_level":"<low|medium|high>"}},
  "next_steps": "<1-2 frasi azionabili>",
  "faq": [{{"question":"<domanda>","answer":"<risposta breve>"}}],
  "conflict": <true|false>,
  "conflict_note": "<se conflict=true, 1 frase su cosa diverge; altrimenti stringa vuota>"
}}"""


def _extract_json_obj(text: str) -> dict[str, Any]:
    """Estrae il primo oggetto JSON dal testo dell'LLM (robusto a preamboli).

    Fail-closed esplicito su risposta vuota/troncata (collaudo 2026-06-06: un reasoner con
    max_tokens basso può restituire content='' bruciando il budget nel reasoning — qui solleva
    un errore chiaro che brief_one cattura e logga, mai un brief corrotto).
    """
    if not text or not text.strip():
        raise ValueError("risposta LLM vuota (probabile troncamento/quota — nessun JSON da estrarre)")
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError(f"nessun oggetto JSON nella risposta LLM (primi 120 char: {text[:120]!r})")
    return json.loads(m.group(0))


def fuse_prose(client, *, news_title: str, news_summary: str,
               news_published: Optional[datetime], nb_brief: dict[str, Any]) -> dict[str, Any]:
    """Una sola chiamata LLM: genera la prosa fusa + il flag conflict. NIENTE citazioni/numeri qui."""
    key_facts = nb_brief.get("key_facts") or []
    prompt = FUSION_PROMPT.format(
        news_title=news_title[:400],
        news_summary=(news_summary or "")[:6000],
        news_published=news_published.isoformat() if news_published else "ignota",
        nb_key_facts=" | ".join(str(f) for f in key_facts[:15]) if key_facts else "(nessun grounding NB)",
        nb_snapshot=nb_brief.get("nb_snapshot_date") or "ignoto",
    )
    resp = client.messages.create(
        model=LLM_MODEL,
        max_tokens=3000,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in resp.content if getattr(block, "type", None) == "text")
    if getattr(resp, "stop_reason", None) == "max_tokens":
        logger.warning("fusione troncata (stop_reason=max_tokens) — JSON potrebbe essere incompleto")
    return _extract_json_obj(text)


# ============================================================================
# Costruzione brief_json (deterministica, post-fusione)
# ============================================================================
def build_brief_json(*, item: dict[str, Any], nb_brief: dict[str, Any],
                     prose: dict[str, Any], prev_revision: int = 0) -> dict[str, Any]:
    """Assembla il brief_json esteso. enrichment con rail iniettati (D6) + campi ricchi (futuro)."""
    title = item.get("title") or ""
    summary = item.get("summary") or ""
    published = _parse_dt(item.get("published_at"))
    chash = item.get("content_hash") or _content_hash(title, summary)

    # D6: i rail (citazioni/numeri/taboo) entrano DENTRO the_facts (il drafter li vede)
    facts_with_rails = _inject_rails_into_facts(prose.get("the_facts", ""), nb_brief)

    enrichment = {
        "thirty_second_brief": prose.get("thirty_second_brief") or {},
        "the_facts": facts_with_rails,
        "bali_zero_take": prose.get("bali_zero_take", ""),
        "in_practice": prose.get("next_steps", ""),  # drafter legge in_practice; mappiamo next_steps
        "next_steps": prose.get("next_steps", ""),
        "faq": (prose.get("faq") or [])[:6],
    }

    brief: dict[str, Any] = {
        # --- contratto minimo (drafter) ---
        "article_title": title,
        "article_summary": summary[:6000],
        "source_url": item.get("canonical_url"),
        "live_news_reasons": (item.get("llm") or {}).get("rationale") and [item["llm"]["rationale"]] or [],
        "live_news_score": (item.get("llm") or {}).get("relevance"),
        "enrichment": enrichment,
        # --- idempotenza / provenienza (D5) ---
        "staging_id": str(item.get("id")) if item.get("id") else None,
        "staging_type": (item.get("llm") or {}).get("service_line"),
        "canonical_url": item.get("canonical_url"),
        "content_hash": chash,
        "published_at": published.isoformat() if published else None,
        "revision": prev_revision + 1,
        # --- campi ricchi NB (persistiti per Step 3 / drafter-v2) ---
        "key_facts": nb_brief.get("key_facts") or [],
        "key_numbers": nb_brief.get("key_numbers") or [],
        "regulatory_citations_verbatim": nb_brief.get("regulatory_citations_verbatim") or [],
        "bilingual_lexicon": nb_brief.get("bilingual_lexicon") or [],
        "taboo_check": nb_brief.get("taboo_check") or [],
        "archetype": nb_brief.get("archetype"),
        "tone_register": nb_brief.get("tone_register"),
        # --- meta fusione (D2 staleness + audit) ---
        "fusion_meta": {
            "nb_sources": nb_brief.get("nb_sources") or [],
            "nb_snapshot_date": nb_brief.get("nb_snapshot_date"),
            "nb_staleness_days": _nb_staleness_days(nb_brief, published),
            "conflict": bool(prose.get("conflict")),
            "conflict_note": prose.get("conflict_note", "") if prose.get("conflict") else "",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model": LLM_MODEL,
        },
    }
    return brief


def decide_status(prose: dict[str, Any]) -> str:
    """D3: conflitto sostanziale ⇒ blocca (drafter salta); altrimenti pronto."""
    return STATUS_CONFLICT if prose.get("conflict") else STATUS_READY


# ============================================================================
# DB I/O (skippabile in --dry-run)
# ============================================================================
async def fetch_full_item(conn, item_id: str) -> Optional[dict[str, Any]]:
    row = await conn.fetchrow(FETCH_FULL_SQL, item_id)
    return dict(row) if row else None


async def check_existing(conn, canonical_url: str) -> Optional[dict[str, Any]]:
    if not canonical_url:
        return None
    row = await conn.fetchrow(DEDUP_SQL, canonical_url)
    return dict(row) if row else None


async def persist(conn, *, topic: str, status: str, brief: dict[str, Any],
                  existing: Optional[dict[str, Any]]) -> tuple[str, str]:
    """INSERT nuovo o UPDATE (re-brief D5). Ritorna (draft_id, action)."""
    payload = json.dumps(brief)
    if existing:
        draft_id = await conn.fetchval(UPDATE_SQL, existing["id"], status, payload)
        return str(draft_id), "rebrief-update"
    draft_id = await conn.fetchval(INSERT_SQL, topic[:500], status, payload)
    return str(draft_id), "insert"


# ============================================================================
# Orchestrazione di un singolo item
# ============================================================================
async def brief_one(conn, client, *, item_min: dict[str, Any], nb_brief: dict[str, Any],
                    dry_run: bool) -> dict[str, Any]:
    """Processa 1 item della shortlist. conn può essere None se dry_run (no DB).

    item_min = record shortlist (item_id, title, canonical_url, source_domain, published_at, llm).
    """
    item_id = item_min.get("item_id") or item_min.get("id")
    canonical_url = item_min.get("canonical_url")
    title_short = item_min.get("title") or ""

    # Stadio 1: summary COMPLETO dal DB (lo shortlist ha summary troncato). Se no-DB, usa lo shortlist.
    if conn is not None and item_id:
        full = await fetch_full_item(conn, str(item_id))
        if not full:
            return {"item_id": item_id, "status": "skipped", "reason": "item non trovato in intel_items"}
        item = {**item_min, **full}  # full sovrascrive (summary completo, content_hash, published_at reali)
    else:
        item = dict(item_min)
        item.setdefault("content_hash", _content_hash(title_short, item.get("summary") or ""))

    # D5: dedup + decisione re-brief
    existing = await check_existing(conn, canonical_url) if conn is not None else None
    prev_revision = 0
    if existing:
        cur_hash = item.get("content_hash") or _content_hash(item.get("title") or "", item.get("summary") or "")
        cur_pub = (_parse_dt(item.get("published_at")).isoformat()
                   if _parse_dt(item.get("published_at")) else None)
        changed = (existing.get("prev_hash") != cur_hash) or (existing.get("prev_published") != cur_pub)
        if not changed:
            return {"item_id": item_id, "status": "skipped",
                    "reason": f"già briefato (draft {existing['id']}, rev {existing['revision']}), contenuto invariato"}
        prev_revision = int(existing.get("revision") or 1)
        logger.info("re-brief: canonical_url cambiato (hash/published) → bump rev %d", prev_revision + 1)

    # Stadio 3: fusione (1 LLM call, solo prosa)
    prose = fuse_prose(
        client,
        news_title=item.get("title") or title_short,
        news_summary=item.get("summary") or "",
        news_published=_parse_dt(item.get("published_at")),
        nb_brief=nb_brief,
    )

    brief = build_brief_json(item=item, nb_brief=nb_brief, prose=prose, prev_revision=prev_revision)
    status = decide_status(prose)

    if dry_run or conn is None:
        return {"item_id": item_id, "status": "dry-run", "would_be_status": status,
                "conflict": bool(prose.get("conflict")), "brief_json": brief}

    draft_id, action = await persist(
        conn, topic=item.get("title") or title_short, status=status, brief=brief, existing=existing)
    return {"item_id": item_id, "status": status, "action": action, "draft_id": draft_id,
            "conflict": bool(prose.get("conflict"))}


# ============================================================================
# Selezione item da processare (D7 — solo approvati)
# ============================================================================
def load_shortlist(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text())
    return data.get("shortlist") or []


def select_items(shortlist: list[dict[str, Any]], *, approved: Optional[list[str]],
                 item_id: Optional[str], top: int) -> list[dict[str, Any]]:
    """D7: senza --approved/--item-id NON si processa tutta la shortlist alla cieca."""
    if item_id:
        return [r for r in shortlist if str(r.get("item_id")) == item_id][:1]
    if approved:
        approved_set = set(approved)
        picked = [r for r in shortlist if str(r.get("item_id")) in approved_set]
        return picked[: max(0, top)]
    # nessun gate fornito → comportamento sicuro: niente (richiede selezione esplicita)
    return []


# ============================================================================
# main
# ============================================================================
async def run(args) -> int:
    out_dir = Path(args.out_dir)
    shortlist_path = (Path(args.shortlist) if args.shortlist
                      else out_dir / f"shortlist-{datetime.now(timezone.utc):%Y-%m-%d}.json")
    if not shortlist_path.exists():
        logger.error("shortlist non trovata: %s", shortlist_path)
        return 2
    shortlist = load_shortlist(shortlist_path)

    approved = args.approved.split(",") if args.approved else None
    items = select_items(shortlist, approved=approved, item_id=args.item_id, top=args.top)
    if not items:
        logger.error("nessun item selezionato. Fornisci --item-id <uuid> o --approved <id1,id2,...> "
                     "(gate umano D7). Shortlist ha %d candidati.", len(shortlist))
        return 3
    items = items[:MAX_PER_RUN]  # D4 cap
    logger.info("Step 2: %d item selezionati (cap %d). dry_run=%s no_nb=%s",
                len(items), MAX_PER_RUN, args.dry_run, args.no_nb)

    nb_brief = {} if args.no_nb else load_nb_brief(args.nb_brief)
    if not nb_brief and not args.no_nb:
        logger.warning("nessun --nb-brief e non --no-nb: il grounding NB sarà VUOTO (fusione degradata). "
                       "In produzione l'orchestratore deve passare il brief NB del subagent.")

    client = _build_client(load_oauth_token())

    conn = None
    if not args.dry_run:
        import asyncpg  # local import (solo se serve il DB)
        conn = await asyncio.wait_for(asyncpg.connect(load_dsn()), timeout=20)
    elif args.with_db:  # dry-run ma con lettura DB per summary completo (no INSERT)
        import asyncpg
        conn = await asyncio.wait_for(asyncpg.connect(load_dsn()), timeout=20)

    results = []
    try:
        for it in items:
            try:
                res = await brief_one(conn, client, item_min=it, nb_brief=nb_brief,
                                      dry_run=args.dry_run)
            except Exception as exc:  # noqa: BLE001 — D4 stop-pulito: logga e prosegui col prossimo
                logger.error("item %s fallito: %s", it.get("item_id"), exc)
                res = {"item_id": it.get("item_id"), "status": "error", "reason": str(exc)}
            results.append(res)
            logger.info("→ %s: %s", it.get("title", "")[:70], res.get("status"))
    finally:
        if conn is not None:
            await conn.close()

    # output: scrivi il risultato (i brief in dry-run) su file per ispezione
    out_path = out_dir / f"step2-{datetime.now(timezone.utc):%Y-%m-%dT%H%M%S}.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"results": results}, ensure_ascii=False, indent=2))
    logger.info("Step 2 done. %d risultati → %s", len(results), out_path)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--shortlist", help="path shortlist-YYYY-MM-DD.json (default: oggi in --out-dir)")
    p.add_argument("--out-dir", default=str(OUT_DIR_DEFAULT))
    p.add_argument("--item-id", help="processa SOLO questo item_id (gate umano singolo)")
    p.add_argument("--approved", help="lista item_id approvati, comma-separated (gate umano D7)")
    p.add_argument("--top", type=int, default=MAX_PER_RUN, help=f"max item dagli approvati (default {MAX_PER_RUN})")
    p.add_argument("--nb-brief", help="path JSON col grounding NB prodotto dal subagent wr2-brief-interpreter")
    p.add_argument("--no-nb", action="store_true", help="salta il grounding NB (fusione degradata, collaudo)")
    p.add_argument("--dry-run", action="store_true", help="NON scrive war_room_drafts (stampa i brief)")
    p.add_argument("--with-db", action="store_true",
                   help="in dry-run, legge comunque il DB per il summary completo (no INSERT)")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        stream=sys.stderr)
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
