#!/usr/bin/env python3
"""Render the organism's merge-queue state as one page a non-developer can read.

WHY THIS EXISTS. The state of the work is spread across surfaces that each
answer a different question and none of which answer "what is stuck, and
why": `gh pr list` shows titles, the merge queue shows positions, the checks
tab shows red/green per PR. Reading them together is a developer's job. Zero
is not a developer and should not have to do it, so this collapses them into
one page whose top line is the only sentence that matters: how many pieces of
work are moving, how many are stuck, and what the single biggest cause is.

WHY A GENERATOR AND NOT A HAND-WRITTEN PAGE. A dashboard written by hand is
true for one minute and then lies quietly. This script measures every number
it prints, at the moment it prints it, and stamps the page with that moment.
Re-run it and republish to the same artifact URL and the page updates; there
is no second copy of the numbers to drift.

THE THREE PROBES AND WHY EACH IS THE ONE USED (each replaces a proxy that
was measured lying, in this repo, on 2026-09-01):

  1. ARMED is read from `mergeQueueEntry`, never from `autoMergeRequest`.
     `autoMergeRequest` is null in three completely different states —
     never armed, armed-then-ejected, and armed-then-CONSUMED by the queue —
     so a PR sitting at queue position 1 reports "not armed". Measured:
     #5458/#5459/#5460 all showed autoMergeRequest=null while holding queue
     positions 3/2/1.

  2. CONFLICT is split into PHANTOM and REAL by a local trial merge, never
     taken from GitHub's `mergeable` field alone. `.gitattributes` declares
     `merge=union` on the PENDING-ARMS ledger; git honours that driver and
     GitHub's server-side mergeability does not, so two PRs that both append
     a ledger row make the second one report CONFLICTING while
     `git merge-tree --write-tree` returns clean. Measured the same day: of
     8 PRs flagged DIRTY, 5 were phantoms. Reporting those 5 as conflicts
     sends a person to hand-resolve a file whose hand-resolution DELETES
     other lanes' rows.

  3. WHY IT IS RED is grouped by the failing check's NAME across all PRs,
     not listed per PR. One check accounted for 12 of the 34 live PRs that
     morning; per-PR listing hides that shape completely, and the shape is
     the actionable fact — it is the difference between "twelve problems"
     and "one problem, twelve times".

Read-only. Runs `gh` and `git`; writes exactly one HTML file. Never mutates
a PR, never arms, never merges.

Usage:
    python3 scripts/fleet_dashboard.py --out /tmp/dashboard.html
    python3 scripts/fleet_dashboard.py --out /tmp/d.html --json /tmp/d.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO = "Bali-Zero/Teman2"

# git is refused in the main checkout by the worktree-isolation hook, and a
# worktree shares the object database, so every git probe runs from wherever
# this script lives — which is always inside a worktree or the checkout root.
GIT_CWD = Path(__file__).resolve().parent.parent


def _run(args: list[str], timeout: int = 90) -> tuple[int, str]:
    """Run a command, returning (rc, stdout). Never raises on a non-zero rc.

    The captured-rc form is deliberate: under `bash -e` (and in CI) a bare
    `out = $(cmd)` aborts the whole step at the assignment, taking the
    diagnostic with it. Here the caller always gets to see what happened.
    """
    try:
        p = subprocess.run(
            args, cwd=str(GIT_CWD), capture_output=True, text=True, timeout=timeout
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return 1, f"{type(exc).__name__}: {exc}"
    return p.returncode, p.stdout


GRAPHQL = """
query {
  repository(owner: "%s", name: "%s") {
    pullRequests(states: OPEN, first: 100) {
      nodes {
        number title isDraft mergeable mergeStateStatus headRefName headRefOid
        updatedAt
        author { login }
        autoMergeRequest { enabledAt }
        mergeQueueEntry { position state }
        commits(last: 1) { nodes { commit { statusCheckRollup {
          state
          contexts(first: 100) { nodes {
            __typename
            ... on CheckRun { name conclusion }
            ... on StatusContext { context state }
          } }
        } } } }
      }
    }
  }
}
""" % tuple(REPO.split("/"))


def fetch_open_prs() -> list[dict[str, Any]]:
    rc, out = _run(["gh", "api", "graphql", "-f", f"query={GRAPHQL}"])
    if rc != 0 or not out.strip():
        raise SystemExit(f"gh graphql failed (rc={rc}): {out[:400]}")
    return json.loads(out)["data"]["repository"]["pullRequests"]["nodes"]


def failing_checks(pr: dict[str, Any]) -> list[str]:
    commits = pr["commits"]["nodes"]
    if not commits:
        return []
    rollup = commits[0]["commit"]["statusCheckRollup"]
    if not rollup:
        return []
    out = []
    for ctx in rollup["contexts"]["nodes"]:
        name = ctx.get("name") or ctx.get("context") or "?"
        verdict = ctx.get("conclusion") or ctx.get("state")
        if verdict == "FAILURE":
            out.append(name)
    return out


def rollup_state(pr: dict[str, Any]) -> str:
    commits = pr["commits"]["nodes"]
    if not commits:
        return "—"
    rollup = commits[0]["commit"]["statusCheckRollup"]
    return (rollup or {}).get("state") or "—"


def conflict_kind(pr: dict[str, Any]) -> str:
    """PHANTOM (git merges it clean) vs REAL — never GitHub's word alone.

    GitHub does not honour the `merge=union` driver `.gitattributes` declares
    for the PENDING-ARMS ledger, so it reports a conflict that does not exist
    in git. The cure for the two kinds is opposite: a phantom wants
    `git merge origin/main` in a worktree and a push; a real conflict wants a
    person. Telling them apart is therefore not cosmetic.
    """
    if pr["mergeable"] != "CONFLICTING":
        return "none"
    branch = pr["headRefName"]
    _run(["git", "fetch", "origin", branch, "--quiet"], timeout=120)
    rc, sha = _run(["git", "rev-parse", f"origin/{branch}"])
    if rc != 0:
        return "unknown"
    rc, _ = _run(
        ["git", "merge-tree", "--write-tree", "--name-only", "origin/main", sha.strip()]
    )
    return "phantom" if rc == 0 else "real"


def merged_today() -> list[dict[str, Any]]:
    rc, out = _run(
        ["gh", "pr", "list", "--state", "merged", "--limit", "80",
         "--json", "number,title,mergedAt"]
    )
    if rc != 0 or not out.strip():
        return []
    today = dt.datetime.now(dt.timezone.utc).date()
    rows = []
    for m in json.loads(out):
        when = dt.datetime.fromisoformat(m["mergedAt"].replace("Z", "+00:00"))
        if when.date() == today:
            rows.append(m)
    return rows


def collect() -> dict[str, Any]:
    prs = fetch_open_prs()
    _run(["git", "fetch", "origin", "main", "--quiet"], timeout=120)

    live = [p for p in prs if not p["isDraft"]]
    queued = [p for p in prs if p["mergeQueueEntry"]]
    causes: dict[str, list[int]] = defaultdict(list)
    for p in live:
        for name in failing_checks(p):
            causes[name].append(p["number"])

    conflicts = {p["number"]: conflict_kind(p) for p in prs if p["mergeable"] == "CONFLICTING"}
    phantom = [n for n, k in conflicts.items() if k == "phantom"]
    real = [n for n, k in conflicts.items() if k == "real"]

    red = [p for p in live if rollup_state(p) == "FAILURE"]
    green = [p for p in live if rollup_state(p) == "SUCCESS"]
    # ready = green, no conflict, not yet in the queue: the pile that would
    # move with no work at all, which is the most useful thing to surface.
    ready = [
        p for p in green
        if p["mergeable"] != "CONFLICTING" and not p["mergeQueueEntry"]
    ]

    return {
        "measured_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "repo": REPO,
        "open_total": len(prs),
        "draft": [p["number"] for p in prs if p["isDraft"]],
        "live": [p["number"] for p in live],
        "queued": sorted(
            ({"n": p["number"], "pos": p["mergeQueueEntry"]["position"],
              "title": p["title"]} for p in queued),
            key=lambda d: d["pos"] or 999,
        ),
        "red": [{"n": p["number"], "title": p["title"],
                 "why": failing_checks(p)} for p in red],
        "green": [p["number"] for p in green],
        "ready": [{"n": p["number"], "title": p["title"]} for p in ready],
        "phantom_conflicts": sorted(phantom),
        "real_conflicts": sorted(real),
        "causes": sorted(
            ({"check": k, "prs": sorted(v)} for k, v in causes.items()),
            key=lambda d: -len(d["prs"]),
        ),
        "merged_today": merged_today(),
        "states": dict(Counter(p["mergeStateStatus"] for p in prs)),
    }


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

CSS = """
<style>
:root{
  --ground:#FBF9F7; --panel:#FFFFFF; --ink:#1B1614; --muted:#6E635C;
  --line:#E7E0D9; --line-strong:#D6CCC2;
  --merah:#C8102E;              /* identity, and deliberately also "needs you" */
  --ok:#2F6E4F; --wait:#4C5966; --warn:#8A6116;
  --ok-bg:#EAF3EE; --wait-bg:#EDF0F3; --warn-bg:#F7F0E2; --merah-bg:#FBECEE;
  --shadow:0 1px 2px rgba(27,22,20,.05), 0 8px 24px rgba(27,22,20,.05);
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --ground:#14110F; --panel:#1D1917; --ink:#F2ECE7; --muted:#A2968D;
    --line:#2C2523; --line-strong:#3C332F;
    --merah:#F2637A; --ok:#7CC79F; --wait:#9DB0C2; --warn:#DDB166;
    --ok-bg:#1B2A22; --wait-bg:#1D242B; --warn-bg:#2B2418; --merah-bg:#301A1E;
    --shadow:0 1px 2px rgba(0,0,0,.3), 0 8px 24px rgba(0,0,0,.28);
  }
}
:root[data-theme="dark"]{
  --ground:#14110F; --panel:#1D1917; --ink:#F2ECE7; --muted:#A2968D;
  --line:#2C2523; --line-strong:#3C332F;
  --merah:#F2637A; --ok:#7CC79F; --wait:#9DB0C2; --warn:#DDB166;
  --ok-bg:#1B2A22; --wait-bg:#1D242B; --warn-bg:#2B2418; --merah-bg:#301A1E;
  --shadow:0 1px 2px rgba(0,0,0,.3), 0 8px 24px rgba(0,0,0,.28);
}
*{box-sizing:border-box}
body{
  background:var(--ground); color:var(--ink); margin:0;
  font-family:"Public Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  font-size:16px; line-height:1.55; -webkit-font-smoothing:antialiased;
}
.wrap{max-width:1020px; margin:0 auto; padding:40px 22px 90px}
h1,h2,h3{font-family:Fraunces,Georgia,"Times New Roman",serif; text-wrap:balance; margin:0}
h1{font-size:clamp(30px,4.4vw,46px); font-weight:600; letter-spacing:-.015em;
   font-variation-settings:"SOFT" 20,"WONK" 1}
