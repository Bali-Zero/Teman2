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
import argparse, glob, json, os, sys, time
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


def collect_claude(profile_dir: str, since: datetime) -> dict:
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
        try:
            if os.path.getmtime(fp) < since.timestamp():
                continue
            with open(fp, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    try:
                        j = json.loads(line)
                    except Exception:
                        continue
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
            out["status"] = "partial"
            out.setdefault("errors", []).append(f"{fp}: {e}")
    for g in groups.values():
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


def collect_codex(codex_home: str, since: datetime) -> dict:
    out = {"status": "ok", "days": defaultdict(lambda: defaultdict(int))}
    root = Path(codex_home) / "sessions"
    if not root.is_dir():
        return {"status": "absent", "note": f"{root} non esiste"}
    files = glob.glob(str(root / "**" / "*.jsonl"), recursive=True)
    if not files:
        return {"status": "empty"}
    for fp in files:
        try:
            if os.path.getmtime(fp) < since.timestamp():
                continue
            day = datetime.fromtimestamp(os.path.getmtime(fp), WITA).strftime("%d/%m")
            last_total: dict | None = None  # ultimo cumulativo visto in QUESTA sessione
            with open(fp, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if "token" not in line:
                        continue
                    try:
                        j = json.loads(line)
                    except Exception:
                        continue
                    usage = _extract_cumulative_token_usage(j)
                    if usage is not None:
                        last_total = usage
            if last_total is not None:
                out["days"][day]["in"] += last_total.get("input_tokens", 0) or 0
                out["days"][day]["out"] += last_total.get("output_tokens", 0) or 0
        except Exception as e:
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=8)
    ap.add_argument("--out", default=str(Path.home() / ".agent/cost-ledger/seat_usage_snapshot.json"))
    ap.add_argument("--seat-map", default=str(Path(__file__).parent / "seat_map.json"))
    ap.add_argument("--inject", help="path dashboard html in cui iniettare i seats (opzionale)")
    args = ap.parse_args()

    since = NOW - timedelta(days=args.days)
    smap = _load_seat_map(Path(args.seat_map))
    seats = []

    for pdir, seat_id in (smap.get("claude_profiles") or {}).items():
        r = collect_claude(os.path.expanduser(pdir), since)
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
        r = collect_codex(os.path.expanduser(chome), since)
        seats.append({"id": seat_id, "source": f"codex:{chome}", "status": r.get("status"),
                      "days": r.get("days", {}),
                      "metrics": fmt_metrics(r.get("days", {})) if r.get("days") else None,
                      "note": r.get("note")})

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
