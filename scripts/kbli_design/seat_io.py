#!/usr/bin/env python3
"""seat_io.py — the seat door of the KBLI Navigator design contest (infra/workflows/kbli-nav-design.js).

  prepare  the round counter on disk (cap 1 per stage+slot: a restart cannot buy a second round), the C6
           family check against the slot's builder, and kit/prompts/<stage>-<slot>.md assembled from
           scripts/kbli_design/briefs/ + kit files — the same bytes whichever seat answers.
  run      prepare, then ONE codex (Sol) or agy (Gemini) one-shot from an empty temp dir, stdin closed,
           material inlined (F5/F6). --detach prints "pending" at once; `wait` polls kit/raw/*.status.
  ingest   r1/repair: split the answer into kit/mockups/<slot>/<stage>/ + manifest.json (sha256).
           grade/refute: keep objections carrying an F/C ref and a `Test:` line (dynamic_workflow's filter).
Every result is one printed line; the workflow compares lines, never exit codes.
"""
from __future__ import annotations
import argparse, fcntl, hashlib, json, re, subprocess, sys, tempfile, time
from pathlib import Path
REPO, HERE = Path(__file__).resolve().parents[2], Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
from scripts.dynamic_workflow import _filter_objection_paragraph, _normalise_seat_output, _split_objections  # noqa: E402
from scripts.lib.codex_seat import codex_seat_env  # noqa: E402

STAGES = ("r1", "repair", "grade", "refute")
FAMILY = {"sol": "openai", "gemini": "google", "sonnet": "anthropic", "opus": "anthropic"}
HTML = tuple(f"{s}.html" for s in ("search-results-day", "registry-table-day", "detail-card-day", "dossier-day",
                                    "sheet-ledger-day", "chat-day", "detail-card-night", "registry-table-night"))
FILES = HTML + ("thesis.md", "derivability.md", "self-report.md", "motion.md")
FILE_RE = re.compile(r"^=== FILE: (\S+) ===[ \t]*\n(.*?)\n=== END FILE ===[ \t]*$", re.S | re.M)
TIMEOUT_S = {"sol": 3000, "gemini": 1500}
DIAG = "docs/design/diagnosis-2026-09-17.md"
sha = lambda b: hashlib.sha256(b).hexdigest()


class Refused(Exception):
    """A refusal the workflow must SEE: printed on stdout as one `refused:` line, never a traceback."""
sec = lambda title, body: f"\n\n## {title}\n\n{body.rstrip()}\n"
brief = lambda name: (HERE / "briefs" / f"{name}.md").read_text(encoding="utf-8")


def final_stage(kit: Path, slot: str) -> str:
    return "repair" if (kit / "mockups" / slot / "repair" / "manifest.json").is_file() else "r1"


def set_text(kit: Path, slot: str, stage: str, names: tuple[str, ...]) -> str:
    d = kit / "mockups" / slot / stage
    return "".join(sec(f"{stage}/{n}", (d / n).read_text(encoding="utf-8")) for n in names)


def assemble(kit: Path, slot: str, stage: str, app: Path) -> str:
    pack = (kit / "content-pack.json").read_text(encoding="utf-8")
    if stage == "r1":
        diag = app / DIAG
        if sha(diag.read_bytes()) != json.loads(pack)["inputs"].get(DIAG):
            raise Refused(f"refused: {diag} differs from the bytes content-pack.json hashed")
        return brief("seat") + sec("Content pack (content-pack.json)", pack) + sec("Measured diagnosis 2026-09-17", diag.read_text(encoding="utf-8"))
    if stage == "repair":
        probes = json.loads((kit / "probes-r1.json").read_text()).get(slot, {})
        objections = kit / "verify" / f"{slot}.md"
        return ((kit / "prompts" / f"r1-{slot}.md").read_text(encoding="utf-8") + "\n\n" + brief("repair")
                + sec("Your first answer", (kit / "raw" / f"r1-{slot}.md").read_text(encoding="utf-8"))
                + sec("Probe row for your set (probes-r1.json)", json.dumps(probes, indent=1, ensure_ascii=False))
                + sec("Objections the grader kept", objections.read_text(encoding="utf-8") if objections.is_file() else "(none)"))
    if stage == "grade":
        return (brief("grade") + sec("The brief the author received", brief("seat")) + sec("Content pack", pack)
                + set_text(kit, slot, "r1", HTML) + sec("AUTHOR SELF-REPORT — open only after your objections are written",
                                                        (kit / "mockups" / slot / "r1" / "self-report.md").read_text(encoding="utf-8")))
    recs = {r["kode_kbli_2025"]: r for r in json.loads((REPO / "data/source_documents/KBLI_2025_FINAL_CLEAN.json").read_bytes())["data"]}
    canon = json.dumps({c: recs[c] for c in json.loads(pack)["frozen"]}, ensure_ascii=False, indent=1)
    return (brief("refute") + sec("Canonical records (KBLI_2025_FINAL_CLEAN.json)", canon) + sec("Content pack", pack)
            + set_text(kit, slot, final_stage(kit, slot), HTML + ("derivability.md",)))