h2{font-size:22px; font-weight:600; margin:0 0 4px}
.eyebrow{font-size:11.5px; letter-spacing:.14em; text-transform:uppercase;
  color:var(--muted); font-weight:600; font-family:"Public Sans",sans-serif}
.rule{height:3px; background:var(--merah); width:56px; border-radius:2px; margin:14px 0 0}
.stamp{font-family:"JetBrains Mono",ui-monospace,Menlo,monospace;
  font-size:12px; color:var(--muted); margin-top:12px}
.lede{font-size:19px; line-height:1.5; margin:20px 0 0; max-width:64ch; color:var(--ink)}
.lede b{color:var(--merah); font-weight:600}
section{margin-top:52px}
.sub{color:var(--muted); font-size:14.5px; margin:0 0 18px; max-width:70ch}

.cards{display:grid; grid-template-columns:repeat(auto-fit,minmax(158px,1fr)); gap:12px; margin-top:22px}
.card{background:var(--panel); border:1px solid var(--line); border-radius:12px;
  padding:16px 16px 14px; box-shadow:var(--shadow)}
.card .n{font-family:Fraunces,Georgia,serif; font-size:38px; line-height:1;
  font-variant-numeric:tabular-nums; font-weight:600}
.card .k{font-size:12.5px; color:var(--muted); margin-top:7px; line-height:1.35}
.card.is-ok .n{color:var(--ok)} .card.is-wait .n{color:var(--wait)}
.card.is-warn .n{color:var(--warn)} .card.is-merah .n{color:var(--merah)}

