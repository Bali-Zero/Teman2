#!/usr/bin/env python3
"""seat_usage_collector.py — misura il consumo dei SEAT abbonamento (l'altra metà
che il ledger PG llm_cost_events non vede) parsando i log locali delle CLI.

⚠ STATO: scritto in sessione cloud 2026-08-09, NON ancora testato sui log reali
del Mac (PENDING-ARMS). Ogni sorgente è difensiva: se il formato non combacia,
il seat esce con status="parse_error" e il resto continua — mai crash totale.

Sorgenti (tutte best-effort, stdlib only):
  - Claude Code: $CLAUDE_PROFILE_DIRS (colon-sep; default ~/.claude) →
    projects/**/*.jsonl → entries con message.usage {input_tokens, output_tokens,
    cache_read_input_tokens, cache_creation_input_tokens} + model + timestamp.
    Grouping on (message.id, requestId) with LAST-WINS: under streaming the
    same response group is rewritten several times with growing CUMULATIVE
    snapshots — the latest snapshot counts, never the first, never their
    sum. Latest is by the record's own timestamp, not file order (tie on
    equal timestamps: the record encountered later in the scan wins), and
    counters merge per field: a counter omitted by the latest snapshot keeps
    the value of its latest report in the group — "unknown" means no record
    of the group ever reported it.
  - Codex CLI: $CODEX_HOMES (colon-sep; default ~/.codex:~/.codex-o2) →
    sessions/**/*.jsonl → oggetti con token count (campi tollerati:
    input_tokens/output_tokens | prompt_tokens/completion_tokens).
  - Cost-ledger locale: ~/.agent/cost-ledger/*.jsonl (output dell'exporter PG
    già armato) → per confronto/offline mirror della parte API.
  - agy: ~/.gemini/antigravity-cli/log/cli-*.log (un file per invocazione CLI,
    verificato "logging before google.Init" in testa al file) → conteggio
    invocazioni, no token. Identità confermata da `installation_id` nella
    stessa dir (2026-08-20: fissato un bug per cui il collettore contava file
    ESTRANEI in ~/.openclaw/logs, la dir del bridge OpenClaw, e li pubblicava
    come "agy logs").
  - kimi: ~/.kimi-code/sessions/**/session_* (una dir per sessione, pinnata
    da session_index.jsonl) → conteggio invocazioni, no token. Identità
    confermata da `session_index.jsonl` nella dir base.
  - Entrambi: senza il marcatore d'identità la dir NON viene contata —
    status "unknown", mai un numero inventato da una dir non verificata.

Output: JSON snapshot (default ~/.agent/cost-ledger/seat_usage_snapshot.json)
con schema {generated_at, seats:[{id, source, status, days:{...}, metrics,
provenance?}]}. `provenance` esiste SOLO sui seat Claude: metadato additivo
(superficie JSONL locale, ultimo snapshot per gruppo, osservato/provvisorio)
— le chiavi in/out/cache_r/cache_w restano invariate per nome, tipo e
semantica di status (matrice collector-provenance/2, righe P3/C2).
Con --inject <dashboard.html> riscrive il blocco window.__SNAPSHOT__.seats.

Uso:
  python3 scripts/usage/seat_usage_collector.py                 # snapshot
  python3 scripts/usage/seat_usage_collector.py --days 8 --out /tmp/x.json
Mappatura profili→seat: scripts/usage/seat_map.json (creato al primo run con
template da editare: quale profilo cswap corrisponde ad A1/A2/A3/AZ, ecc.)
"""
from __future__ import annotations
import argparse
import glob
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from pathlib import Path

WITA = timezone(timedelta(hours=8))
NOW = datetime.now(WITA)

DEFAULT_SEAT_MAP = {
    "_doc": "Mappa profilo-locale -> seat FLEET_TOPOLOGY. Edita i path dopo aver installato cswap.",
    "claude_profiles": {
        str(Path.home() / ".claude"): "A?",
        # "~/.claude-swap-backup/<profilo>": "A1|A2|A3|AZ"
    },
    "codex_homes": {
        str(Path.home() / ".codex"): "O1",
        str(Path.home() / ".codex-o2"): "O2",
    },
}


def _load_seat_map(path: Path) -> dict:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(DEFAULT_SEAT_MAP, indent=2))
        print(f"[seat-usage] creato template mappa: {path} — edita i seat!", file=sys.stderr)
    try:
        return json.loads(path.read_text())
    except Exception as e:
        print(f"[seat-usage] seat_map illeggibile ({e}); uso default", file=sys.stderr)
        return DEFAULT_SEAT_MAP


def _day(ts: str) -> str | None:
    """timestamp ISO -> giorno WITA 'DD/MM'. None se non parsabile."""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.astimezone(WITA).strftime("%d/%m")
    except Exception:
        return None


