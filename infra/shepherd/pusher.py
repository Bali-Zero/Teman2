#!/usr/bin/env python3
"""session_pusher — ATTUATORE: una passata sola, pensata per un cron ogni 3 minuti.

Mandato di Zero (2026-09-20): «spingi tutte le sessioni se si fermano, cron ogni 3 minuti».
Il pastore precedente (~/.agent/shepherd/shepherd.py) era un SENSORE: segnalava e aspettava
che la sessione madre mandasse il nudge con SendMessage. Quando la madre e' morta col salto
di finestra, nessuno ha piu' spinto nulla per due ore. Questo processo spinge da solo.

Canale del nudge: il titolo della finestra Ghostty viene timbrato sul tty del pid (la ricetta
provata di window_jump.sh), la finestra viene risolta PER NOME dal dizionario nativo, e solo
se il nome col marchio compare in UNA sola finestra si digita. Zero o due match: niente
digitato (superscar #3: mai una guardia su substring ambiguo). Gli id finestra di Ghostty non
sono stabili nel tempo, quindi non si memorizzano mai fra una passata e l'altra.

CHI viene spinto: SOLO le lane elencate in ~/.agent/shepherd/pusher-lanes.txt (una riga
"<sid> <etichetta>"), mai "tutte le sessioni vive". La finestra in cui Zero conversa e' una
sessione viva come le altre: spingerla la farebbe ripartire da sola ogni 3 minuti. Lista
vuota o assente = non si spinge nulla e si esce 2, mai "spingo tutto per default". Quando una
lane salta finestra il successore viene adottato da jump.log e il file viene riscritto.

Stato fra le passate: ~/.agent/shepherd/pusher-state.json (per sid: marchio dell'ultimo
testo, quando e' stato spinto, quante volte). Tre spinte sullo stesso marchio e si ferma: se
tre nudge non l'hanno mossa il problema non e' che dorme (superscar #2: non insistere su un
gauge fermo).
"""
import json, os, re, subprocess, sys, time
from datetime import datetime, timezone

REG = os.path.expanduser("~/.claude/sessions")
STATE = os.path.expanduser("~/.agent/shepherd/pusher-state.json")
LOG = os.path.expanduser(os.environ.get("PUSHER_LOG") or "~/.agent/shepherd/pusher.log")
LANES = os.path.expanduser("~/.agent/shepherd/pusher-lanes.txt")
JUMPLOG = os.path.expanduser("~/.organism/context-guard/jump.log")
AS = os.path.expanduser("~/.organism/context-guard/window_jump_native.applescript")

IDLE_S = int(os.environ.get("PUSHER_IDLE_S") or 150)
IDLE_WAITING_S = int(os.environ.get("PUSHER_WAIT_S") or 900)
MAX_PUSHES = int(os.environ.get("PUSHER_MAX_PUSHES") or 3)
# tetto DURO per lane, indipendente dal marchio: una sessione che ri-riporta "non ho nulla da
# fare" con un timestamp nuovo cambia il marchio a ogni giro e azzerava il contatore — il
# 2026-09-20 DYNAMIC-WORKFLOW ha incassato 8 nudge cosi', tutti inutili.
MAX_PER_HOUR = int(os.environ.get("PUSHER_MAX_PER_HOUR") or 2)

BLOCKED = re.compile(
    r"decisione (di|per|tua) Zero|risposta di Zero|resta (a|alla) tua|attendo la tua|serve Zero|"
    r"tua mossa|Resta la tua|non ha altro da fare|lane (e'|è) chius|mandato (e'|è) chius|"
    r"non posso fare altro|nulla che io possa sbloccare|non resta nulla", re.I)
WAITING = re.compile(r"attend|aspett|in attesa|in corso|deploy|merge queue|coda di merge|alla notifica|batch|in volo|login|CI\b|run \d", re.I)
GUARD = re.compile(r"context guard|nz-jump|limite di contesto|salto di finestra", re.I)

NUDGE = (
    "continua fino alla fine senza chiedere conferme. Prima ri-verifica lo stato reale in "
    "questo turno (i subagent in-process possono essere morti). Se aspetti una decisione di "
    "Zero non ri-chiederla: elencala in una riga e avanza su tutto il resto. Se aspetti un "
    "evento reale (deploy, coda di merge, CI, login) dillo in una riga e nomina l'evento."
)


def log(msg):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load(path, default):
    try:
        return json.load(open(path))
    except Exception:
        return default


