#!/usr/bin/env bash
# Merge-OS v2 round-2 Cure #1 (adapted 2026-08-18) — manual emergency
# override for the change-map ring-gating in tests.yml's `changes` job.
#
# WHY THIS IS "ADAPTED" AND NOT A LITERAL PORT of the round-2 finding
# (PENDING-ARMS.md, "Wave 2 of Merge-OS v2 may be armed ONLY with the four
# round-2 cures incorporated", opened 2026-08-10):
#
# The 2026-08-10 refutation demanded an explicit OPT-IN kill-switch
# expression (`vars.MERGEOS_RING_GATING != 'on'`) whose ambiguous states
# (unset, typo, 'off') all resolve to the EXPENSIVE/SAFE direction (full
# suite) — never to the cheap/risky direction (silent skip) — because at
# the time ring-gating did not exist yet and was going to be introduced
# gated OFF by default.
#
# By the time this cure was revisited (2026-08-18), ring-gating had
# already shipped default-ON via #4181 (2026-08-14, "promote change-map
# from shadow to enforcing"), with its OWN fail-open defaults baked into
# every internal layer: classifier-extraction failure, guilt/innocence
# corpus failure, enumeration failure, or an unclassified path all force
# `run_all=true` (see tests.yml's `changes` job `outputs:` block, every
# `run_*` key defaults `|| 'true'`). Re-applying the v2 variable literally
# — `vars.MERGEOS_RING_GATING != 'on'` gating the *entire* classifier off
# by default — would have SILENTLY REGRESSED #4181's shipped benefit back
# to always-run-everything the instant this landed, because nothing sets
# `MERGEOS_RING_GATING=on` anywhere in this repo's config today. That is
# an own-goal, not a cure.
#
# What was still genuinely missing (verified 2026-08-18 against
# origin/main: no `vars.` reference of any kind exists in tests.yml) is a
# DISCRETIONARY MANUAL LEVER: something an operator can flip during an
# incident to force the full suite regardless of what the classifier
# itself computes — independent of whether the classifier is technically
# "working" (its own fail-open defaults only catch classifier ERRORS, not
# an operator's judgment call that they don't trust a specific
# classification today). That is what this script adds: additive to the
# existing fail-open defaults, never subtractive from them.
#
# Truth table (same invariant as round-2 — an ambiguous value must never
# resolve to the risky direction — expressed with the opposite-polarity
# variable this shipped reality actually needs):
#
#   MERGEOS_RING_GATING_DISABLED | override state | effect
#   ------------------------------|----------------|---------------------------
#   'true' (exact, case-sensitive)| ACTIVE          | force full suite (classifier bypassed entirely)
#   'false'                       | inactive        | classifier decides (today's shipped default, unchanged)
#   unset / '' / any other value  | inactive        | classifier decides (today's shipped default, unchanged)
#
# Every value except the exact literal string "true" leaves today's
# behavior completely untouched. By construction, the only reachable
# effect of misconfiguring this variable is running MORE tests, never
# fewer — it is structurally impossible to use this override to widen a
# skip. That property is what makes it safe to wire with a plain `==`
# check rather than needing the `!=` inversion trick round-2 required for
# the original (opt-in-to-enable) polarity.
set -euo pipefail

if [[ "${MERGEOS_RING_GATING_DISABLED:-}" == "true" ]]; then
  echo "active=true"
else
  echo "active=false"
fi