def _ts_epoch(ts: str) -> float:
    """Record timestamp as epoch seconds, for ordering a group's snapshots.
    A naive ISO timestamp is assumed UTC; a missing/unparseable one maps to
    -inf, so any timestamped record outranks it and two untimestamped
    records fall through to the encounter-order tie-break (see
    collect_claude's docstring)."""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return float("-inf")


def _tok_or_none(usage: dict, key: str) -> int | None:
    """Value of a token counter: int if reported, None if ABSENT.
    0 and 'not reported' are different facts — never collapse None into 0."""
    v = usage.get(key)
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def _acc_tok(acc: int | str, val: int | None) -> int | str:
    """Accumulate a counter that may be 'unknown'. If ANY contribution is
    None (not reported) the aggregate stays 'unknown': summing only the
    known values would be an underestimate passed off as a total."""
    if not isinstance(acc, int) or val is None:
        return "unknown"
    return acc + val


def collect_claude(profile_dir: str, since: datetime, *, task_index: dict | None = None) -> dict:
    """Parse Claude Code JSONL transcripts for one profile/account.

    Real bug (2026-09-07, "output 852 vs 14931" on a Sonnet builder
    transcript): under streaming the same response group (message.id,
    requestId) is written MULTIPLE times into the transcript, each line a
    CUMULATIVE snapshot of that group's counters growing as the stream
    advances. The old dedupe kept the FIRST snapshot seen (first-wins on a
    `seen` set) and dropped every update — it published the partial
    beginning-of-stream count. Correct semantics: per group the LATEST
    snapshot wins (last-wins); NEVER sum a group's snapshots (they are
    cumulative: summing double-counts, the same defect class as the Codex
    2026-08-20 bug).

    "Latest" is decided by the record's own `timestamp`, NOT by file order
    (records can arrive out of order: replays, merged logs, concurrent
    writers). Ordering key is (timestamp, encounter_seq). Tie-break,
    explicit: records of a group with EQUAL timestamps resolve to the one
    encountered LATER in the scan — deterministic, and right for streaming
    (a same-timestamp rewrite is the more advanced snapshot). A record with
    a missing/unparseable timestamp sorts lowest (-inf): any timestamped
    record outranks it; two untimestamped records fall back to the
    encounter-order tie-break.

    Counters merge PER FIELD across the group's records: a counter omitted
    by the winning record keeps the latest value any record of the group
    reported (same ordering). A counter surfaces as "unknown" ONLY when no
    record of the group ever reported it — "missing from the last snapshot"
    is not unknown, and 0 and "not reported" are different facts.

    cache_* stay counters SEPARATE from in/out (they can overlap): never add
    them together. Day and model come from the group's latest record.

    Incomplete identity: the pair (message.id, requestId) groups records ONLY
    when BOTH ids are present. A record missing either id receives a fresh
    unique group key (a singleton group): partial identity cannot prove
    sameness, so it must never merge two records on the strength of the one
    id they happen to share — see the INCOMPLETE-IDENTITY POLICY comment in
    the code below.
    """
    out = {"status": "ok", "days": defaultdict(lambda: defaultdict(int)), "models": defaultdict(int)}
    root = Path(profile_dir) / "projects"
    if not root.is_dir():
        return {"status": "absent", "note": f"{root} non esiste"}
    # (message.id, requestId) -> per-group state: "order" is the (timestamp,
    # seq) key of the latest record overall (source of day/model); each
    # counter is None or the (timestamp, seq, value) of its latest REPORT.
    groups: dict[tuple, dict] = {}
    anon = 0
    seq = 0
    files = glob.glob(str(root / "**" / "*.jsonl"), recursive=True)
    if not files:
        return {"status": "empty"}
    for fp in files:
        file_node = None
        try:
            if os.path.getmtime(fp) < since.timestamp():
                continue
            with open(fp, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    try:
                        j = json.loads(line)
                    except Exception:
                        if task_index is not None and file_node:
                            task_index["nodes"][file_node]["read_error"] = True
                        continue
                    if task_index is not None and isinstance(j.get("sessionId"), str):
                        sid = j["sessionId"]
                        parent = sid if Path(fp).parent.name == "subagents" else None
                        identity = f"{sid}:{Path(fp).stem}" if parent else sid
                        file_node = _task_node(task_index, "claude", identity, parent)
                    msg = j.get("message") or {}
                    usage = msg.get("usage")
                    if not usage:
                        continue
                    key = (msg.get("id"), j.get("requestId"))
                    if key[0] is None or key[1] is None:
                        # INCOMPLETE-IDENTITY POLICY (explicit, never implicit):
                        # the group key answers "are these the same record?"
                        # and a tuple with a hole cannot answer yes — a hole
                        # is not a value.
                        #   - BOTH ids present → dedupe on the pair
                        #     (last-wins per group, per the docstring);
                        #   - EITHER id missing → identity is incomplete: the
                        #     record must NOT merge with another record on the
                        #     strength of the half that is present. Two
                        #     genuinely independent records can share a
                        #     requestId while both lack message.id (or vice
                        #     versa); collapsing them is the W1 exactly-once
                        #     defect shape — a key that silently merges what
                        #     it should distinguish;
                        #   - both missing → the anonymous path (unchanged).
                        # Mechanism: ANY incomplete-identity record gets a
                        # FRESH unique key, i.e. a singleton group of one —
                        # records merge only when both ids are present and
                        # equal, the only shape in which sameness is provable.
                        anon += 1
                        key = ("__incomplete_id__", anon)
                    seq += 1
                    order = (_ts_epoch(j.get("timestamp", "")), seq)
                    g = groups.setdefault(
                        key,
                        {"order": None, "day": "??", "model": "?",
                         "in": None, "out": None, "cache_r": None, "cache_w": None},
                    )
                    if g["order"] is None or order >= g["order"]:
                        # day/model follow the group's latest record
                        g["order"] = order
                        g["day"] = _day(j.get("timestamp", "")) or "??"
                        g["model"] = msg.get("model", "?")
                        if task_index is not None:
                            g["task_node"] = file_node
                    for field, usage_key in (("in", "input_tokens"),
                                             ("out", "output_tokens"),
                                             ("cache_r", "cache_read_input_tokens"),
                                             ("cache_w", "cache_creation_input_tokens")):
                        v = _tok_or_none(usage, usage_key)
                        if v is None:
                            continue  # absent here: keep any earlier report
                        cur = g[field]
                        if cur is None or order >= (cur[0], cur[1]):
                            g[field] = (order[0], order[1], v)
        except Exception as e:  # a broken source does not stop the run
            if task_index is not None and file_node:
                task_index["nodes"][file_node]["read_error"] = True
            out["status"] = "partial"
            out.setdefault("errors", []).append(f"{fp}: {e}")
    for key, g in groups.items():
        if task_index is not None and g.get("task_node"):
            # Reuse the already reduced response groups, including field-level
            # streaming updates. Cross-profile aliases must not count twice.
            identity = (*g["task_node"], key) if key[0] == "__incomplete_id__" else key
            group_key = hashlib.sha256(repr(identity).encode()).hexdigest()
            old = task_index.setdefault("claude_groups", {}).get(group_key)
            merged = dict(g if not old or g["order"] >= old["order"] else old)
            if old:
                for field in ("in", "out", "cache_r", "cache_w"):
                    values = [x[field] for x in (old, g) if x[field]]
                    merged[field] = max(values, key=lambda value: value[:2]) if values else None
            task_index["claude_groups"][group_key] = merged
            if key[0] == "__incomplete_id__":
                task_index["nodes"][g["task_node"]]["incomplete_identity"] = True
        d = out["days"][g["day"]]
        for k in ("in", "out", "cache_r", "cache_w"):
            d[k] = _acc_tok(d[k], g[k][2] if g[k] is not None else None)
        group_out = g["out"][2] if g["out"] is not None else None
        out["models"][g["model"]] = _acc_tok(out["models"][g["model"]], group_out)
    out["days"] = {k: dict(v) for k, v in out["days"].items()}
    out["models"] = dict(out["models"])
    return out


def _extract_cumulative_token_usage(event: dict) -> dict | None:
    """Estrae lo snapshot CUMULATIVO di token da un evento di sessione Codex.

    Bug reale (2026-08-20, "in=3.3e11/giorno"): ogni riga `token_count` di
    ~/.codex/sessions/**/*.jsonl porta DUE oggetti fratelli —
    `info.total_token_usage` (cumulativo per l'INTERA sessione, monotono
    non-decrescente: cresce ad ogni turno) e `info.last_token_usage` (delta
    del solo ultimo turno). La vecchia `collect_codex` faceva una DFS cieca
    sull'intero albero JSON di ogni riga e sommava OGNI dict con
    {input_tokens,output_tokens} che trovava — cioè sommava sia il
    cumulativo (che ri-conta tutto il traffico pregresso ad ogni evento) sia
    il delta, per ogni evento di sessioni con centinaia di eventi. Su una
    sessione con n eventi token_count il termine dominante è la somma dei
    total_token_usage crescenti (~n * totale_finale / 2) — con n~900 e un
    totale finale nell'ordine delle centinaia di migliaia, il risultato
    esplode di diversi ordini di grandezza oltre il consumo reale.

    Qui si estrae SOLO `total_token_usage` (il cumulativo autoritativo che
    Codex stesso calcola) e il chiamante ne tiene solo l'ULTIMO per
    sessione (last-wins) — quello è già il totale corretto dell'intera
    sessione, non va mai sommato più volte.
    """
    payload = event.get("payload") if isinstance(event, dict) else None
    if isinstance(payload, dict) and payload.get("type") == "token_count":
        info = payload.get("info")
        if isinstance(info, dict):
            total = info.get("total_token_usage")
            if isinstance(total, dict):
                ti = total.get("input_tokens")
                to = total.get("output_tokens")
                if isinstance(ti, int) and isinstance(to, int):
                    return {"input_tokens": ti, "output_tokens": to}
    # schema drift tollerato: formati legacy piatti a livello top
    # ({input_tokens,output_tokens} o {prompt_tokens,completion_tokens})
    # trattati come lo snapshot cumulativo CORRENTE (last-wins) — mai
    # sommati riga per riga come faceva la DFS precedente.
    if isinstance(event, dict):
        ti = event.get("input_tokens", event.get("prompt_tokens"))
        to = event.get("output_tokens", event.get("completion_tokens"))
        if isinstance(ti, int) and isinstance(to, int):
            return {"input_tokens": ti, "output_tokens": to}
    return None


def collect_codex(codex_home: str, since: datetime, *, task_index: dict | None = None) -> dict:
    out = {"status": "ok", "days": defaultdict(lambda: defaultdict(int))}
    root = Path(codex_home) / "sessions"
    if not root.is_dir():
        return {"status": "absent", "note": f"{root} non esiste"}
    files = glob.glob(str(root / "**" / "*.jsonl"), recursive=True)
    if not files:
        return {"status": "empty"}
    for fp in files:
        task_node = None
        try:
            if os.path.getmtime(fp) < since.timestamp():
                continue
            day = datetime.fromtimestamp(os.path.getmtime(fp), WITA).strftime("%d/%m")
            last_total: dict | None = None  # ultimo cumulativo visto in QUESTA sessione
            with open(fp, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if "token" not in line and not (task_index is not None and "session_meta" in line):
                        continue
                    try:
                        j = json.loads(line)
                    except Exception:
                        if task_index is not None and task_node:
                            task_index["nodes"][task_node]["read_error"] = True
                        continue
                    if task_index is not None and j.get("type") == "session_meta":
                        meta = j.get("payload") or {}
                        source = meta.get("source")
                        sub = source.get("subagent") if isinstance(source, dict) else None
                        spawn = sub.get("thread_spawn") if isinstance(sub, dict) else None
                        parent = spawn.get("parent_thread_id") if isinstance(spawn, dict) else None
                        task_node = _task_node(task_index, "codex", meta.get("id"), parent)
                    usage = _extract_cumulative_token_usage(j)
                    if usage is not None:
                        last_total = usage
                        if task_index is not None and task_node:
                            stamp = _ts_epoch(j.get("timestamp", ""))
                            info = (j.get("payload") or {}).get("info") or {}
                            raw_total = info.get("total_token_usage") or usage
                            total = {k: _tok_or_none(raw_total, k) for k in TASK_COUNTERS["codex"]}
                            event_key = (stamp, tuple(total.values()))
                            last = info.get("last_token_usage") or {}
                            last = {k: _tok_or_none(last, k) for k in TASK_COUNTERS["codex"]}
                            task_index["nodes"][task_node]["events"][event_key] = (stamp, total, last)
            if last_total is not None:
                out["days"][day]["in"] += last_total.get("input_tokens", 0) or 0
                out["days"][day]["out"] += last_total.get("output_tokens", 0) or 0
        except Exception as e:
            if task_index is not None and task_node:
                task_index["nodes"][task_node]["read_error"] = True
            out["status"] = "partial"
            out.setdefault("errors", []).append(f"{fp}: {e}")
    out["days"] = {k: dict(v) for k, v in out["days"].items()}
    return out


def collect_invocations(base_dir: str, since: datetime, *, identity_marker: str, entity_glob: str) -> dict:
    """Best-effort: conta le ENTITÀ (file o dir) che sono davvero un'invocazione
    della CLI — mai un conteggio cieco di TUTTO ciò che sta nella home della
    CLI. Nessun token qui, solo conteggio invocazioni.

    Bug reale (2026-08-20): il chiamante G1 puntava a `~/.openclaw/logs` —
    la home del bridge OpenClaw (git-sync.log, t4_monitor.log, pipeline nb),
    che non ha NULLA a che fare con `agy`/Antigravity — e un `rglob("*")`
    cieco su quella dir tornava un numero plausibile (11) di file altrui,
    pubblicato come "id": "G1", "source": "agy logs". Uno zero sarebbe
    saltato all'occhio; un piccolo numero plausibile no.

    Antidoto: prova d'identità PRIMA di contare. `identity_marker` è un file
    caratteristico che esiste SOLO nella home reale di quella CLI (es.
    `installation_id` per Antigravity, `session_index.jsonl` per Kimi) — se
    `base_dir` esiste ma il marcatore manca, la dir potrebbe essere estranea:
    status "unknown", MAI un conteggio. Solo col marcatore presente si conta
    via `entity_glob` (relativo a `base_dir`, `glob.glob(..., recursive=True)`
    — supporta `**`), filtrato per mtime >= since. Il glob stesso è già
    scoping-per-entità (es. `log/cli-*.log`, non l'intero albero) così cache/
    telemetry/updater/scratch della CLI non si sommano come se fossero
    invocazioni.
    """
    base = os.path.expanduser(base_dir)
    p = Path(base)
    if not p.is_dir():
        return {"status": "absent"}
    if not (p / identity_marker).exists():
        return {
            "status": "unknown",
            "note": (f"marcatore d'identita' '{identity_marker}' assente in {p} — "
                     "non verificabile che questa dir appartenga al seat atteso, nessun conteggio"),
        }
    n = 0
    for fp in glob.glob(os.path.join(base, entity_glob), recursive=True):
        try:
            if os.path.getmtime(fp) >= since.timestamp():
                n += 1
        except OSError:
            continue
    return {"status": "ok", "recent_invocations": n}


def collect_api_mirror(export_dir: str, since: datetime) -> dict:
    """Mirror locale del ledger PG (output di cost_ledger_export)."""
    p = Path(os.path.expanduser(export_dir))
    if not p.is_dir():
        return {"status": "absent"}
    tot = defaultdict(float)
    for fp in p.glob("*.jsonl"):
        try:
            with open(fp, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    try:
                        j = json.loads(line)
                        ts = j.get("ts_utc", "")
                        d = _day(ts)
                        if d:
                            tot[j.get("provider", "?")] += float(j.get("cost_usd", 0) or 0)
                    except Exception:
                        continue
        except Exception:
            continue
    return {"status": "ok", "usd_by_provider": dict(tot)} if tot else {"status": "empty"}


def _fmt_tok(v: int | str) -> str:
    return f"{v:,}" if isinstance(v, int) else "unknown"


def _sum_tok(values: Iterable[int | str]) -> int | str:
    """Sum only if EVERY contribution is known: a single 'unknown' makes the
    total 'unknown' (a partial sum would be an underestimate)."""
    total = 0
    for v in values:
        if not isinstance(v, int):
            return "unknown"
        total += v
    return total


# Provenance label for the figures collect_claude publishes (acceptance
# matrix collector-provenance/2, rows P1/P5/C1). Three DIFFERENT surfaces
# produce token figures and must never read as one: SDK per-step counters
# (which may be documented placeholders), cumulative SSE deltas, and THIS
# collector's source — the local Claude Code JSONL transcripts, read as
# latest-observed snapshot per response group. The label names the third.
# Claude seats ONLY: the provenance of Codex/agy/Kimi/TP1 figures is not
# established here, so their metrics strings stay byte-unchanged (row C3) —
# stamping this label on them would manufacture a claim, not state a fact.
CLAUDE_LOCAL_JSONL_PROVENANCE = (
    "fonte: JSONL locali, ultimo snapshot per gruppo — "
    "osservato/provvisorio, non provider-final"
)


def fmt_metrics(days: dict, provenance: str | None = None) -> str:
    """Render the per-seat metrics line. `provenance=None` (the default)
    keeps the rendering BYTE-IDENTICAL to the pre-provenance format — the
    Codex path depends on that (row C3); only the Claude path passes the
    label, so the provenance claim travels with the string a dashboard
    reader copies (row C1), not just with the JSON payload."""
    today = NOW.strftime("%d/%m")
    t = days.get(today, {})
    tot_out_7d = _sum_tok(v.get("out", 0) for v in days.values())
    s = (f"oggi: {_fmt_tok(t.get('in', 0))}in/{_fmt_tok(t.get('out', 0))}out · "
         f"7g out: {_fmt_tok(tot_out_7d)} tok · "
         f"cache r/w oggi: {_fmt_tok(t.get('cache_r', 0))}/{_fmt_tok(t.get('cache_w', 0))}")
    if provenance:
        s += f" · {provenance}"
    return s


TASK_COUNTERS = {
    "claude": ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens", "output_tokens"),
    "codex": ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens"),
}
TASK_ROLES = {"dux", "implementer", "review", "gate", "probe", "release"}
TASK_CLASSES = {"infra-hooks", "workflow", "code", "docs", "research", "operations", "other"}
TASK_COHORTS = {"baseline", "pre-token-efficiency-six", "post-token-efficiency-six", "compact-only", "manual"}


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _is_sha(value) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _task_node(index: dict, provider: str, sid, parent=None):
    if not isinstance(sid, str) or not sid or sid.startswith("None:"):
        return None
    key = (provider, _sha(sid))
    node = index.setdefault("nodes", {}).setdefault(key, {"parent": None, "events": {}})
    if isinstance(parent, str) and parent:
        node["parent"] = (provider, _sha(parent))
    return key


def _task_timestamp(value):
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError("timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timezone required")
    return parsed.timestamp()


def _task_manifest(doc: dict) -> tuple[dict, bool]:
    """Strict whitelist: no arbitrary text, transcript paths, or raw identities."""
    allowed = {"schema", "task_sha256", "task_class", "cohort", "sessions", "outcome", "started_utc", "ended_utc"}
    if not isinstance(doc, dict) or set(doc) - allowed or doc.get("schema") != "task-outcome/1":
        raise ValueError("schema")
    if not _is_sha(doc.get("task_sha256")) or doc.get("task_class") not in TASK_CLASSES or doc.get("cohort") not in TASK_COHORTS:
        raise ValueError("task identity")
    start = _task_timestamp(doc["started_utc"]) if "started_utc" in doc else float("-inf")
    end = _task_timestamp(doc["ended_utc"]) if "ended_utc" in doc else float("inf")
    if start >= end:
        raise ValueError("window")
    rows = doc.get("sessions")
    if not isinstance(rows, list) or not rows:
        raise ValueError("sessions")
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) - {"provider", "session_sha256", "parent_session_sha256", "role", "attempt", "overhead", "status"}:
            raise ValueError("session schema")
        if row.get("provider") not in TASK_COUNTERS or not _is_sha(row.get("session_sha256")) or row.get("role") not in TASK_ROLES:
            raise ValueError("session identity")
        if row.get("parent_session_sha256") is not None and not _is_sha(row["parent_session_sha256"]):
            raise ValueError("parent identity")
        if type(row.get("attempt")) is not int or row["attempt"] < 1 or type(row.get("overhead")) is not bool:
            raise ValueError("attempt")
        if row.get("status", "unknown") not in {"unknown", "succeeded", "failed"}:
            raise ValueError("session status")
        key = (row["provider"], row["session_sha256"])
        if key in seen:
            raise ValueError("duplicate session")
        seen.add(key)
    outcome = doc.get("outcome", {"status": "unknown"})
    if not isinstance(outcome, dict) or set(outcome) - {"status", "verifier_role", "verifier_session_sha256", "evidence_sha256", "verified_utc"}:
        raise ValueError("outcome schema")
    if outcome.get("status") not in {"verified_complete", "failed", "abandoned", "unknown"}:
        raise ValueError("outcome")
    if outcome.get("verifier_role", "none") not in {"fresh-gate", "ci", "none"}:
        raise ValueError("verifier role")
    for field in ("verifier_session_sha256", "evidence_sha256"):
        if outcome.get(field) is not None and not _is_sha(outcome[field]):
            raise ValueError("verifier identity")
    if outcome.get("verified_utc") is not None:
        _task_timestamp(outcome["verified_utc"])
    verified = outcome.get("status") == "verified_complete"
    verifier = outcome.get("verifier_session_sha256")
    independent = verifier is not None and any(r["session_sha256"] == verifier and r["role"] == "gate" for r in rows)
    independent = independent and not any(r["session_sha256"] == verifier and r["role"] != "gate" for r in rows)
    valid_proof = outcome.get("verifier_role") in {"fresh-gate", "ci"} and outcome.get("evidence_sha256") and outcome.get("verified_utc")
    # CI attestations can identify a job instead of a metered model session.
    valid_proof = valid_proof and (independent or outcome.get("verifier_role") == "ci")
    # Completed-task attribution is frozen; a later turn in a reused session
    # must not silently change the recorded cost of an earlier task.
    valid_proof = valid_proof and "started_utc" in doc and "ended_utc" in doc
    if valid_proof:
        valid_proof = start <= _task_timestamp(outcome["verified_utc"]) <= end
    return {**doc, "status": "unknown" if verified and not valid_proof else outcome["status"], "window": (start, end)}, bool(verified and not valid_proof)


def _task_events(index: dict) -> None:
    """Add Claude response groups to the same hashed, provider-specific index."""
    mapping = dict(zip(TASK_COUNTERS["claude"], ("in", "cache_r", "cache_w", "out")))
    for identity, group in index.get("claude_groups", {}).items():
        values = {field: group[key][2] if group[key] else None for field, key in mapping.items()}
        index["nodes"][group["task_node"]]["events"][identity] = (group["order"][0], values, {})


def _task_usage(provider: str, node: dict, window: tuple) -> tuple[dict, set]:
    fields = TASK_COUNTERS[provider]
    result = dict.fromkeys(fields, 0)
    result["usage_events"] = 0
    previous = {}
    selected = set()
    for identity, (stamp, values, last) in sorted(node["events"].items(), key=lambda item: item[1][0]):
        delta = {}
        for field in fields:
            value = values.get(field)
            if value is None or value < 0:
                delta[field] = None
                continue
            old = previous.get(field)
            if provider == "claude":
                delta[field] = value
            elif old is None:
                # Forked/resumed threads can start with inherited cumulative
                # counters. Only this observed call belongs to the new thread.
                delta[field] = last.get(field)
            else:
                delta[field] = value if value < old else value - old
            if delta[field] is not None and (delta[field] < 0 or delta[field] > value):
                delta[field] = None
            previous[field] = value
        if window[0] <= stamp < window[1]:
            # Duplicate cumulative observations are not additional usage/calls.
            if provider == "codex" and all(v == 0 for v in delta.values()):
                continue
            for field in fields:
                result[field] = _acc_tok(result[field], delta[field])
            result["usage_events"] += 1
            selected.add(identity)
    return result, selected


def collect_task_outcomes(directory: Path, index: dict) -> dict:
    meta = {"schema": "task-usage/1", "status": "ok", "rejected": 0, "downgraded": 0,
            "scope": "observed local Claude/Codex usage; trusted outcome attestations; no monetary estimate"}
    paths = sorted(directory.glob("*.json")) if directory.is_dir() else []
    if not paths:
        meta["status"] = "no_manifests"
    _task_events(index)
    tasks, used, identities = [], {}, {}
    for path in paths:
        try:
            if path.stat().st_size > 1_000_000:
                raise ValueError("oversized manifest")
            doc, downgraded = _task_manifest(json.loads(path.read_text()))
            if doc["task_sha256"] in identities:
                identities[doc["task_sha256"]]["usage_complete"] = False
                identities[doc["task_sha256"]]["usage_issues"].append("duplicate_task_manifest")
                raise ValueError("duplicate task")
        except (OSError, ValueError, TypeError, KeyError):
            meta["rejected"] += 1
            continue
        meta["downgraded"] += downgraded
        declared = {(r["provider"], r["session_sha256"]): r for r in doc["sessions"]}
        selected = dict(declared)
        nodes = index.get("nodes", {})
        while True:
            children = {k: selected[n["parent"]] for k, n in nodes.items() if k not in selected and n["parent"] in selected}
            if not children:
                break
            selected.update(children)
        # Traverse before pruning so an active grandchild is still found through
        # a parent whose own usage predates this task's window.
        selected = {key: row for key, row in selected.items()
                    if key in declared or not nodes[key]["events"] or nodes[key].get("read_error")
                    or any(doc["window"][0] <= event[0] < doc["window"][1] or event[0] == float("-inf")
                           for event in nodes[key]["events"].values())}
        result = {"task_sha256": doc["task_sha256"], "task_class": doc["task_class"], "cohort": doc["cohort"],
                  "status": doc["status"], "sessions_declared": len(declared), "sessions_found": 0,
                  "sessions_missing": sum(k not in nodes for k in declared), "descendants_added": len(selected) - len(declared),
                  "attempts_max": max(r["attempt"] for r in declared.values()),
                  "failed_or_retried_sessions": sum(r.get("status") == "failed" or r["attempt"] > 1 for r in declared.values()),
                  "overhead_sessions": 0, "by_provider": {}, "overhead_tokens": {}, "usage_complete": True,
                  "usage_issues": []}
        if result["sessions_missing"]:
            result["usage_issues"].append("missing_sessions")
        for key, row in selected.items():
            if key not in nodes:
                continue
            provider = key[0]
            usage, events = _task_usage(provider, nodes[key], doc["window"])
            result["sessions_found"] += 1
            result["overhead_sessions"] += row["overhead"]
            if not nodes[key]["events"] or any(v == "unknown" for v in usage.values()):
                result["usage_issues"].append("missing_or_unknown_counters")
            if nodes[key].get("incomplete_identity"):
                result["usage_issues"].append("incomplete_response_identity")
            if nodes[key].get("read_error"):
                result["usage_issues"].append("source_read_error")
            if any(event[0] == float("-inf") for event in nodes[key]["events"].values()):
                result["usage_issues"].append("unknown_event_timestamp")
            for identity in events:
                event_key = (key, identity)
                if event_key in used:
                    other = used[event_key]
                    other["usage_complete"] = False
                    other["usage_issues"].append("overlapping_task_usage")
                    result["usage_issues"].append("overlapping_task_usage")
                used[event_key] = result
            for section in ("by_provider", "overhead_tokens") if row["overhead"] else ("by_provider",):
                subtotal = result[section].setdefault(provider, dict.fromkeys(usage, 0))
                for field, value in usage.items():
                    subtotal[field] = _acc_tok(subtotal[field], value if isinstance(value, int) else None)
        result["usage_complete"] = not result["usage_issues"]
        tasks.append(result)
        identities[doc["task_sha256"]] = result
    for task in tasks:
        task["usage_issues"] = sorted(set(task["usage_issues"]))
    eligible = [t for t in tasks if t["status"] == "verified_complete" and t["usage_complete"]]
    meta["verified_tasks_with_complete_usage"] = len(eligible)
    meta["tokens_per_verified_task"] = None
    meta["average_reason"] = "no_verified_tasks_with_complete_usage"
    cohorts = defaultdict(list)
    for task in eligible:
        cohorts[(task["cohort"], task["task_class"])].append(task)
    meta["cohorts"] = []
    for (cohort, task_class), members in sorted(cohorts.items()):
        averages = {}
        for provider, fields in TASK_COUNTERS.items():
            present = [t["by_provider"][provider] for t in members if provider in t["by_provider"]]
            if present:
                averages[provider] = {k: sum(t[k] for t in present) / len(members) for k in fields}
        meta["cohorts"].append({"cohort": cohort, "task_class": task_class,
                                "verified_tasks": len(members), "tokens_per_verified_task": averages})
    if len(cohorts) > 1:
        meta["average_reason"] = "mixed_cohorts_or_task_classes; compare_matched_tasks"
    elif eligible:
        meta["tokens_per_verified_task"] = meta["cohorts"][0]["tokens_per_verified_task"]
        meta["average_reason"] = "provider_counters_separate; denominator_is_verified_tasks_with_complete_usage"
    return {"tasks": tasks, "tasks_meta": meta}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=8)
    ap.add_argument("--out", default=str(Path.home() / ".agent/cost-ledger/seat_usage_snapshot.json"))
    ap.add_argument("--seat-map", default=str(Path(__file__).parent / "seat_map.json"))
    ap.add_argument("--inject", help="path dashboard html in cui iniettare i seats (opzionale)")
    ap.add_argument("--task-outcomes", default=str(Path.home() / ".agent/cost-ledger/task-outcomes"))
    ap.add_argument("--tasks-only", action="store_true", help="Print the additive task report without writing a snapshot")
    args = ap.parse_args()

    since = NOW - timedelta(days=args.days)
    smap = _load_seat_map(Path(args.seat_map))
    seats = []
    task_dir = Path(os.path.expanduser(args.task_outcomes))
    task_index = {} if task_dir.is_dir() and any(task_dir.glob("*.json")) else None

    for pdir, seat_id in (smap.get("claude_profiles") or {}).items():
        r = collect_claude(os.path.expanduser(pdir), since, task_index=task_index)
        seats.append({"id": seat_id, "source": f"claude:{pdir}", "status": r.get("status"),
                      "days": r.get("days", {}), "models": r.get("models", {}),
                      "metrics": fmt_metrics(r.get("days", {}),
                                             provenance=CLAUDE_LOCAL_JSONL_PROVENANCE)
                      if r.get("days") else None,
                      # Additive metadata (rows P1/C2): the existing keys
                      # above keep names, types and status semantics;
                      # provenance only ADDS, never renames or retypes.
                      "provenance": {
                          "surface": "claude_code_local_jsonl_transcripts",
                          "method": "latest_observed_snapshot_per_response_group",
                          "reading": "observed/provisional — not provider-final",
                          "label": CLAUDE_LOCAL_JSONL_PROVENANCE,
                      },
                      "note": r.get("note")})

    for chome, seat_id in (smap.get("codex_homes") or {}).items():
        r = collect_codex(os.path.expanduser(chome), since, task_index=task_index)
        seats.append({"id": seat_id, "source": f"codex:{chome}", "status": r.get("status"),
                      "days": r.get("days", {}),
                      "metrics": fmt_metrics(r.get("days", {})) if r.get("days") else None,
                      "note": r.get("note")})

    task_report = collect_task_outcomes(task_dir, task_index or {})
    if args.tasks_only:
        print(json.dumps(task_report, sort_keys=True))
        return 0

    seats.append({"id": "G1", "source": "agy (antigravity-cli) invocation logs", **collect_invocations(
        "~/.gemini/antigravity-cli", since,
        identity_marker="installation_id",
        entity_glob="log/cli-*.log",
    )})
    seats.append({"id": "K1", "source": "kimi-code session dirs", **collect_invocations(
        "~/.kimi-code", since,
        identity_marker="session_index.jsonl",
        entity_glob="sessions/**/session_*",
    )})
    seats.append({"id": "TP1", "source": "dashscope", "status": "pending_probe1",
                  "note": "crediti Token Plan: endpoint da individuare in PROBE-1"})

    snapshot = {
        "generated_at": NOW.isoformat(timespec="seconds"),
        "window_days": args.days,
        "seats": seats,
        "api_mirror": collect_api_mirror("~/.agent/cost-ledger", since),
        **task_report,
    }

    out = Path(os.path.expanduser(args.out))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False))
    print(f"[seat-usage] snapshot → {out} ({len(seats)} seat)")

    if args.inject:
        try:
            html_p = Path(os.path.expanduser(args.inject))
            html = html_p.read_text()
            marker = '"seats": '
            # iniezione minimale: il dashboard fa comunque fetch del JSON se servito insieme
            html_p.with_suffix(".snapshot.json").write_text(json.dumps(snapshot))
            print(f"[seat-usage] snapshot affiancato a {html_p.name} (il fetch() lo trova)")
            _ = (html, marker)
        except Exception as e:
            print(f"[seat-usage] inject fallita: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
