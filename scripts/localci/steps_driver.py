#!/usr/bin/env python3
"""Run one required context's steps inside the candidate container and write one junit <testcase> per step, in plan order.

Runner-owned: runner.py injects this file and its steps config at /cfg (never from the candidate tree) and pins its sha256 in
the plan. Usage: python -I steps_driver.py <steps.json> <junit.xml>

Exit 0 = every executed step returned 0 · 1 = at least one step failed · 4 = a step was killed by a signal and none failed ·
3 = a step could not start and nothing worse happened · 2 = the driver itself broke (no verdict). Every step runs even after a
failure: the junit is the per-step evidence. A verbatim `run:` body is written to a file and its path replaces `{0}` in GitHub's
shell template, as the hosted runner does.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

GIT_ID = {"GIT_AUTHOR_NAME": "localci", "GIT_AUTHOR_EMAIL": "localci@invalid", "GIT_COMMITTER_NAME": "localci",
          "GIT_COMMITTER_EMAIL": "localci@invalid"}


def index_tree(root: str, history: dict | None, base_dir: Path) -> None:
    """Steps that call `git ls-files`/`git diff` see the frozen tree as a commit. The tar carries tracked blobs only, so `add -f`
    indexes exactly the candidate's tracked set (ignored-but-tracked files included). With `history`, BASE is rebuilt first —
    the candidate's index minus the paths it added, plus the BASE blob and mode of every path it changed (<cfg dir>/base/<path>) — and
    the candidate commit sits on it: `main`, `origin/main` and a fetch of `origin main` (origin = this repo) all name BASE."""
    env = {**os.environ, **GIT_ID}

    def git(*args: str, data: str | None = None) -> str:
        return subprocess.run(["git", *args], cwd=root, env=env, input=data, check=True, capture_output=True, text=True).stdout.strip()

    git("init", "-q", "-b", "localci")
    git("add", "-A", "-f")
    if history is not None:
        git("update-index", "--force-remove", "-z", "--stdin", data="".join(f"{p}\0" for p in history["added"]))
        paths = [str(base_dir / p) for p, _, _ in history["base"]]
        oids = git("hash-object", "-w", "--no-filters", "--stdin-paths", data="".join(f"{p}\n" for p in paths)).split() if paths else []
        if oids != [o for _, _, o in history["base"]]:
            raise RuntimeError("a BASE blob shipped into the sandbox does not hash to the BASE object it claims to be")
        git("update-index", "-z", "--index-info", data="".join(f"{m} {o}\t{p}\0" for p, m, o in history["base"]))
        base = git("commit-tree", git("write-tree"), "-m", "localci BASE")
        git("update-ref", "refs/heads/main", base)
        git("update-ref", "refs/remotes/origin/main", base)
        git("remote", "add", "origin", root)
        git("update-ref", "HEAD", base)
        git("add", "-A", "-f")
    git("commit", "-q", "--no-verify", "--allow-empty", "-m", "localci candidate tree")
    git("repack", "-a", "-d", "-q")   # packed, as a fresh fetch is: thousands of loose objects invite an auto-gc mid-step


def bare_python(prefix: str) -> str:
    """setup-python hands the job an interpreter with nothing installed: a venv of the pinned one, so a step sees exactly what the
    steps before it `pip install`ed (offline, from the image's wheelhouse) and never a package another job needed."""
    venv = Path("/tmp/localci-python")
    subprocess.run([os.path.join(prefix, "python3") if prefix else "python3", "-m", "venv", str(venv)], check=True, stdout=subprocess.DEVNULL)
    return str(venv / "bin")


def read_kv_file(p: Path) -> tuple[dict, str | None]:
    """GITHUB_OUTPUT as the hosted Linux runner reads it back (FileCommandManager): UTF-8 (a BOM dropped), lines split on \\n only
    (a \\r stays in the value), empty lines skipped, `key=value` or `key<<DELIM` ... a line exactly DELIM; an empty key or delimiter,
    a line of neither shape, a missing delimiter or a value line with no newline fails the step there, so it fails it here.
    -> (outputs, error)."""
    lines = p.read_bytes().decode("utf-8-sig", "replace").split("\n") if p.exists() else [""]
    has_nl = [True] * (len(lines) - 1) + [False]
    if lines[-1] == "":
        lines, has_nl = lines[:-1], has_nl[:-1]
    out, i = {}, 0
    while i < len(lines):
        ln, i = lines[i], i + 1
        if not ln:
            continue
        eq, hd = ln.find("="), ln.find("<<")
        if eq >= 0 and (hd < 0 or eq < hd):
            key, val = ln.split("=", 1)
        elif hd >= 0:
            key, delim = ln.split("<<", 1)
            if not key or not delim:
                return out, f"GITHUB_OUTPUT: invalid format {ln!r}"
            buf = []
            while i >= len(lines) or lines[i] != delim:
                if i >= len(lines) or not has_nl[i]:
                    return out, f"GITHUB_OUTPUT: no matching delimiter for {ln!r}"
                buf.append(lines[i])
                i += 1
            val, i = "\n".join(buf), i + 1
        else:
            return out, f"GITHUB_OUTPUT: invalid format {ln!r}"
        if not key:
            return out, f"GITHUB_OUTPUT: invalid format {ln!r}"
        out[key] = val
    return out, None


def expr_steps(cfg: dict, root: str, prefix: str, gh: Path, suite) -> tuple[int, int, int, int]:
    """Expression mode (service contexts): `if:` decided as the hosted runner decides it, `${{ }}` in env and bodies evaluated at
    step start, `continue-on-error` and step `timeout-minutes` honoured, outputs read back for later steps, and emulated artifact
    steps. A step with no `if:` is `success()`, so after a failure only `always()`/`failure()` steps run, as hosted; `job.status`
    is the job's status as it stands."""
    sys.path.insert(0, str(Path(__file__).parent))
    import gh_expr as X   # noqa: PLC0415 — runner-owned, shipped beside this driver and sha-pinned with it
    import resource       # noqa: PLC0415

    ctx = {**cfg["expr"], "steps": {}, "env": {}}
    status, failed, killed, blocked, skipped = "success", 0, 0, 0, 0
    jenv: dict = {}
    for k, v in (cfg.get("job_env") or {}).items():
        jenv[k] = X.substitute(str(v), {**ctx, "env": jenv}, status)
    for i, st in enumerate(cfg["steps"]):
        case = ET.SubElement(suite, "testcase", classname="localci.ctx", name=st["name"])
        if "not_applicable" in st:
            skipped += 1
            ET.SubElement(case, "skipped", message=st["not_applicable"])
            continue
        ctx["env"], ctx["job"] = jenv, {"status": status}
        if not X.step_runs(st.get("if"), ctx, status):
            skipped += 1
            ET.SubElement(case, "skipped", message=f"if: {' '.join(str(st.get('if', 'success()')).split())} -> false (status {status})")
            if st.get("id"):
                ctx["steps"][st["id"]] = {"outputs": {}, "outcome": "skipped", "conclusion": "skipped"}
            continue
        senv = {**jenv, **{k: X.substitute(str(v), ctx, status) for k, v in (st.get("env") or {}).items()}}
        ctx["env"] = senv
        outp = gh / f"github_output-{i}"
        path = os.pathsep.join(p for p in (prefix, os.environ.get("PATH")) if p)
        env = {**os.environ, "PATH": path, **cfg.get("env", {}), **senv, "GITHUB_OUTPUT": str(outp), "GITHUB_STEP_SUMMARY": str(gh / f"summary-{i}")}
        Path(env.get("RUNNER_TEMP", "/tmp")).mkdir(parents=True, exist_ok=True)
        print(f"##[localci] step {i}: {st['name']}", flush=True)
        t0, cpu0, rc, note = time.monotonic(), resource.getrusage(resource.RUSAGE_CHILDREN), None, ""
        if "precomputed" in st:   # run by the runner outside this sandbox (BASE judge on the host, or a declared egress step)
            rc, note = st["precomputed"].get("rc"), st["precomputed"].get("reason", "")
            print(st["precomputed"].get("log", ""), flush=True)
        elif "emulate" in st:     # actions/upload-artifact and download-artifact: the runner moves the files; the step checks them here
            em = st["emulate"]
            p = Path(root) / X.substitute(em.get("path", ""), ctx, status)
            have = p.is_dir() and any(p.iterdir()) or p.is_file()
            rc = 1 if (em["action"] == "upload" and not have and em.get("if_no_files_found", "warn") == "error") else 0
            note = f"{em['action']} {p}: {'files present' if have else 'no files'}"
        else:
            argv = st["argv"]
            if "script" in st:
                script = gh / f"step-{i}.sh"
                script.write_text(X.substitute(st["script"], ctx, status))
                argv = [str(script) if a == "{0}" else a for a in argv]
            try:
                rc = subprocess.run(argv, cwd=os.path.join(root, st.get("cwd") or "."), env=env, timeout=st.get("timeout_s")).returncode
            except OSError as e:
                note = f"could not start: {type(e).__name__}: {e}"
            except subprocess.TimeoutExpired:
                rc, note = 124, f"step timeout-minutes ({st.get('timeout_s')}s) exceeded"
        outputs, bad = read_kv_file(outp)
        if bad and rc == 0:
            rc, note = 1, bad
        cpu1 = resource.getrusage(resource.RUSAGE_CHILDREN)
        case.set("time", f"{time.monotonic() - t0:.3f}")
        case.set("cpu", f"{cpu1.ru_utime + cpu1.ru_stime - cpu0.ru_utime - cpu0.ru_stime:.3f}")
        outcome = "success" if rc == 0 else "failure"
        coe = rc != 0 and bool(st.get("continue_on_error"))   # hosted: outcome failure, conclusion success, the job goes on
        if rc is not None and rc > 0 and coe:
            case.set("outcome", "failure")
            ET.SubElement(case, "system-out").text = f"rc={rc} {note}".strip()
        elif rc is None:   # no verdict on the candidate either way: BLOCKED, whatever continue-on-error says
            blocked, status = blocked + 1, status if coe else "failure"
            ET.SubElement(case, "error", type="not-started", message=note)
        elif rc < 0:
            killed, status = killed + 1, status if coe else "failure"
            ET.SubElement(case, "error", type="signal", message=f"killed by signal {-rc}")
        elif rc != 0:
            failed += 1
            status = "failure"
            ET.SubElement(case, "failure", message=f"rc={rc} {note}".strip())
        if st.get("id"):
            ctx["steps"][st["id"]] = {"outputs": outputs, "outcome": outcome,
                                      "conclusion": "success" if coe else outcome}
        print(f"##[localci] step {i} rc={rc} {note}".rstrip(), flush=True)
    return failed, killed, blocked, skipped


def main(cfg_path: str, junit_path: str) -> int:
    cfg = json.loads(Path(cfg_path).read_text())
    root = cfg["root"]
    if cfg.get("git_index"):
        index_tree(root, cfg.get("history"), Path(cfg_path).parent / "base")
    if cfg.get("checkout") == "base":   # a job that checks out its BASE ref (`with: ref: <base sha>`) and reads the candidate through git
        subprocess.run(["git", "checkout", "-q", "--detach", "main"], cwd=root, check=True)
    prefix = os.pathsep.join(p for p in (bare_python(cfg.get("path_prefix") or "") if cfg.get("venv") else "", cfg.get("path_prefix")) if p)
    gh = Path("/tmp/localci-gh")
    gh.mkdir(parents=True, exist_ok=True)
    suite = ET.Element("testsuite", name=cfg["context"])
    if cfg.get("expr") is not None:
        failed, killed, blocked, skipped = expr_steps(cfg, root, prefix, gh, suite)
        return finish(suite, cfg, junit_path, failed, killed, blocked, skipped)
    failed = killed = blocked = skipped = 0
    for i, st in enumerate(cfg["steps"]):
        case = ET.SubElement(suite, "testcase", classname="localci.ctx", name=st["name"])
        if "not_applicable" in st:
            skipped += 1
            ET.SubElement(case, "skipped", message=st["not_applicable"])
            continue
        path = os.pathsep.join(p for p in (prefix, os.environ.get("PATH")) if p)   # setup-python's stand-in
        env = {**os.environ, "PATH": path, **cfg.get("env", {}), **st.get("env", {}),
               **{k: str(gh / f"{k.lower()}-{i}") for k in ("GITHUB_OUTPUT", "GITHUB_STEP_SUMMARY")}}   # written, never read back
        Path(env.get("RUNNER_TEMP", "/tmp")).mkdir(parents=True, exist_ok=True)
        argv = st["argv"]
        if "script" in st:
            script = gh / f"step-{i}.sh"
            script.write_text(st["script"])
            argv = [str(script) if a == "{0}" else a for a in argv]
        print(f"##[localci] step {i}: {st['name']}", flush=True)
        t0 = time.monotonic()
        try:
            rc = subprocess.run(argv, cwd=os.path.join(root, st.get("cwd") or "."), env=env).returncode
        except OSError as e:
            rc = None
            blocked += 1
            ET.SubElement(case, "error", type="not-started", message=f"could not start: {type(e).__name__}: {e}")
        else:
            if rc < 0:
                killed += 1
                ET.SubElement(case, "error", type="signal", message=f"killed by signal {-rc}")
            elif rc != 0:
                failed += 1
                ET.SubElement(case, "failure", message=f"rc={rc}")
        case.set("time", f"{time.monotonic() - t0:.3f}")
        print(f"##[localci] step {i} rc={rc}", flush=True)
    return finish(suite, cfg, junit_path, failed, killed, blocked, skipped)


def finish(suite, cfg: dict, junit_path: str, failed: int, killed: int, blocked: int, skipped: int) -> int:
    suite.set("tests", str(len(cfg["steps"])))
    suite.set("failures", str(failed))
    suite.set("errors", str(blocked + killed))
    suite.set("skipped", str(skipped))
    ET.ElementTree(suite).write(junit_path, encoding="utf-8", xml_declaration=True)
    return 1 if failed else 4 if killed else 3 if blocked else 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1], sys.argv[2]))
    except Exception as e:  # noqa: BLE001 — a broken driver is no verdict (rc 2), never a failed step
        print(f"##[localci] driver error: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
        sys.exit(2)
