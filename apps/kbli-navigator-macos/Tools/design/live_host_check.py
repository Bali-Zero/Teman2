#!/usr/bin/env python3
"""live_host_check.py - every LIVE call site of a View that has an immersive presentation mounts it under ImmersiveHost.

The user's default is the immersive layout (IMM, 2026-10-11): `ImmersiveKey` defaults to false so the flat path stays the
baseline of the content proof, and the app reaches the immersive one only through `.immersiveHost()` / `ImmersiveHost`.
A live site that loses its host would ship the flat layout silently, so this check names it. A View counts as having an
immersive presentation when the file that defines it reads `@Environment(\\.immersive)`.

  live_host_check.py            check Sources/ (exit 1 on a bare live site or a vanished required site)
  live_host_check.py --selftest guilt + innocence: a hosted site passes, the same site without its host fails
"""
import re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2] / "Sources"
# Files that need no host of their own, each with its reason.
EXEMPT_FILES = {"Snapshot.swift": "the snapshot harness picks flat or --imm itself",
                "Immersion.swift": "the host itself", "ImmersionStage.swift": "KBLIImmersiveCard is the host wrapper"}
EXEMPT_SITES = {("RegistryVerdictSheet.swift", "KBLIRegistryView"): "embedded child: its parent sheet is the hosted site",
                ("KBLIRegistryView.swift", "KBLIRegistryView"): "KBLIImmersiveLedger is the host wrapper"}
# A site the app must keep (so the check cannot pass vacuously), required once its View is immersive-aware: (file, view).
REQUIRED = [("SearchListView.swift", "RegistryVerdictSheet"), ("RootView.swift", "ChatView")]
HOSTED = re.compile(r"\.immersiveHost\(\)|\bImmersiveHost\s*\{")
FORCED_FLAT = re.compile(r"\.environment\(\\\.immersive,\s*false\)|\.transformEnvironment\(\\\.immersive\)")   # any write of the switch
COMMENT = re.compile(r"//[^\n]*")
IMMERSIVE_READ = re.compile(r"@Environment\(\\\.immersive\)")
# The mount roots: Views a UI path constructs. Their children read the environment and need no host of their own.
ROOTS = {"RegistryVerdictSheet", "ChatView", "KBLIDetailRichView", "KBLIRegistryView"}
DEFINITION = re.compile(r"^\s*(?:final\s+)?struct\s+(\w+)\s*:\s*View\b", re.M)

def aware_views(files):
    """The Views whose defining file reads `\\.immersive`: (view -> call-site pattern)."""
    out = {}
    for _, text in files:
        if IMMERSIVE_READ.search(text):
            for name in (n for n in DEFINITION.findall(text) if n in ROOTS):
                out[name] = r"\b%s\(" % name
    return out

def hosted(window):
    """Hosted, and not forced flat: `.environment(\\.immersive, false)` BEFORE `.immersiveHost()` (inside it) or after `ImmersiveHost {`
    overrides the host's switch; after `.immersiveHost()` (outside it) it overrides nothing. The pixel witness (png_census C25) is
    the arbiter for what a text cannot say: `#if false`, a sibling host, `transformEnvironment`."""
    h, f = HOSTED.search(window), FORCED_FLAT.search(window)
    return bool(h) and not (f and (f.start() < h.start()) == h.group().startswith("."))

def sites(text, view, pat):
    for m in re.finditer(pat, text):
        line_start = text.rfind("\n", 0, m.start()) + 1
        if re.match(r"\s*(struct|class|enum|extension|//)", text[line_start:m.start() + 20]): continue
        if re.search(r"(struct|class)\s+%s\b" % view, text[line_start:m.end() + 10]): continue
        window = text[max(0, m.start() - 60):m.start()] + text[m.start():m.start() + 700].split("\n\n")[0]
        yield text.count("\n", 0, m.start()) + 1, hosted(window)