table{width:100%; border-collapse:collapse; font-size:14.5px}
.scroll{overflow-x:auto; border:1px solid var(--line); border-radius:12px; background:var(--panel)}
th{text-align:left; font-size:11.5px; letter-spacing:.09em; text-transform:uppercase;
  color:var(--muted); font-weight:600; padding:12px 14px; border-bottom:1px solid var(--line-strong);
  white-space:nowrap}
td{padding:12px 14px; border-bottom:1px solid var(--line); vertical-align:top}
tr:last-child td{border-bottom:none}
td.num{font-family:"JetBrains Mono",ui-monospace,monospace; font-variant-numeric:tabular-nums;
  white-space:nowrap; font-size:13px}
.bar{height:7px; border-radius:4px; background:var(--merah); min-width:5px; display:block}
.mono{font-family:"JetBrains Mono",ui-monospace,monospace; font-size:12.5px; color:var(--muted)}

.pill{display:inline-block; font-size:11.5px; font-weight:600; padding:3px 9px;
  border-radius:99px; white-space:nowrap; font-family:"Public Sans",sans-serif}
.p-ok{background:var(--ok-bg); color:var(--ok)}
.p-wait{background:var(--wait-bg); color:var(--wait)}
.p-warn{background:var(--warn-bg); color:var(--warn)}
.p-merah{background:var(--merah-bg); color:var(--merah)}

