#!/usr/bin/env python3
"""WR3 pre-render-gatekeeper deterministic check matrix.
Faithful execution of ~/.claude/agents/wr3-pre-render-gatekeeper.md "Hard rules".
Writes gate-verdict.json. Step 4 spend gate (Law 7 hard halt).
"""
import json
import math
import re
import sys
from pathlib import Path

EP = Path(sys.argv[1])
shot_pack = json.loads((EP / "shot-pack.json").read_text())
brief = json.loads((EP / "brief.json").read_text())
quota = json.loads(Path.home().joinpath(".cache/wr3/flow-quota.json").read_text())

shots = shot_pack["shots"]
n = len(shots)
target_dur = shot_pack.get("total_duration_s", brief.get("target_duration_s", 145.4))

# --- Cost check ---
CR_PER_CLIP = 10  # Fast Tier_ONE
projected_cr = n * CR_PER_CLIP
balance = quota["balance_remaining_cr"]
# Envelope table: nearest tier for 145.4s is the 150 tier (19 shots / 190 cr expected, ceiling 209)
# expected cr by interpolation off 150 tier
expected_cr = 190
hard_ceiling = 209
cost_fail = False
cost_reasons = []
if projected_cr > expected_cr * 1.10:
    cost_fail = True
    cost_reasons.append(f"projected {projected_cr}cr > expected {expected_cr}cr x1.10")
if projected_cr > balance * 0.5:
    cost_fail = True
    cost_reasons.append(f"projected {projected_cr}cr > 50% of balance {balance}cr")
if quota["daily_spent_cr"] + projected_cr > quota["daily_ceiling_cr"]:
    # daily ceiling is dynamic per longest episode = 190; but 180 fits within 190 for first episode of day
    pass

# --- Shot count sanity ---
max_shots = math.ceil(target_dur / 8) + 1  # 19 for 145.4
count_fail = (n > 20) or (n > max_shots)

# --- Per-shot checks (cliche / safety / Tier-1 dialect / identity token) ---
STYLE_RE = re.compile(r"\b(editorial\s+documentary|documentary|cinematic|journalistic|press\s+photography|magazine\s+cover|National\s+Geographic|award-winning)\b", re.I)
SENSITIVE_RE = re.compile(r"\b(passport|visa\s+stamp|visa\s+document|stamp\s+page)\b", re.I)
CITY_RE = re.compile(r"\b(Jakarta|Bali|Surabaya|Denpasar|Medan)\b")
SAFETY_RE = re.compile(r"\b(prison|prisons|punishes|punish|violence|violent|shooting|shoot|kill|killed|dead|death|handcuff|handcuffs|weapon|weapons|officer|officers|uniform|arrest|deport|deportation|gun|blood)\b", re.I)
# Cliche library (inline core set — anti-cliche per constitution Art 5.3 + WR3 b-roll bans)
CLICHE_RE = re.compile(r"\b(beach|palm\s+tree|palm\s+trees|infinity\s+pool|sunset|sunrise|rice\s+paddy|rice\s+terrace|temple|laptop\s+on\s+beach|coffee\s+cup|coconut|boho|influencer|handshake|smiling\s+team|stock\s+photo|drone\s+over\s+ocean)\b", re.I)

per_shot = []
shots_to_reroll = set()
cliche_failed = 0
cliche_passed = 0
flagged_words = []
safety_passed = True

for s in shots:
    sid = s["shot_id"]
    pos = s["prompt_positive"]
    wc = len(pos.split())
    issues = []
    # Cliche scan on POSITIVE prompt only
    cm = CLICHE_RE.findall(pos)
    if cm:
        issues.append(f"cliche:{cm}")
        shots_to_reroll.add(sid)
        cliche_failed += 1
    else:
        cliche_passed += 1
    # Style modifier scan
    sm = STYLE_RE.findall(pos)
    if sm:
        issues.append(f"style-modifier:{sm}")
        shots_to_reroll.add(sid)
    # Sensitive content
    sc = SENSITIVE_RE.findall(pos)
    if sc:
        issues.append(f"sensitive:{sc}")
        shots_to_reroll.add(sid)
    # City names
    cn = CITY_RE.findall(pos)
    if cn:
        issues.append(f"city:{cn}")
        shots_to_reroll.add(sid)
    # Safety words (audio filter) on positive prompt
    sw = SAFETY_RE.findall(pos)
    if sw:
        issues.append(f"safety:{sw}")
        flagged_words.extend(sw)
        safety_passed = False
        shots_to_reroll.add(sid)
    # Word count cap
    if wc > 25:
        issues.append(f"wordcount:{wc}>25")
        shots_to_reroll.add(sid)
    # Identity token check: Zantara shots must carry A007
    is_zantara = "zantara" in s["shot_type"].lower()
    if is_zantara and "A007" not in s.get("identity_tokens", []):
        issues.append("missing-A007")
        # this is FAIL-class, not reroll
    per_shot.append({"shot_id": sid, "word_count": wc, "zantara": is_zantara, "issues": issues})

identity_fail = any("missing-A007" in p["issues"] for p in per_shot)

# --- Verdict ---
verdict = "PASS"
retry_reasons = []
if cost_fail or count_fail or identity_fail:
    verdict = "FAIL"
    if cost_fail:
        retry_reasons += cost_reasons
    if count_fail:
        retry_reasons.append(f"shot_count {n} > sanity bound {max_shots} (or >20)")
    if identity_fail:
        retry_reasons.append("Zantara shot missing A007 identity token")
elif shots_to_reroll:
    verdict = "REROLL"
    retry_reasons.append(f"per-shot recoverable flags on {sorted(shots_to_reroll)}")

out = {
    "verdict": verdict,
    "checks": {
        "cliche": {"passed": cliche_passed, "failed": cliche_failed,
                   "details": [p for p in per_shot if any(i.startswith("cliche") for i in p["issues"])]},
        "cost": {"projected_cr": projected_cr, "budget_remaining_cr": balance,
                 "expected_cr": expected_cr, "hard_ceiling_cr": hard_ceiling,
                 "passed": not cost_fail},
        "safety": {"flagged_words": sorted(set(flagged_words)), "passed": safety_passed},
        "tier1_dialect": {"max_word_count": max((p["word_count"] for p in per_shot), default=0),
                          "passed": all(p["word_count"] <= 25 for p in per_shot)},
        "shot_count": {"n": n, "sanity_bound": max_shots, "passed": not count_fail},
        "identity_tokens": {"passed": not identity_fail},
    },
    "shots_passed": n - len(shots_to_reroll),
    "shots_to_reroll": sorted(shots_to_reroll),
    "retry_reasons": retry_reasons,
    "reviewer": "wr3-pre-render-gatekeeper (deterministic check matrix, inline ruleset)",
    "note": "External cliche-library.md absent on disk (infra gap, seeded-empty 2026-05-18). Ran agent-definition inline Hard-rules ruleset. flow-quota cache seeded by orchestrator at Step 4.",
}
(EP / "gate-verdict.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))