def registry():
    """sessionId -> entry, SOLO se quel sessionId ha UN processo vivo.

    Due processi vivi sullo stesso sessionId sono un active-active (superscar #10): scrivono
    lo stesso transcript e un nudge finirebbe in quello che il dict ha tenuto per ultimo, cioe'
    a caso. Misurato il 2026-09-20 su f0e01939 e 31172471, ognuno con due attacchi. Una lane
    ambigua non si spinge: si segnala, come due match in `old-id`."""
    seen = {}
    try:
        names = os.listdir(REG)
    except Exception:
        return {}
    for fn in names:
        if not fn.endswith(".json"):
            continue
        try:
            d = json.load(open(os.path.join(REG, fn)))
            os.kill(int(d["pid"]), 0)
        except Exception:
            continue
        sid = d.get("sessionId")
        if sid:
            seen.setdefault(sid, []).append(d)
    out = {}
    for sid, rows in seen.items():
        if len(rows) == 1:
            out[sid] = rows[0]
        else:
            pids = ", ".join(f"{r['pid']}({r.get('name')})" for r in sorted(rows, key=lambda r: r["pid"]))
            log(f"AMBIGUA {sid[:8]}: {len(rows)} processi vivi sullo stesso sessionId [{pids}] — non spingo, chiudere il duplicato")
    return out


def transcript_path(sid, cwd=None):
    base = os.path.expanduser("~/.claude/projects")
    cands = []
    if cwd:
        cands.append("-" + cwd.lstrip("/").replace("/", "-").replace(".", "-"))
    cands += ["-Users-balizero-Desktop-nuzantara", "-Users-balizero-nuzantara"]
    for c in cands:
        p = os.path.join(base, c, sid + ".jsonl")
        if os.path.exists(p):
            return p
    import glob
    hit = glob.glob(os.path.join(base, "*", sid + ".jsonl"))
    return hit[0] if hit else ""