.note{border-left:3px solid var(--line-strong); padding:2px 0 2px 16px; color:var(--muted);
  font-size:14px; margin-top:18px; max-width:72ch}
.note b{color:var(--ink)}
ul.plain{margin:14px 0 0; padding-left:19px} ul.plain li{margin:7px 0}
footer{margin-top:64px; padding-top:18px; border-top:1px solid var(--line);
  color:var(--muted); font-size:12.5px}
@media (max-width:560px){ .wrap{padding:28px 15px 70px} .card .n{font-size:32px} }
</style>
"""


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def prlink(n: int) -> str:
    return f'<a class="mono" style="color:inherit" href="https://github.com/{REPO}/pull/{n}">#{n}</a>'


def render(d: dict[str, Any]) -> str:
    live_n = len(d["live"])
    red_n = len(d["red"])
    moving = len(d["queued"]) + len(d["ready"])
    top = d["causes"][0] if d["causes"] else None
    when = d["measured_at"].replace("T", " ").replace("+00:00", " UTC")
    wita = (
        dt.datetime.fromisoformat(d["measured_at"]) + dt.timedelta(hours=8)
    ).strftime("%H:%M")

    if top:
        lede = (
            f'Delle <b>{live_n}</b> proposte di modifica vive, <b>{moving}</b> si stanno '
            f'muovendo da sole e <b>{red_n}</b> sono ferme. La causa più frequente non è '
            f'{red_n} problemi diversi: è <b>una sola</b>, «{esc(top["check"])}», che da sola '
            f'ferma {len(top["prs"])} proposte.'
        )
    else:
        lede = (
            f'Delle <b>{live_n}</b> proposte di modifica vive, <b>{moving}</b> si stanno '
            f'muovendo e nessuna è ferma per un controllo rosso.'
        )

    cards = [
        ("is-wait", len(d["queued"]), "in coda, si fondono da sole"),
        ("is-ok", len(d["ready"]), "verdi e pronte, nessun lavoro da fare"),
        ("is-merah", red_n, "ferme su un controllo rosso"),
        ("is-warn", len(d["real_conflicts"]), "conflitti veri, serve una persona"),
        ("is-wait", len(d["phantom_conflicts"]), "conflitti finti (li scioglie una fusione)"),
        ("is-wait", len(d["draft"]), "bozze, non ancora proposte"),
    ]
    cards_html = "\n".join(
        f'<div class="card {cls}"><div class="n">{n}</div><div class="k">{esc(k)}</div></div>'
        for cls, n, k in cards
    )

    widest = max((len(c["prs"]) for c in d["causes"]), default=1)
    cause_rows = "\n".join(
        f'<tr><td><b>{esc(c["check"])}</b><div class="mono">'
        + ", ".join(prlink(n) for n in c["prs"][:10])
        + (" …" if len(c["prs"]) > 10 else "")
        + f'</div></td><td class="num">{len(c["prs"])}</td>'
        f'<td style="width:34%"><span class="bar" style="width:'
        f'{round(100 * len(c["prs"]) / widest)}%"></span></td></tr>'
        for c in d["causes"]
    ) or '<tr><td colspan="3">Nessun controllo rosso.</td></tr>'

    queue_rows = "\n".join(
        f'<tr><td class="num">{q["pos"]}</td><td class="num">{prlink(q["n"])}</td>'
        f'<td>{esc(q["title"])}</td></tr>'
        for q in d["queued"]
    ) or '<tr><td colspan="3">La coda è vuota.</td></tr>'

    ready_rows = "\n".join(
        f'<tr><td class="num">{prlink(r["n"])}</td><td>{esc(r["title"])}</td>'
        f'<td><span class="pill p-ok">verde</span></td></tr>'
        for r in d["ready"]
    ) or '<tr><td colspan="3">Nessuna in attesa: tutto ciò che è verde è già in coda.</td></tr>'

    # The "ready" pile is routinely dominated by dependency bumps, and they are
    # the one case where "all green, arm them all" is the WRONG move: bumps that
    # share a lockfile invalidate each other the moment the first one lands, so
    # arming them together burns a queue cycle per PR. Saying so here is the
    # difference between a page that informs and a page that misleads.
    bumps = [r for r in d["ready"] if r["title"].lower().startswith("chore(deps")]
    ready_note = ""
    if len(bumps) >= 2:
        ready_note = (
            f'<div class="note"><b>{len(bumps)} di queste sono aggiornamenti di dipendenze.</b> '
            "Vanno armate <em>una per volta</em>: condividono lo stesso file di lock, quindi "
            "la prima che entra invalida le altre e armarle insieme spreca un giro di coda "
            "per ciascuna.</div>"
        )

    merged_rows = "\n".join(
        f'<tr><td class="num">{prlink(m["number"])}</td><td>{esc(m["title"])}</td></tr>'
        for m in d["merged_today"]
    ) or '<tr><td colspan="2">Niente ancora oggi.</td></tr>'

    conf = ""
    if d["phantom_conflicts"] or d["real_conflicts"]:
        conf = f"""
