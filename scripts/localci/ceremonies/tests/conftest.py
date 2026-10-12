from __future__ import annotations

import getpass
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
SHIPPED = ROOT / "scripts/localci/ceremonies/launcher.zsh"
REAL_GIT = Path("/Library/Developer/CommandLineTools/usr/bin/git")
FIXED_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"


@dataclass(frozen=True)
class Patch:
    name: str
    old: str
    new: str
    count: int = 1


def apply_patches(source: str, patches: tuple[Patch, ...]) -> str:
    out = source
    for patch in patches:
        assert out.count(patch.old) == patch.count, (patch.name, out.count(patch.old))
        out = out.replace(patch.old, patch.new)
    return out


class Rig:
    def __init__(self, root: Path, bodies: dict[str, str] | None = None):
        self.root = root
        self.home = root / "home"
        self.base = self.home / "ceremony"
        self.trust = root / "trust"
        self.clt = self.trust / "clt"
        self.git = self.clt / "usr/bin/git"
        self.probe = self.trust / "probe"
        self.link = self.trust / "link"
        self.target = self.clt / "good-parent/target"
        self.zshenv = root / "zshenv"
        self.launcher = self.trust / "launcher.zsh"
        self.remote = root / "remote.git"
        self.pidfile = root / "fetch.pid"
        self.marker = f"localci-watchdog-{os.getpid()}-{root.name}"
        self.user = getpass.getuser()
        self.root.mkdir(parents=True)
        self.base.mkdir(parents=True)
        for path in (self.clt / "usr/bin", self.clt / "usr/libexec/git-core", self.clt / "usr/share/git-core", self.target.parent):
            path.mkdir(parents=True)
        self.probe.touch()
        self.target.touch()
        self.link.symlink_to(self.target)
        self.write_git_wrapper()
        self.m1, self.m2 = self._make_remote(bodies or {})
        source = SHIPPED.read_text()
        self.patches = self._patches(source)
        self.launcher.write_text(apply_patches(source, self.patches))
        self.launcher.chmod(0o555)

    def _patches(self, source: str) -> tuple[Patch, ...]:
        file_url = self.remote.as_uri()
        c3_old = "C3-bootstrap|C3) REMOTE='https://github.com/Bali-Zero/Teman2.git'; transport=(-c protocol.allow=never -c protocol.https.allow=always); transport_expected=$'command line:\\tprotocol.https.allow=always' ;;"
        c12_old = "C12) REMOTE='ssh://mini/Users/nuzantara/localci/replica.git'; transport=(-c protocol.allow=never -c protocol.ssh.allow=always); transport_expected=$'command line:\\tprotocol.ssh.allow=always' ;;"
        remote_new = f"REMOTE='{file_url}'; transport=(-c protocol.allow=never -c protocol.file.allow=always); transport_expected=$'command line:\\tprotocol.file.allow=always' ;;"
        trust_new = f'trust=("{self.trust}" "{self.clt}" "$CLT/usr" "$CLT/usr/bin" "$CLT/usr/libexec" "$CLT/usr/share" "$GIT" "{self.probe}" "{self.link}" "{self.launcher}")'
        return (
            Patch("ceremony-home", "/Users/zero-ops", str(self.home), source.count("/Users/zero-ops")),
            Patch("tool-root", "CLT=/Library/Developer/CommandLineTools", f"CLT={self.clt}", 2),
            Patch("trust-owner", "-user root", f"-user {self.user}", 3),
            Patch("link-parent-stop", "STOP=/;", f"STOP={self.trust};"),
            Patch("trust-roots", 'trust=(/ /Library /Library/Developer "$CLT" "$CLT/usr" "$CLT/usr/bin" "$CLT/usr/libexec" "$CLT/usr/share" /bin /usr /usr/bin /System /usr/local /usr/local/localci /usr/local/localci/bin /usr/local/localci/bin/ceremony-launcher.zsh)', trust_new),
            Patch("closure-roots", '"$GIT" "$CLT/usr/libexec/git-core" "$CLT/usr/share/git-core" /bin/realpath', '"$GIT" "$CLT/usr/libexec/git-core" "$CLT/usr/share/git-core"'),
            Patch("c3-file-remote", c3_old, f"C3-bootstrap|C3) {remote_new}"),
            Patch("c12-file-remote", c12_old, f"C12) {remote_new}"),
            Patch("zshenv-probe", "/etc/zshenv", str(self.zshenv), 2),
            Patch("unprivileged-install", '/usr/bin/sudo /usr/bin/install -o root -g wheel -m 0444 "$d/last-main.new" "$journal"', '/usr/bin/install -m 0444 "$d/last-main.new" "$journal"'),
            Patch("watchdog-ticks", "ticks < 600", "ticks < 4"),
            Patch("watchdog-tick-duration", "zselect -t 100", "zselect -t 5"),
            Patch("watchdog-grace", "zselect -t 500", "zselect -t 5"),
        )

    def _git_run(self, *args: str, cwd: Path | None = None) -> str:
        return subprocess.run([str(REAL_GIT), *args], cwd=cwd, check=True, text=True, capture_output=True).stdout.strip()

    def _make_remote(self, bodies: dict[str, str]) -> tuple[str, str]:
        src = self.root / "src"
        self._git_run("init", "-b", "main", str(src))
        self._git_run("config", "user.name", "Fixture", cwd=src)
        self._git_run("config", "user.email", "fixture@example.invalid", cwd=src)
        ceremonies = src / "docs/ceremonies"
        ceremonies.mkdir(parents=True)
        for name in ("C3-bootstrap", "C3", "C12"):
            (ceremonies / f"{name}.zsh").write_text(bodies.get(name, "exit 0\n"))
        (src / "generation").write_text("one\n")
        self._git_run("add", ".", cwd=src)
        self._git_run("commit", "-m", "fixture one", cwd=src)
        m1 = self._git_run("rev-parse", "HEAD", cwd=src)
        (src / "generation").write_text("two\n")
        self._git_run("add", "generation", cwd=src)
        self._git_run("commit", "-m", "fixture two", cwd=src)
        m2 = self._git_run("rev-parse", "HEAD", cwd=src)
        self._git_run("clone", "--bare", str(src), str(self.remote))
        return m1, m2

    def write_git_wrapper(self, mode: str = "normal", plant: str | None = None) -> None:
        fetch = ""
        if mode == "sleep":
            fetch = f'''if [[ " $* " == *" fetch --no-tags "* ]]; then\n  print -r -- $$ >"{self.pidfile}"\n  exec -a "{self.marker}" /bin/sleep 30\nfi\n'''
        elif mode == "fail":
            fetch = 'if [[ " $* " == *" fetch --no-tags "* ]]; then exit 23; fi\n'
        planted = {
            None: "",
            "credential.helper": "print -r -- $'[credential]\\n\\thelper = !false' >>\"$repo/config\"",
            "include.path": "print -r -- $'[include]\\n\\tpath = /dev/null' >>\"$repo/config\"",
            "duplicate hooksPath": "print -r -- $'[core]\\n\\thooksPath = /dev/null' >>\"$repo/config\"",
            "core.bare=false": f'"{REAL_GIT}" -C "$repo" config core.bare false',
        }[plant]
        init = ""
        if planted:
            init = f'''if [[ " $* " == *" init --bare "* ]]; then\n  "{REAL_GIT}" "$@" || exit $?\n  repo=${{@[-1]}}\n  {planted}\n  exit 0\nfi\n'''
        self.git.write_text(f'''#!/bin/zsh -f\nunsetopt BG_NICE\n{fetch}{init}exec "{REAL_GIT}" "$@"\n''')
        self.git.chmod(0o755)

    def run(self, m: str, name: str, *, stdin: str = "", extra: tuple[str, ...] = ()) -> subprocess.CompletedProcess[str]:
        return self.run_args((m, name, *extra), stdin=stdin)

    def run_args(self, args: tuple[str, ...], *, stdin: str = "") -> subprocess.CompletedProcess[str]:
        cmd = ["/usr/bin/env", "-i", f"HOME={self.home}", f"PATH={FIXED_PATH}", "LC_ALL=C", "HOSTILE_BODY_ENV=present", "/bin/zsh", "-f", str(self.launcher), *args]
        return subprocess.run(cmd, input=stdin, text=True, capture_output=True, timeout=15)

    def runs(self) -> list[Path]:
        return sorted(p for p in self.base.iterdir() if p.name != "last-main")

    def set_journal(self, value: str) -> Path:
        journal = self.base / "last-main"
        journal.write_text(value + ("" if value.endswith("\n") else "\n"))
        journal.chmod(0o444)
        return journal

    def fetch_alive(self) -> tuple[bool, int | None]:
        pid = int(self.pidfile.read_text()) if self.pidfile.exists() else None
        probe = subprocess.run(["/usr/bin/pgrep", "-f", self.marker], text=True, capture_output=True)
        if probe.returncode == 0:
            return True, pid
        if probe.returncode == 1:
            return False, pid
        if pid is None:
            return False, None
        try:
            os.kill(pid, 0)
            return True, pid
        except ProcessLookupError:
            return False, pid

    def kill_fetch(self, pid: int | None) -> None:
        if pid is None:
            return
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        for _ in range(50):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.01)


@pytest.fixture
def rig_factory(tmp_path: Path):
    made = 0

    def make(bodies: dict[str, str] | None = None) -> Rig:
        nonlocal made
        made += 1
        return Rig(tmp_path / f"rig-{made}", bodies)

    return make


def pytest_configure(config):
    config.addinivalue_line("markers", "network: requires LOCALCI_NET_TESTS=1")


def pytest_collection_modifyitems(config, items):
    if os.environ.get("LOCALCI_NET_TESTS") == "1":
        return
    skip = pytest.mark.skip(reason="set LOCALCI_NET_TESTS=1 for network cases")
    for item in items:
        if "network" in item.keywords:
            item.add_marker(skip)
