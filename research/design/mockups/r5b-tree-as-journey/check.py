#!/usr/bin/env python3
"""R5b checker Rev 2 (post-panel): (1) EXECUTES the journey engine's
pure-function selftest under node; (2) static falsifiable checks. Panel fixes
folded in: the D4 check is now a parser over the dark block that REJECTS
#ff2d4c anywhere except text-color properties and the one declared progress
exception (codex 10); the reduction disclosure must live in VISIBLE markup,
not comments (codex 7); the guarantee scan covers absolute-change language
(codex 11). Every check can go red."""
import json, pathlib, re, subprocess, sys

R5B = pathlib.Path(__file__).parent
html = (R5B / "journey.html").read_text()
body_only = html.split("<script")[0]

# ---- 1. engine selftest under node ----
m = re.search(r'<script id="engine">\n(.*?)\n</script>', html, re.S)
assert m, "engine script block not found"
proc = subprocess.run(["node", "-e", m.group(1)], capture_output=True, text=True, timeout=30)
try:
    st = json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else {}
except Exception:
    st = {}
checks = {"engine_selftest": {
    "node_exit_0": proc.returncode == 0,
    "tests_run": st.get("total", 0),
    "tests_run_gte_14": st.get("total", 0) >= 14,
    "failures": st.get("fails", ["<no output parsed>"]),
    "zero_failures": st.get("fails") == [],
}}

# ---- 2. D4 structural parser over the dark CSS block ----
dark_rules = re.findall(r'(\.jr\[data-oracle-theme="dark"\][^{]*)\{([^}]*)\}', html)
d4_violations = []
for selector, block in dark_rules:
    for decl in block.split(";"):
        if "#ff2d4c" not in decl:
            continue
        prop = decl.split(":")[0].strip()
        if prop in ("--link", "color"):          # text-color placements: allowed by D4
            continue
        if prop == "background" and ".progress-fill" in selector:  # the ONE declared graphical exception
            continue
        d4_violations.append(f"{selector.strip()} {{ {decl.strip()} }}")
dark_root = next((b for _s, b in dark_rules if "--ground" in b), "").replace(" ", "")
checks["d4_structural"] = {
    "violations": d4_violations,
    "no_ff2d4c_fill_outside_declared": d4_violations == [],
    "action_fill_stays_D01033_in_dark": "--action-fill:#D01033" in dark_root,
    "link_dark_is_ff5f74_measured": "--link:#ff5f74" in dark_root,
}

# ---- 3. static checks ----
s = {}
s["identity_header"] = ('class="wordmark"' in html and 'lang-toggle' in html and '<a class="wa-entry"' in html)
s["identifier_line"] = "{PT_LEGAL_NAME}" in html and "{NPWP}" in html
s["dated_line"] = "27 Aug 2026" in html
s["aria_live_region"] = 'aria-live="polite"' in html
s["single_atomic_announcement"] = "parts.join" in html
s["focus_management"] = "focusTitle" in html and "tabIndex=-1" in html
s["keyboard_arrows_on_radio"] = "ArrowDown" in html and '"role","radiogroup"' in html
s["roving_tabindex"] = "b.tabIndex = (sel===val" in html
s["color_scheme_declared"] = "color-scheme:light" in html and "color-scheme:dark" in html
s["nsbtn_styled"] = ".notsure button" in body_only
s["counter_recompute_announce"] = "counterAnnouncement" in html and "counterAnnounce" in html
s["counter_confirms_exactness"] = "Your path is confirmed" in html
s["counter_no_plus_arithmetic"] = not re.search(r'\(\+\$\{|\+\$\{d\}', html)
s["counter_honest_prefork"] = "or more" in html
s["subprogress_dv11"] = "Sponsor ${sp.i} of ${sp.n}" in html
s["sponsor_ids_exact_array"] = ('SPONSOR_IDS = ["family_relation","marital_status","family_sponsor_nationalities",'
                               '"family_sponsor_status_code","family_marriage_registered","family_sponsor_confirmed"]') in html
s["branch_note_m3"] = "Immigration history — 2 questions" in html and "sponsor — 6 questions" in html
s["branchnote_tokenized"] = '"@Your@ sponsor — 6 questions"' in html
s["delegate_flow"] = "who_answers" in html and "delegate-banner" in html and "the traveller" in html
s["delegate_authorization_step"] = "delegate_confirm" in html and "delegateOnly" in html
s["real_permit_options"] = ('"E33G","E33G — Second Home Visa — Remote Worker"' in html
                            and '"E23","E23 — Working Visa"' in html and "C312" not in html)
s["no_dev_telemetry_in_ui"] = "fact-mapper.ts" not in body_only and "PR #5077" not in html
s["dv5_search"] = "Start typing a country" in html and "Other / not listed" in html
s["notsure_on_overstay"] = re.search(r'"overstay_days"[^\n]*notSure:true', html) is not None
s["no_guarantee_language"] = not re.search(
    # promissory language only — "guarantee letter" is a real document's NAME
    # (Surat Jaminan), not a promise: word-boundary + lookahead excludes it
    r'\bnever blocks\b|\bguarantee[d]?\b(?!\s+letter)|\bdijamin\b|changes nothing|nothing will change', html, re.I)
s["engine_shadow_honest"] = "runs in shadow" in html and "the engine would decide" in html
s["no_checkout_pay_claim"] = "checkout and pay" not in html
s["case_code_marked_study"] = "study example code" in html
s["step_id_in_wa_link"] = "&step=" in html
s["prune_on_fork"] = "pruneOrphans" in html and "q.fork" in html
s["resume_versioned_by_qid"] = "SAVE_VERSION" in html and "s.qid" in html and "removeItem(SAVE_KEY)" in html
s["review_textcontent_only"] = "rv.textContent=String(facts" in html and "row.innerHTML" not in html
s["no_real_prices"] = not re.search(r'IDR\s*[\d.]{6,}', html)
s["reduction_visible_markup"] = "17 of the 53" in body_only and "5 of 29" in body_only
s["order_caveat_visible"] = "orders some questions differently" in body_only
s["audit_trail_in_source"] = all(x in html for x in ("tree.ts", "flow.ts", "ThemeToggle.tsx:45"))
s["reduced_motion"] = "prefers-reduced-motion" in html
s["focus_single_ring"] = "0 0 0 4px var(--link)" in html and "0 0 0 5px var(--ground)" not in html
s["subprogress_boundary"] = "border:1px solid var(--line-input)" in html.split(".jr .subprogress")[1][:220]
s["header_mobile_mediaquery"] = "@media (max-width:380px)" in html
s["id_toggle_honest"] = 'aria-disabled="true"' in html
checks["static"] = s

(R5B / "checks.json").write_text(json.dumps(checks, indent=1))
fails = [f"engine.{k}" for k, v in checks["engine_selftest"].items() if v is False] + \
        [f"d4.{k}" for k, v in checks["d4_structural"].items() if v is False] + \
        [f"static.{k}" for k, v in s.items() if v is False]
print("SELFTEST:", proc.stdout.strip() or proc.stderr.strip()[:400])
print("D4:", json.dumps(checks["d4_structural"]))
print("FAILS:", fails if fails else "none")
sys.exit(1 if fails else 0)