def check(files):
    views, bad, seen = aware_views(files), [], set()
    for path, text in files:
        name = pathlib.Path(path).name
        if name in EXEMPT_FILES: continue
        for view, pat in views.items():
            for line, hosted in sites(text, view, pat):
                seen.add((name, view))
                if not hosted and (name, view) not in EXEMPT_SITES: bad.append("%s:%d %s is mounted without ImmersiveHost" % (name, line, view))
    bad += ["%s no longer mounts %s: the required live site is gone" % r for r in REQUIRED if r[1] in views and r not in seen]
    return bad

def main():
    if "--selftest" in sys.argv:
        aware = ("RegistryVerdictSheet.swift", "struct RegistryVerdictSheet: View {\n  @Environment(\\.immersive) var i\n}\n")
        chat = ("ChatView.swift", "struct ChatView: View {\n  @Environment(\\.immersive) var i\n}\n")
        good = [aware, chat, ("SearchListView.swift", "x\n    RegistryVerdictSheet(kbli: k) {\n    }\n    .immersiveHost()\n"),
                ("RootView.swift", "case .chat:\n    ChatView().immersiveHost()\n")]
        assert check(good) == [], check(good)
        bare = [aware, chat, ("SearchListView.swift", "x\n    RegistryVerdictSheet(kbli: k) {\n    }\n    .frame(x)\n"),
                ("RootView.swift", "case .chat:\n    ChatView().immersiveHost()\n")]
        assert len(check(bare)) == 1, check(bare)
        assert len(check([aware, chat] + good[2:3])) == 1, "a vanished required site must fail"
        assert len(check([aware, chat, ("SearchListView.swift", COMMENT.sub("", "x\n    RegistryVerdictSheet(kbli: k) {\n    }\n    // .immersiveHost()\n")),
                          ("RootView.swift", "case .chat:\n    ChatView().immersiveHost()\n")])) == 1, "a commented-out host must fail"
        forced = [aware, chat, ("SearchListView.swift", "x\n    RegistryVerdictSheet(kbli: k) {\n    }\n    .environment(\\.immersive, false).immersiveHost()\n"),
                  ("RootView.swift", "case .chat:\n    ChatView().immersiveHost()\n")]
        assert len(check(forced)) == 1, "a host with the immersive switch forced off must fail"
        outside = [aware, chat, ("SearchListView.swift", "x\n    RegistryVerdictSheet(kbli: k) {\n    }\n    .immersiveHost().environment(\\.immersive, false)\n"),
                   ("RootView.swift", "case .chat:\n    ChatView().immersiveHost()\n")]
        assert check(outside) == [], "an override OUTSIDE the host overrides nothing: the sheet is immersive"
        transform = [aware, chat, ("SearchListView.swift", "x\n    RegistryVerdictSheet(kbli: k) {\n    }\n    .transformEnvironment(\\.immersive) { $0 = false }\n    .immersiveHost()\n"),
                     ("RootView.swift", "case .chat:\n    ChatView().immersiveHost()\n")]
        assert len(check(transform)) == 1, "a transformEnvironment write of the switch inside the host must fail"
        block = [aware, chat, ("SearchListView.swift", "x\n    ImmersiveHost { RegistryVerdictSheet(kbli: k) {\n    }.environment(\\.immersive, false) }\n"),
                 ("RootView.swift", "case .chat:\n    ChatView().immersiveHost()\n")]
        assert len(check(block)) == 1, "an override INSIDE an ImmersiveHost block must fail"
        flat = [("ChatView.swift", "struct ChatView: View {\n}\n"), ("RootView.swift", "case .chat:\n    ChatView()\n")]
        assert check(flat) == [], "a View that is not immersive-aware needs no host"
        print("live_host_check selftest ok (guilt + innocence)"); return 0
    files = [(str(p), COMMENT.sub("", p.read_text())) for p in sorted(ROOT.rglob("*.swift"))]   # a commented-out host is no host
    bad = check(files)
    for b in bad: print("LIVE-HOST", b)
    print("live_host_check: %d finding(s) in %d files, immersive-aware: %s" % (len(bad), len(files), ", ".join(sorted(aware_views(files))) or "none"))
    return 1 if bad else 0

sys.exit(main())
