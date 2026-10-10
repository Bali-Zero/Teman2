"""Applies one named mutation to the scratch tree, or reverts all of them: A, B, I10, or revert."""
import sys
from pathlib import Path

M = Path("/Users/balizero/nuzantara/.worktrees/mouth-kbli-r19-w0d2p-mutants/apps/mouth/src")
NAV = M / "app/v2/_components/MobileNav.tsx"
LAYOUT = M / "app/kbli/layout.tsx"
EDITS = {
    "A": [(NAV, '            background: "var(--nav-bg)",\n',
           '            background: isR19 ? "var(--nav-bg)" : "#F7F4EE",\n')],
    "B": [(NAV, '"color-mix(in srgb, var(--accent-funnel) 6%, transparent)"',
           '"color-mix(in srgb, var(--accent-funnel) 40%, transparent)"')],
    "I10": [(NAV, "  funnel: Funnel;\n}", "  funnel: Funnel;\n  paper?: boolean;\n}"),
            (NAV, "export function MobileNav({ items, funnel }: MobileNavProps)",
             "export function MobileNav({ items, funnel, paper }: MobileNavProps)"),
            (NAV, '            background: "var(--nav-bg)",\n',
             '            background: paper ? "#F7F4EE" : "var(--nav-bg)",\n'),
            (LAYOUT, '<MobileNav items={navItems} funnel="kbli" />', '<MobileNav items={navItems} funnel="kbli" paper />')],
}
which = sys.argv[1]
if which == "revert":
    for name in ("A", "B", "I10"):
        for path, a, b in reversed(EDITS[name]):
            t = path.read_text()
            if b in t:
                path.write_text(t.replace(b, a))
else:
    for path, a, b in EDITS[which]:
        t = path.read_text()
        assert t.count(a) == 1, (which, a)
        path.write_text(t.replace(a, b))
print(which, "done")