def prepare(kit: Path, slot: str, stage: str, seat: str, app: Path) -> str:
    (kit / "prompts").mkdir(parents=True, exist_ok=True)
    with open(kit / "rounds.json.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = kit / "rounds.json"
        rounds = json.loads(path.read_text()) if path.is_file() else {}
        builder = rounds.get(f"r1/{slot}")
        if f"{stage}/{slot}" in rounds:
            return f"refused: {stage}/{slot} at cap 1/1 (taken by {rounds[f'{stage}/{slot}']})"
        if stage == "repair" and seat != builder:
            return f"refused: repair/{slot} by {seat}, but {builder} built it"
        if stage in ("grade", "refute") and (builder is None or FAMILY[seat] == FAMILY[builder]):
            return f"refused: C6, {stage}/{slot} by {seat} on a set built by {builder}"
        try:
            prompt = assemble(kit, slot, stage, app)
        except Refused as e:
            return str(e)
        (kit / "prompts" / f"{stage}-{slot}.md").write_text(prompt, encoding="utf-8")
        path.write_text(json.dumps({**rounds, f"{stage}/{slot}": seat}, indent=1, sort_keys=True) + "\n")
    return f"granted {stage}/{slot} 1/1 prompt={sha(prompt.encode())[:16]}"


def launch(seat: str, prompt: str) -> str:
    try:
        with tempfile.TemporaryDirectory() as tmp:
            if seat == "sol":
                out = Path(tmp) / "answer.md"
                subprocess.run(["codex", "exec", "-m", "gpt-5.6-sol", "-c", 'model_reasoning_effort="xhigh"', "-C", tmp,
                                "-s", "read-only", "--skip-git-repo-check", "-o", str(out), prompt],
                               stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=TIMEOUT_S[seat], env=codex_seat_env())
                return out.read_text(encoding="utf-8") if out.is_file() else ""
            return subprocess.run(["agy", "-p", prompt, "--model", "gemini-3.1-pro-high", "--output-format", "text"],
                                  stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=TIMEOUT_S[seat], cwd=tmp).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def ingest(kit: Path, slot: str, stage: str, seat: str) -> str:
    raw = kit / "raw" / f"{stage}-{slot}.md"
    text = _normalise_seat_output(raw.read_text(encoding="utf-8")) if raw.is_file() else ""
    verdict = text.split("\n", 1)[0] if text.startswith("VERDICT:") else ""
    if stage in ("r1", "repair"):
        files = dict(FILE_RE.findall(text))
        if lost := [f for f in FILES if f not in files]:
            return f"{slot} {stage} dead: " + ("empty answer" if not text else f"missing {','.join(lost)}")
        d = kit / "mockups" / slot / stage
        d.mkdir(parents=True, exist_ok=True)
        for name in FILES:
            (d / name).write_text(files[name] + "\n", encoding="utf-8")
        man = {"seat": seat, "verdict": verdict, "raw_sha256": sha(raw.read_bytes()),
               "files": {n: sha((d / n).read_bytes()) for n in FILES}}
        (d / "manifest.json").write_text(json.dumps(man, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        return f"{slot} {stage} files={len(FILES)} manifest={sha((d / 'manifest.json').read_bytes())[:16]}"
    if not text:
        return f"{stage} {slot} by {seat} dead: empty answer"
    kept, rejected, kc, rc = [], [], 0, 0
    for p in _split_objections(text[len(verdict):]):
        k, r, a, b = _filter_objection_paragraph(p)
        kept, rejected, kc, rc = kept + [k] * bool(k), rejected + [r] * bool(r), kc + a, rc + b
    out = kit / ("verify" if stage == "grade" else "r2")
    out.mkdir(exist_ok=True)
    (out / f"{slot}.md").write_text(f"{verdict}\n\n" + "\n\n".join(kept) + "\n", encoding="utf-8")
    (out / f"{slot}.rejected.md").write_text("\n\n".join(rejected) + "\n", encoding="utf-8")
    return f"{stage} {slot} by {seat} kept={kc} rejected={rc}"


def job(kit: Path, slot: str, stage: str, seat: str) -> str:
    status = kit / "raw" / f"{stage}-{slot}.status"
    with open(kit / "rounds.json.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        rounds = json.loads((kit / "rounds.json").read_text()) if (kit / "rounds.json").is_file() else {}
        if rounds.get(f"{stage}/{slot}") != seat or not status.is_file() or status.read_text().strip() != "pending":
            return f"refused: {stage}/{slot} has no pending grant for {seat}"
        status.write_text("running\n")
    answer = launch(seat, (kit / "prompts" / f"{stage}-{slot}.md").read_text(encoding="utf-8"))
    (kit / "raw" / f"{stage}-{slot}.md").write_text(answer, encoding="utf-8")
    line = ingest(kit, slot, stage, seat)
    (kit / "raw" / f"{stage}-{slot}.status").write_text(line + "\n")
    return line


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=("prepare", "run", "wait", "ingest", "_job"))
    ap.add_argument("--kit", type=Path, required=True)
    ap.add_argument("--slot", required=True, choices=("a", "b", "c"))
    ap.add_argument("--stage", required=True, choices=STAGES)
    ap.add_argument("--seat", choices=tuple(FAMILY))
    ap.add_argument("--app", type=Path, default=Path.home() / "kbli-navigator-app")
    ap.add_argument("--detach", action="store_true")
    ap.add_argument("--max-s", type=int, default=570)
    a = ap.parse_args(argv)
    kit, status = a.kit.resolve(), a.kit.resolve() / "raw" / f"{a.stage}-{a.slot}.status"
    if any((d / ".git").exists() for d in (kit, *kit.parents)):
        return print(f"refused: kit {kit} is inside a git checkout; it must live outside the repo (C3)") or 0
    if a.cmd in ("prepare", "run", "ingest", "_job") and not a.seat:
        return print(f"refused: {a.cmd} needs --seat") or 2
    if a.cmd == "wait":
        for _ in range(max(1, a.max_s // 5)):
            line = status.read_text().strip() if status.is_file() else "missing status"
            if line not in ("pending", "running"):
                return print(line) or 0
            time.sleep(5)
        return print("pending") or 0
    if a.cmd in ("ingest", "_job"):
        return print(ingest(kit, a.slot, a.stage, a.seat) if a.cmd == "ingest" else job(kit, a.slot, a.stage, a.seat)) or 0
    if a.cmd == "run" and a.seat not in TIMEOUT_S:
        return print(f"refused: run is for codex/agy seats, {a.seat} is a native lane") or 2
    granted = prepare(kit, a.slot, a.stage, a.seat, a.app)
    print(granted)
    if a.cmd == "prepare" or not granted.startswith("granted"):
        return 0
    (kit / "raw").mkdir(exist_ok=True)
    status.write_text("pending\n")
    if not a.detach:
        return print(job(kit, a.slot, a.stage, a.seat)) or 0
    with open(kit / "raw" / f"{a.stage}-{a.slot}.log", "w") as log:
        subprocess.Popen([sys.executable, "-I", __file__, "_job", "--kit", str(kit), "--slot", a.slot, "--stage", a.stage,
                          "--seat", a.seat], stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    return print("pending") or 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