<section>
  <div class="eyebrow">Conflitti</div>
  <h2>Due malattie con lo stesso nome</h2>
  <p class="sub">GitHub scrive «conflitto» in due casi che non si curano allo stesso modo.
  Questa pagina li separa provando la fusione in locale, dove git applica la regola
  <span class="mono">merge=union</span> che GitHub ignora.</p>
  <div class="scroll"><table>
    <tr><th>Tipo</th><th>Proposte</th><th>Cosa serve</th></tr>
    <tr><td><span class="pill p-wait">finto</span></td>
        <td class="num">{" ".join(prlink(n) for n in d["phantom_conflicts"]) or "—"}</td>
        <td>Git le fonde pulite. Basta fondere <span class="mono">origin/main</span> nel ramo
            e ripubblicare. <b>Mai</b> risolvere il file a mano: cancella le righe di altri.</td></tr>
    <tr><td><span class="pill p-warn">vero</span></td>
        <td class="num">{" ".join(prlink(n) for n in d["real_conflicts"]) or "—"}</td>
        <td>Due modifiche incompatibili sullo stesso punto. Qui serve una decisione.</td></tr>
  </table></div>
</section>"""

    return f"""<title>Stato dell'organismo</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400..700&family=Public+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap">
{CSS}
<div class="wrap">
  <header>
    <div class="eyebrow">Bali Zero · Nuzantara</div>
    <h1>Stato dell'organismo</h1>
    <div class="rule"></div>
    <p class="lede">{lede}</p>
    <div class="stamp">misurato {esc(when)} · {esc(wita)} WITA · {esc(d["repo"])} · {d["open_total"]} proposte aperte</div>
  </header>

  <section>
    <div class="eyebrow">In una riga</div>
    <h2>Dove sta il lavoro adesso</h2>
    <div class="cards">{cards_html}</div>
  </section>

  <section>
    <div class="eyebrow">La domanda che conta</div>
    <h2>Perché sono ferme</h2>
    <p class="sub">Raggruppate per <em>controllo fallito</em>, non per proposta. Una riga lunga
    significa un solo difetto ripetuto tante volte — si cura una volta e si sbloccano tutte.</p>
    <div class="scroll"><table>
      <tr><th>Controllo che fallisce</th><th>Quante</th><th></th></tr>
      {cause_rows}
    </table></div>
  </section>

  <section>
    <div class="eyebrow">In movimento</div>
    <h2>La coda</h2>
    <p class="sub">Queste si fondono da sole, in quest'ordine. Nessuno deve fare niente.</p>
    <div class="scroll"><table>
      <tr><th>Pos.</th><th>Proposta</th><th>Titolo</th></tr>
      {queue_rows}
    </table></div>
    <div class="note"><b>Nota tecnica, per chi verrà dopo:</b> lo stato «armata» qui è letto da
    <span class="mono">mergeQueueEntry</span>. Il campo che sembra dirlo,
    <span class="mono">autoMergeRequest</span>, è vuoto in tre situazioni diverse — mai armata,
    armata e poi espulsa, armata e <em>consumata dalla coda</em> — quindi una proposta in prima
    posizione risulterebbe «non armata».</div>
  </section>

  <section>
    <div class="eyebrow">Pronte</div>
    <h2>Verdi, senza conflitti, non ancora in coda</h2>
    <div class="scroll"><table>
      <tr><th>Proposta</th><th>Titolo</th><th>Controlli</th></tr>
      {ready_rows}
    </table></div>
    {ready_note}
  </section>
{conf}
  <section>
    <div class="eyebrow">Oggi</div>
    <h2>Cosa è entrato</h2>
    <div class="scroll"><table>
      <tr><th>Proposta</th><th>Titolo</th></tr>
      {merged_rows}
    </table></div>
  </section>

  <footer>
    Generata da <span class="mono">scripts/fleet_dashboard.py</span>. Ogni numero di questa pagina
    è misurato al momento indicato in alto — nessuno è scritto a mano. Ri-eseguire lo script e
    ripubblicare aggiorna la pagina allo stesso indirizzo.
  </footer>
</div>
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, help="path of the HTML file to write")
    ap.add_argument("--json", dest="json_out", help="also dump the raw measurements")
    args = ap.parse_args(argv)

    data = collect()
    Path(args.out).write_text(render(data), encoding="utf-8")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(data, indent=2), encoding="utf-8")

    print(
        f"fleet_dashboard: {args.out} — {len(data['live'])} live, "
        f"{len(data['queued'])} queued, {len(data['red'])} red, "
        f"{len(data['phantom_conflicts'])} phantom + {len(data['real_conflicts'])} real conflicts"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
