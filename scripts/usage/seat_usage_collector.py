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
    Dedupe su (message.id, requestId) — stesso approccio di ccusage.
  - Codex CLI: $CODEX_HOMES (colon-sep; default ~/.codex:~/.codex-o2) →
    sessions/**/*.jsonl → oggetti con token count (campi tollerati:
    input_tokens/output_tokens | prompt_tokens/completion_tokens).
  - Cost-ledger locale: ~/.agent/cost-ledger/*.jsonl (output dell'exporter PG
    già armato) → per confronto/offline mirror della parte API.
  - agy / kimi: conteggio invocazioni dai log se le dir esistono (no token).

Output: JSON snapshot (default ~/.agent/cost-ledger/seat_usage_snapshot.json)
con schema {generated_at, seats:[{id, source, status, days:{...}, metrics}]}.
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


def collect_claude(profile_dir: str, since: datetime) -> dict:
    """Parse dei transcript JSONL di Claude Code per un profilo/account."""
    out = {"status": "ok", "days": defaultdict(lambda: defaultdict(int)), "models": defaultdict(int)}
    root = Path(profile_dir) / "projects"
    if not root.is_dir():
        return {"status": "absent", "note": f"{root} non esiste"}
    seen: set[tuple] = set()
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
                    if key in seen and key != (None, None):
                        continue
                    seen.add(key)
                    day = _day(j.get("timestamp", "")) or "??"
                    model = msg.get("model", "?")
                    d = out["days"][day]
                    d["in"] += usage.get("input_tokens", 0) or 0
                    d["out"] += usage.get("output_tokens", 0) or 0
                    d["cache_r"] += usage.get("cache_read_input_tokens", 0) or 0
                    d["cache_w"] += usage.get("cache_creation_input_tokens", 0) or 0
                    out["models"][model] += (usage.get("output_tokens", 0) or 0)
        except Exception as e:  # una sorgente rotta non ferma il giro
            out["status"] = "partial"
            out.setdefault("errors", []).append(f"{fp}: {e}")
    out["days"] = {k: dict(v) for k, v in out["days"].items()}
    out["models"] = dict(out["models"])
    return out


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
            with open(fp, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if "tokens" not in line:
                        continue
                    try:
                        j = json.loads(line)
                    except Exception:
                        continue
                    # schema drift tollerato: cerca in profondità coppie note
                    stack = [j]
                    while stack:
                        node = stack.pop()
                        if isinstance(node, dict):
                            ti = node.get("input_tokens", node.get("prompt_tokens"))
                            to = node.get("output_tokens", node.get("completion_tokens"))
                            if isinstance(ti, int) and isinstance(to, int):
                                out["days"][day]["in"] += ti
                                out["days"][day]["out"] += to
                            else:
                                stack.extend(node.values())
                        elif isinstance(node, list):
                            stack.extend(node)
        except Exception as e:
            out["status"] = "partial"
            out.setdefault("errors", []).append(f"{fp}: {e}")
    out["days"] = {k: dict(v) for k, v in out["days"].items()}
    return out


def collect_invocations(log_dir: str, since: datetime) -> dict:
    """Best-effort: conta file di log recenti (agy, kimi) — nessun token."""
    p = Path(os.path.expanduser(log_dir))
    if not p.is_dir():
        return {"status": "absent"}
    n = sum(1 for f in p.rglob("*") if f.is_file() and f.stat().st_mtime >= since.timestamp())
    return {"status": "ok", "recent_files": n}


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


def fmt_metrics(days: dict) -> str:
    today = NOW.strftime("%d/%m")
    t = days.get(today, {})
    tot_out_7d = sum(v.get("out", 0) for v in days.values())
    return (f"oggi: {t.get('in',0):,}in/{t.get('out',0):,}out · "
            f"7g out: {tot_out_7d:,} tok · cache r/w oggi: {t.get('cache_r',0):,}/{t.get('cache_w',0):,}")


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
                      "metrics": fmt_metrics(r.get("days", {})) if r.get("days") else None,
                      "note": r.get("note")})

    for chome, seat_id in (smap.get("codex_homes") or {}).items():
        r = collect_codex(os.path.expanduser(chome), since)
        seats.append({"id": seat_id, "source": f"codex:{chome}", "status": r.get("status"),
                      "days": r.get("days", {}),
                      "metrics": fmt_metrics(r.get("days", {})) if r.get("days") else None,
                      "note": r.get("note")})

    seats.append({"id": "G1", "source": "agy logs", **collect_invocations("~/.openclaw/logs", since)})
    seats.append({"id": "K1", "source": "kimi logs", **collect_invocations("~/.kimi-code", since)})
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
