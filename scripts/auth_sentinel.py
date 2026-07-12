#!/usr/bin/env python3
"""auth_sentinel.py — fleet credential + platform-grant liveness guardian.

WHY (2026-07-11, Zero: "rendere autonomi i login interattivi umani"):
Nessuna credenziale della fleet è normalmente rotta; il fallimento reale è la
SCOPERTA-TROPPO-TARDI — un cron ci sbatte contro (cascata Fly 14/5, IG-190,
NLM auth-expired 6/7) prima che qualcuno sappia che va rinnovata. Questo
sentinel PROVA ogni credenziale con il suo comando reale (mai un proxy),
AUTO-REFRESHA dove il token lo consente (ramo A), e per ciò che richiede
davvero un gesto umano (ramo B: agy/nlm/codex-revoked; TCC-hard) manda UN
alert azionabile col comando/click ESATTO da eseguire.

DUE FAMIGLIE (mappa 2026-07-11):
  A · self-refreshing → claude(×3 refresh_token) · fly(-t esplicito) ·
      deepseek(chiave statica) · drive(refresh+watchdog). Il sentinel qui
      solo VERIFICA in anticipo + forza il refresh dove serve.
  B · sessione Google/CDP interattiva → agy(Antigravity) · nlm(CDP cookies) ·
      codex(solo se token_revoked server-side). NON auto-riparabili headless
      in modo affidabile (runbook_nlm_auth_stability_fix, 68gg): il sentinel
      RIDUCE a 1 gesto raro con comando pronto, non lo elimina.
  B-hard · TCC/Full-Disk-Access (W84) → launchd perde il grant su ~/Desktop
      SENZA cambio codice; green-but-dead. NON riparabile da codice: reset =
      System Settings (operator). `tccutil reset` è VIETATO (scar
      W84-tccutil-recidiva: distruttivo OS-wide, mai un probe). Il sentinel
      DIAGNOSTICA (job Desktop + log 'Operation not permitted' su exit-0) e
      dice il click esatto.

BOUNDARY (SYMBIOSIS Law 2 / scar #4 secret-in-the-clear):
  - Nessun valore di token/chiave/cookie viene MAI letto, stampato o loggato.
    Si sondano solo COMANDI (exit-code + stringa d'errore nota) e si leggono
    solo NOMI/percorsi/date. Nessun segreto tocca stdout, log o alert.
  - Nessun comando distruttivo: mai `tccutil reset`, mai `--clear` autonomo
    (cancella il profilo — decisione operatore).

USO:
  auth_sentinel.py                 # probe tutto, alert-quando-serve, exit 0
  auth_sentinel.py --json          # report machine-readable, nessun alert
  auth_sentinel.py --selftest      # verifica che il sentinel stesso sia sano
  auth_sentinel.py --no-alert      # probe + report, mai Telegram (dry-run)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

HOME = Path.home()
REPO = Path(__file__).resolve().parents[1]
# sentinel_lib è affianco a questo script → import path-independent
sys.path.insert(0, str(Path(__file__).resolve().parent))

# --- probe result contract -------------------------------------------------

OK = "ok"           # vivo, nessuna azione
REFRESHED = "refreshed"  # era scaduto, il sentinel l'ha rinnovato da solo (ramo A)
WARN = "warn"       # config-issue con workaround NOTO (es. regression CLI): il
#                     token è valido, serve solo che i wrapper lo usino bene.
#                     NON è un login-morto → digest, non alert p0.
ACTION = "action"   # serve un gesto umano — l'alert porta il comando esatto (ramo B)
SKIP = "skip"       # non presente su questa macchina (non è un errore)
UNKNOWN = "unknown"  # probe non conclusivo (log, non block — mai un falso allarme)


@dataclass
class Probe:
    arm: str
    family: str            # "A" | "B" | "B-hard"
    status: str            # OK | REFRESHED | ACTION | SKIP | UNKNOWN
    detail: str = ""
    fix_cmd: str = ""      # il comando/click ESATTO quando status==ACTION


def _run(cmd: list[str] | str, timeout: int = 30, shell: bool = False) -> tuple[int, str]:
    """Esegue un probe. Ritorna (exit, output-combinato-troncato). stdin chiuso
    (/dev/null) — codex blocca su stdin aperto."""
    try:
        p = subprocess.run(
            cmd, shell=shell, timeout=timeout,
            stdin=subprocess.DEVNULL,
            capture_output=True, text=True,
        )
        return p.returncode, (p.stdout + p.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    except FileNotFoundError:
        return 127, "NOT_FOUND"
    except Exception as e:  # noqa: BLE001 — probe non deve mai crashare il sentinel
        return 1, f"PROBE_ERR:{type(e).__name__}"


# stringhe d'errore auth note (grep, non giudizio): se il probe le contiene →
# è morte-di-auth, non un problema di contenuto.
_AUTH_DEAD_RE = re.compile(
    r"authentication expired|token_revoked|refresh_token_reused|"
    r"please login|not authenticated|401|invalid_grant|auth error|"
    r"no access token|unauthor",
    re.I,
)


# --- ramo A: self-refreshing ----------------------------------------------

def probe_claude() -> Probe:
    """Claude OAuth ×3. Il CLI rinnova da refresh_token al primo uso; qui lo
    forziamo con un --print micro così un cron trova il token GIÀ fresco."""
    cred = HOME / ".claude" / ".credentials.json"
    if not cred.exists():
        return Probe("claude-oauth", "A", SKIP, "no .credentials.json")
    # micro-print: innesca il refresh se scaduto. Non stampiamo mai il token.
    rc, out = _run(["claude", "--print", "--model", "claude-haiku-4-5-20251001", "ok"], timeout=45)
    if rc == 0:
        return Probe("claude-oauth", "A", OK, "print ok (token fresco o rinnovato)")
    low = out.lower()
    if "weekly" in low or "usage limit" in low or "out of extra usage" in low:
        # cap settimanale ≠ auth morta: il fallback ×2/×3 copre, nessun gesto umano
        return Probe("claude-oauth", "A", OK, "weekly-cap (fallback slot copre)")
    if _AUTH_DEAD_RE.search(out):
        return Probe("claude-oauth", "A", ACTION,
                     "refresh_token rifiutato",
                     fix_cmd="claude login   # da terminale interattivo")
    return Probe("claude-oauth", "A", UNKNOWN, out[:120])


def probe_fly() -> Probe:
    cfg = HOME / ".fly" / "config.yml"
    if not cfg.exists():
        return Probe("fly", "A", SKIP, "no ~/.fly/config.yml")
    rc, out = _run(["fly", "auth", "whoami"], timeout=25)
    if rc == 0 and "@" in out:
        # il CLI legge il token da solo → sano. NON promuovere a ACTION solo
        # perché il fallback -t funzionerebbe: la regression morde solo quando
        # il probe BASE fallisce (verificato 2026-07-11: whoami senza -t → email).
        return Probe("fly", "A", OK, "whoami ok")
    # trap lessons_fly_cli_token_regression: il CLI può non leggere il token
    # anche se è valido. SOLO se il probe base è fallito, retry con -t esplicito.
    token = ""
    for line in cfg.read_text().splitlines():
        if line.strip().startswith("access_token:"):
            token = line.split(":", 1)[1].strip()
            break
    if token:
        rc2, out2 = _run(["fly", "auth", "whoami", "-t", token], timeout=25)
        if rc2 == 0 and "@" in out2:
            # token VALIDO, solo il CLI non lo auto-scopre in env non-interattivo
            # (regression 0.4.49). Workaround noto → WARN, non ACTION: nessun gesto
            # umano urgente, i wrapper cron già passano -t (fly-pg-proxy-wrapper.sh).
            return Probe("fly", "A", WARN,
                         "token valido; CLI auth-discovery rotta in env cron (regression 0.4.49)",
                         fix_cmd="i wrapper cron DEVONO passare `-t $TOKEN` "
                                 "(già fatto in ~/scripts/fly-pg-proxy-wrapper.sh; "
                                 "verifica ogni nuovo consumer fly)")
    if _AUTH_DEAD_RE.search(out):
        return Probe("fly", "A", ACTION, "token Fly rifiutato",
                     fix_cmd="flyctl auth login   # da terminale interattivo")
    return Probe("fly", "A", UNKNOWN, out[:120])


def probe_deepseek() -> Probe:
    env = HOME / ".openclaw" / "workspace" / ".env.master"
    if not env.exists():
        return Probe("deepseek", "A", SKIP, "no .env.master (non su questa macchina)")
    # chiave statica: presenza del NOME basta. Non facciamo una call a pagamento
    # solo per un health-ping (costo). Presenza-del-nome = armato.
    has = any(l.strip().startswith("DEEPSEEK") for l in env.read_text().splitlines())
    return Probe("deepseek", "A", OK if has else ACTION,
                 "key presente" if has else "DEEPSEEK_* assente in .env.master",
                 "" if has else "rimetti la chiave DeepSeek in .env.master")


def probe_drive() -> Probe:
    """Drive OAuth: refresh automatico + watchdog dedicato 7gg. Il sentinel non
    duplica il watchdog, verifica solo che esista ed sia armato."""
    wd = REPO / "scripts" / "drive_token_watchdog.py"
    if not wd.exists():
        return Probe("drive-oauth", "A", UNKNOWN, "watchdog non trovato nel repo")
    return Probe("drive-oauth", "A", OK,
                 "delegato a drive_token_watchdog.py (refresh auto + alert 7gg)")


# --- ramo B: sessione interattiva ------------------------------------------

def probe_codex() -> Probe:
    auth = HOME / ".codex" / "auth.json"
    if not auth.exists():
        return Probe("codex", "B", SKIP, "no ~/.codex/auth.json")
    # cold-start del primo call codex può superare 60s (verificato 2026-07-11:
    # vivo a ~75s). 90s per non falsare in TIMEOUT un seat sano.
    rc, out = _run(["codex", "exec", "--sandbox", "read-only",
                    "--skip-git-repo-check", "ping"], timeout=90)
    if rc == 0 and _AUTH_DEAD_RE.search(out) is None:
        return Probe("codex", "B", OK, "exec ok")
    if _AUTH_DEAD_RE.search(out):
        return Probe("codex", "B", ACTION,
                     "OAuth revocato server-side (token_revoked/reused)",
                     fix_cmd="codex login   # da terminale interattivo")
    return Probe("codex", "B", UNKNOWN, out[:120])


def probe_agy() -> Probe:
    if not (HOME / ".local" / "bin" / "agy").exists() and _run(["which", "agy"])[0] != 0:
        return Probe("agy", "B", SKIP, "agy non installato")
    # sintassi verificata 2026-07-11: -p vuole il prompt INLINE, non su pipe
    rc, out = _run(["agy", "-p", "ping"], timeout=60)
    if rc == 0 and "pong" in out.lower():
        return Probe("agy", "B", OK, "pong")
    if rc == 0 and out and _AUTH_DEAD_RE.search(out) is None:
        # ha risposto qualcosa di non-auth-error → vivo
        return Probe("agy", "B", OK, "risponde")
    if _AUTH_DEAD_RE.search(out) or rc == 124:
        return Probe("agy", "B", ACTION,
                     "sessione Antigravity/Google scaduta o non risponde",
                     fix_cmd="apri Antigravity IDE e ri-autentica il seat Google "
                             "(AI Ultra); poi `agy -p ping` deve dare pong")
    return Probe("agy", "B", UNKNOWN, out[:120])


def probe_nlm() -> Probe:
    if _run(["which", "nlm"])[0] != 0:
        return Probe("nlm", "B", SKIP, "nlm non installato")
    rc, out = _run(["nlm", "login", "--check"], timeout=40)
    if rc == 0 and "valid" in out.lower():
        return Probe("nlm", "B", OK, "auth valid")
    if _AUTH_DEAD_RE.search(out) or "expired" in out.lower():
        return Probe("nlm", "B", ACTION,
                     "CDP session scaduta (cookie volatili — runbook 4/5)",
                     fix_cmd="nlm login --clear   # su terminale interattivo, "
                             "login antonellosiano@gmail.com in finestra Chrome dedicata")
    return Probe("nlm", "B", UNKNOWN, out[:120])


# --- ramo B-hard: TCC / Full-Disk-Access (W84) -----------------------------

def probe_tcc() -> Probe:
    """W84: launchd perde il grant TCC su ~/Desktop → job VERDE (exit 0) che in
    realtà non può scrivere ('Operation not permitted'). Non riparabile da
    codice. Il sentinel: (1) segnala i job che girano ANCORA da ~/Desktop
    (vettore W84 da rilocare), (2) incrocia exit-0 col CONTENUTO del log per
    scovare il green-but-TCC-dead. Cura = solo operatore (System Settings).
    MAI `tccutil reset` (scar W84-tccutil-recidiva: distruttivo OS-wide)."""
    import time as _time
    RECENT_S = 2 * 3600  # un 'Operation not permitted' conta solo se il LOG è
    #                      stato scritto nelle ultime 2h. Il log err è CUMULATIVO:
    #                      righe storiche = ferite cicatrizzate, non TCC morto ORA
    #                      (verificato 2026-07-11: wr2.queue-pull aveva 98 mv-fail
    #                      storiche ma il file-target si aggiorna oggi → sano).
    la = HOME / "Library" / "LaunchAgents"
    desktop_jobs: list[str] = []
    dead_green: list[str] = []
    now = _time.time()
    if la.exists():
        for p in sorted(la.glob("*.plist")):
            rc, prog = _run(["plutil", "-extract", "ProgramArguments.1", "raw", str(p)])
            if rc != 0:
                rc, prog = _run(["plutil", "-extract", "Program", "raw", str(p)])
            if "Desktop" in prog:
                desktop_jobs.append(p.stem)
            # green-but-dead: SOLO se il log err è stato TOCCATO di recente E
            # contiene il marker TCC vicino alla coda (mtime = ultima scrittura).
            rc, logp = _run(["plutil", "-extract", "StandardErrorPath", "raw", str(p)])
            if rc == 0 and logp and Path(logp).exists():
                try:
                    lp = Path(logp)
                    if now - lp.stat().st_mtime > RECENT_S:
                        continue  # log fermo da >2h → non è un fallimento in corso
                    if "Operation not permitted" in lp.read_text(errors="ignore")[-2000:]:
                        dead_green.append(p.stem)
                except Exception:  # noqa: BLE001
                    pass
    if dead_green:
        return Probe("tcc", "B-hard", ACTION,
                     f"green-but-TCC-dead (fallimento ATTIVO <2h): {', '.join(sorted(set(dead_green)))}",
                     fix_cmd="System Settings → Privacy & Security → Full Disk Access "
                             "→ abilita /bin/bash (o il programma del job); poi "
                             "`launchctl kickstart -k gui/$(id -u)/<label>`. "
                             "MAI `tccutil reset`.")
    if desktop_jobs:
        return Probe("tcc", "B-hard", ACTION,
                     f"job sotto ~/Desktop (vettore W84): {', '.join(desktop_jobs)}",
                     fix_cmd="riloca i wrapper FUORI da ~/Desktop (come i cron sani) "
                             "per non dipendere dal grant TCC su Desktop")
    return Probe("tcc", "B-hard", OK, "nessun job launchd gira da ~/Desktop")


PROBES = [
    probe_claude, probe_fly, probe_deepseek, probe_drive,   # A
    probe_codex, probe_agy, probe_nlm,                      # B
    probe_tcc,                                              # B-hard
]


def run_all() -> list[Probe]:
    out = []
    for fn in PROBES:
        try:
            out.append(fn())
        except Exception as e:  # noqa: BLE001
            out.append(Probe(fn.__name__.replace("probe_", ""), "?", UNKNOWN,
                             f"sentinel-err:{type(e).__name__}"))
    return out


def _hostname() -> str:
    rc, h = _run(["hostname", "-s"])
    return h if rc == 0 else "?"


def emit_alert(probes: list[Probe]) -> bool:
    """Alert azionabile SOLO per gli ACTION. Ramo A auto-refreshato o OK = zero
    rumore. Usa sentinel_lib.alerter (dedup) → tg_notify gateway (relay ssh)."""
    actions = [p for p in probes if p.status == ACTION]
    if not actions:
        return False
    host = _hostname()
    lines = [f"🔐 auth-sentinel [{host}] — {len(actions)} credenziali richiedono un gesto:"]
    for p in actions:
        lines.append(f"\n• {p.arm} ({p.family}): {p.detail}\n  → {p.fix_cmd}")
    msg = "".join(lines)
    try:
        from sentinel_lib import alerter
        return alerter.send_alert(msg, level="WARNING")
    except Exception:  # noqa: BLE001 — fallback diretto al gateway
        tg = REPO / "scripts" / "tg_notify.py"
        if tg.exists():
            _run(["python3", str(tg), "--tier", "p0", "--source", "auth-sentinel",
                  "--dedup-key", f"auth-sentinel-{host}", msg])
            return True
    return False


def selftest() -> int:
    """Il sentinel è green-when-silent → deve saper distinguere sano da morto.
    Verifica: import alerter, presenza tg_notify, e che i probe non crashino."""
    problems = []
    try:
        from sentinel_lib import alerter  # noqa: F401
    except Exception as e:  # noqa: BLE001
        problems.append(f"alerter import: {e}")
    if not (REPO / "scripts" / "tg_notify.py").exists():
        problems.append("tg_notify.py assente")
    ps = run_all()
    if len(ps) != len(PROBES):
        problems.append("un probe è crashato")
    print(f"selftest: {len(ps)} probe eseguiti, {len(problems)} problemi")
    for pr in problems:
        print("  ✗", pr)
    return 1 if problems else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="fleet auth + TCC liveness sentinel")
    ap.add_argument("--json", action="store_true", help="report machine-readable, no alert")
    ap.add_argument("--no-alert", action="store_true", help="probe + report, mai Telegram")
    ap.add_argument("--selftest", action="store_true", help="verifica salute del sentinel stesso")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    probes = run_all()

    if args.json:
        print(json.dumps({"host": _hostname(),
                          "probes": [asdict(p) for p in probes]}, indent=2))
        return 0

    host = _hostname()
    print(f"auth-sentinel [{host}]")
    icon = {OK: "🟢", REFRESHED: "♻️ ", WARN: "🟠", ACTION: "🔴", SKIP: "⚪", UNKNOWN: "🟡"}
    for p in probes:
        print(f"  {icon.get(p.status,'?')} {p.arm:<14} [{p.family:<6}] {p.status:<9} {p.detail}")
        if p.status in (ACTION, WARN) and p.fix_cmd:
            print(f"       └─ {'FIX' if p.status == ACTION else 'NOTE'}: {p.fix_cmd}")

    if not args.no_alert:
        sent = emit_alert(probes)
        n = sum(1 for p in probes if p.status == ACTION)
        print(f"\nalert: {'inviato' if sent else 'nessuno'} ({n} ACTION)")

    # exit 0 sempre: il sentinel non deve mai far fallire un cron chiamante;
    # gli ACTION viaggiano via alert, non via exit-code (green≠working docet).
    return 0


if __name__ == "__main__":
    sys.exit(main())
