#!/usr/bin/env python3
"""Applies the ten gate-7691 product mutants (T1-T5 TaxCalendarBody, Y1-Y5
MyTaxCalendar) one at a time to the REAL files, runs the per-page guard, and
restores the file with cp. Run from the worktree root. Every row must be RED."""
import pathlib, re, shutil, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parents[3]
APP = ROOT / "apps/mouth"
FUN = "src/components/funnel/"
FILES = {"T": FUN + "TaxCalendarBody.tsx", "Y": FUN + "MyTaxCalendar.tsx"}
GUARDS = {"T": FUN + "TaxCalendarBody.r19-guard.test.tsx", "Y": FUN + "MyTaxCalendar.r19-guard.test.tsx"}
MUTANTS = [
    ("T", "T1 class literal in a ternary branch", 45, '"pill pill-active"', '"pill pill-active text-[#0A2540]"'),
    ("T", "T2 border rgb() in the pill style", 49, '"1px solid var(--r19-line)"', '"1px solid rgb(0 0 0 / .1)"'),
    ("T", "T3 color oklch() on the strong", 140, '"var(--r19-ink)"', '"oklch(0.3 0.05 250)"'),
    ("T", "T4 outlineColor Highlight on the section", 31, 'fontFamily: "var(--font-sans)" }', 'fontFamily: "var(--font-sans)", outlineColor: "Highlight" }'),
    ("T", "T5 unrendered ternary literal", 140, '"var(--r19-ink)"', 'deadlines.length > 99 ? "#0A2540" : "var(--r19-ink)"'),
    ("Y", "Y1 border hex in the label style", 112, '"1px solid var(--r19-line)"', '"1px solid #0A2540"'),
    ("Y", "Y2 boxShadow rgba in const cardStyle", 46, 'borderRadius: "8px",', 'borderRadius: "8px", boxShadow: "0 1px 2px rgba(0,0,0,.2)",'),
    ("Y", "Y3 aside background whitesmoke", 544, '"var(--r19-wash)"', '"whitesmoke"'),
    ("Y", "Y4 className palette on the p", 266, "<p style=", '<p className="text-slate-600" style='),
    ("Y", "Y5 unrendered ternary literal", 544, '"var(--r19-wash)"', 'count > 999 ? "ivory" : "var(--r19-wash)"'),
]

def main() -> int:
    backups = {}
    tmp = pathlib.Path(tempfile.mkdtemp())
    for key, rel in FILES.items():
        backups[key] = tmp / f"{key}.bak"
        shutil.copy(APP / rel, backups[key])
    bad = 0
    try:
        for key, name, line, old, new in MUTANTS:
            target = APP / FILES[key]
            lines = backups[key].read_text().split("\n")
            assert old in lines[line - 1], (name, lines[line - 1])
            lines[line - 1] = lines[line - 1].replace(old, new, 1)
            target.write_text("\n".join(lines))
            run = subprocess.run(["npx", "vitest", "run", GUARDS[key]], cwd=APP, capture_output=True, text=True)
            tests = re.search(r"Tests\s+(.*)", run.stdout + run.stderr)
            verdict = "RED" if run.returncode else "GREEN"
            bad += verdict != "RED"
            print(f"{name} | {verdict} | {tests.group(1).strip() if tests else '?'}")
            shutil.copy(backups[key], target)
    finally:
        for key, rel in FILES.items():
            shutil.copy(backups[key], APP / rel)
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