def classify(sid, cwd=None, nbytes=400_000):
    """(state, idle_s, last_text). BUSY = tool in volo o turno dell'utente."""
    path = transcript_path(sid, cwd)
    if not path:
        return "UNKNOWN", 0, ""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            f.seek(max(0, size - nbytes))
            blob = f.read()
    except Exception:
        return "UNKNOWN", 0, ""
    lines = blob.split(b"\n")[1:] if size > nbytes else blob.split(b"\n")
    recs = []
    for ln in lines:
        if not ln.strip():
            continue
        try:
            recs.append(json.loads(ln.decode("utf-8", "replace")))
        except Exception:
            continue
    state, last_ts, text = "BUSY", None, ""
    for d in reversed(recs):
        if d.get("isSidechain") or d.get("type") not in ("assistant", "user"):
            continue
        last_ts = d.get("timestamp")
        blocks = (d.get("message") or {}).get("content")
        blocks = blocks if isinstance(blocks, list) else []
        if d.get("type") == "assistant":
            has_tool = any(isinstance(b, dict) and b.get("type") == "tool_use" for b in blocks)
            text = " ".join(b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text").strip()
            state = "BUSY" if has_tool else "TURN_END"
        else:
            state = "BUSY"
        break
    idle = 0
    if last_ts:
        try:
            idle = int((datetime.now(timezone.utc) - datetime.fromisoformat(last_ts.replace("Z", "+00:00"))).total_seconds())
        except Exception:
            pass
    return state, idle, text.replace("\n", " ")


def tty_of(pid):
    try:
        t = subprocess.run(["ps", "-o", "tty=", "-p", str(pid)], capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return ""
    if not t or t == "??":
        return ""
    # macOS `ps -o tty=` stampa GIA' 'ttys001'; prefissare a mano dava /dev/ttyttys001, e
    # aprire in scrittura un path inesistente sotto /dev alza PermissionError (EACCES su
    # /dev), non FileNotFoundError: l'errore mentiva sulla causa.
    dev = t if t.startswith("/dev/") else ("/dev/" + t if t.startswith("tty") else "/dev/tty" + t)
    return dev if os.path.exists(dev) else ""


LAST_OSA_ERR = ""


def osa(*args, timeout=25):
    """'' sia per 'osascript ha fallito' sia per 'risposta vuota': la differenza finisce in
    LAST_OSA_ERR, perche' senza di essa un diniego TCC ('python3 richiede di controllare
    Ghostty' non approvato) e una finestra non trovata scrivono la STESSA riga di log."""
    global LAST_OSA_ERR
    LAST_OSA_ERR = ""
    try:
        r = subprocess.run(["osascript", AS, *args], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        LAST_OSA_ERR = f"osascript timeout {timeout}s (dialogo TCC modale aperto?)"
        return ""
    except Exception as e:
        LAST_OSA_ERR = f"{e.__class__.__name__}: {e}"
        return ""
    if r.returncode != 0:
        LAST_OSA_ERR = (r.stderr or "").strip()[:160] or f"exit {r.returncode}"
        return ""
    return r.stdout.strip()


def ghostty_window_for(pid, sid):
    """Timbra il titolo sul tty del pid e risolve la finestra PER NOME. '' se ambigua."""
    dev = tty_of(pid)
    if not dev:
        return "", "no-tty"
    mark = "NZP-" + sid[:8]
    try:
        with open(dev, "w") as f:
            f.write(f"\033]0;{mark}\007")
    except Exception as e:
        return "", f"stamp-failed:{e.__class__.__name__}"
    time.sleep(0.6)
    wid = osa("old-id", mark)
    if wid:
        return wid, "ok"
    return "", (f"osascript-ko: {LAST_OSA_ERR}" if LAST_OSA_ERR else "no-unique-window")


def type_into(wid, text):
    for _ in range(3):
        if osa("type-into", wid, text) == "ok":
            return True
        time.sleep(1.5)
    return False


def lanes():
    """[(sid, label)] dalla allowlist. Niente file, niente spinte."""
    out = []
    try:
        for ln in open(LANES):
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            parts = ln.split(None, 1)
            out.append((parts[0], parts[1] if len(parts) > 1 else "?"))
    except Exception:
        return []
    return out


def successor(sid, known):
    """L'id che il context guard ha stampato in jump.log per questo sid, se e' nuovo."""
    try:
        log_txt = open(JUMPLOG, errors="replace").read()
    except Exception:
        return None
    new = None
    for line in log_txt.splitlines():
        if sid in line:
            m = re.search(r"new session ([0-9a-f-]{36}) is up", line)
            if m and m.group(1) not in known:
                new = m.group(1)
    return new


def write_lanes(rows):
    with open(LANES, "w") as f:
        f.write("# lane sorvegliate dal pusher — '<sid> <etichetta>'. La finestra di Zero NON va qui.\n")
        for sid, label in rows:
            f.write(f"{sid} {label}\n")


def main():
    rows = lanes()
    if not rows:
        log(f"nessuna lane in {LANES}: non spingo nulla (allowlist vuota per scelta, non per errore)")
        return 2
    st = load(STATE, {})
    reg = registry()
    if not reg:
        log("registry vuoto: nessuna sessione viva, nulla da spingere")
        return 2
    known = {sid for sid, _ in rows}
    changed = False
    for i, (sid, label) in enumerate(list(rows)):
        if sid in reg:
            continue
        new = successor(sid, known)
        if new and new in reg:
            rows[i] = (new, label)
            known.add(new)
            changed = True
            log(f"ADOTTATA {label}: salto finestra {sid[:8]} -> {new[:8]}")
    if changed:
        write_lanes(rows)
    board, pushed = [], 0
    for sid, label in rows:
        d = reg.get(sid)
        if not d:
            board.append(f"{label}[{sid[:8]}]=MORTA")
            continue
        name = d.get("name", "?")
        state, idle, text = classify(sid, d.get("cwd"))
        s = st.setdefault(sid, {"mark": "", "pushes": 0, "last": 0, "hist": []})
        now = time.time()
        if state != "TURN_END":
            if s["pushes"]:
                log(f"RIPARTITA {label} [{name}]: di nuovo al lavoro dopo {s['pushes']} nudge")
            st[sid] = {"mark": "", "pushes": 0, "last": 0, "hist": s.get("hist", [])}
            board.append(f"{label}[{name}]={state}/{idle}s")
            continue
        thr = IDLE_WAITING_S if WAITING.search(text or "") else IDLE_S
        board.append(f"{label}[{name}]=TURN_END/{idle}s")
        if idle < thr:
            continue
        if BLOCKED.search(text or ""):
            log(f"BLOCCATA {label} [{name}]: dichiara di essere ferma su Zero o a mandato chiuso, non la spingo | {(text or '')[-160:]}")
            continue
        if GUARD.search(text or ""):
            log(f"GUARD {label} [{name}]: ferma sul context guard, il nudge non serve — serve il salto di finestra")
            continue
        recent = [t for t in s.get("hist", []) if now - t < 3600]
        s["hist"] = recent
        if len(recent) >= MAX_PER_HOUR:
            log(f"TETTO {label} [{name}]: {len(recent)} nudge nell'ultima ora, non insisto (ferma da {idle}s)")
            continue
        mark = (text or "(nessun testo)")[:120]
        if mark == s["mark"] and s["pushes"] >= MAX_PUSHES:
            continue
        if mark != s["mark"]:
            s.update(mark=mark, pushes=0)
        wid, why = ghostty_window_for(d["pid"], sid)
        if not wid:
            log(f"NON SPINTA {label} [{name}] ferma da {idle}s: finestra non risolta ({why})")
            continue
        if os.environ.get("PUSHER_DRY"):
            log(f"DRY {label} [{name}] ferma da {idle}s: spingerei su {wid}")
            continue
        if type_into(wid, NUDGE):
            s["pushes"] += 1
            s["last"] = now
            s.setdefault("hist", []).append(now)
            pushed += 1
            log(f"SPINTA {label} [{name}] ferma da {idle//60}m{idle%60:02d}s (nudge {s['pushes']}/{MAX_PUSHES}) | ultimo: {mark[:100]}")
        else:
            log(f"NON SPINTA {label} [{name}]: type-into rifiutato su {wid}")
    st = {k: v for k, v in st.items() if k in known}
    try:
        json.dump(st, open(STATE, "w"), indent=1)
    except Exception as e:
        log(f"stato non salvato: {e}")
    log("STATO " + " · ".join(board) + f" | spinte={pushed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
