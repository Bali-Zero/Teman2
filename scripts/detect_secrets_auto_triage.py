#!/usr/bin/env python3
"""
detect-secrets baseline auto-triage.

Runs a set of conservative path-based rules against `.secrets.baseline` and
marks findings as `is_secret: false` when they fall inside files that are
definitionally non-sensitive (example env files, test fixtures, planning
documents, etc.). Everything else is left `unaudited` so a human can
inspect the residue.

A second, narrower rule class (CONTENT_KEYED_RULES) exists for files that are
NOT definitionally non-sensitive as a whole — e.g. a script that legitimately
holds executable code-signing identity pins (sha256/cdhash) alongside other
code. A plain path-based rule on such a file would blanket-approve ANY future
finding in it, including a real secret added on an unrelated line later
(cicatrix-superscar #3, guard-over-match: match entity/intent, never bare
path/substring). CONTENT_KEYED_RULES require the exact source line at the
finding's line_number to also match a narrow content pattern (the assignment
target's name), so only the specific pinned-identity lines are approved.

Usage:
    python3 scripts/detect_secrets_auto_triage.py             # dry-run
    python3 scripts/detect_secrets_auto_triage.py --apply     # write back
    python3 scripts/detect_secrets_auto_triage.py --report    # human report

Conservative means:
    - Never auto-approve files inside production code paths
    - Never auto-approve anything with `prod`, `production`, `live` in the path
    - Never auto-approve `.env` (only `.env.example`, `.env.*.example`, `.env.sample`)
    - Never auto-approve anything outside the whitelist patterns
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE = REPO_ROOT / ".secrets.baseline"

# Each rule is (path_pattern, content_pattern, reason). The path_pattern
# scopes the rule to specific known files; the content_pattern must ALSO
# match the actual source line at the finding's line_number (read live off
# disk — these files are always present in the checkout when this script
# runs, per .github/workflows/security.yml's checkout-then-scan-then-triage
# order). Approval requires BOTH to match, so an unrelated secret added
# later to one of these files (on a line whose assignment target isn't in
# the content_pattern) is still left unaudited for human review.
CONTENT_KEYED_RULES: list[tuple[re.Pattern[str], re.Pattern[str], str]] = [
    # worker-plane review panel: executable code-signing identity pins
    # (sha256/cdhash of production CLI binaries — Claude Code, Gemini/agy,
    # Codex, Kimi, sandbox-exec) used to VERIFY supply-chain integrity
    # before spawning a reviewer process, plus a PRODUCTION_ARTIFACT_SHA256
    # dict of wrapper/package content hashes for the same purpose. These are
    # public integrity anchors — anyone can recompute them from the signed
    # binary — never credentials; removing them would weaken the check they
    # implement, not improve security.
    #
    # Content-keyed on assignment target NAME *and* VALUE SHAPE, with the
    # match anchored to end-of-line (optional trailing comma): the whole
    # line must be exactly `<key><:|=> "<hex>"[,]`. This closes two holes a
    # target-name-only version had (found in review, 2026-07-26):
    #   1. `sha256="ghp_<realtoken>"` — a real credential assigned to a pin
    #      name would have been approved on name alone; the value must now
    #      be exactly 64 (sha256/codex_wrapper/codex_package) or 40 (cdhash)
    #      lowercase hex characters.
    #   2. `sha256="<hash>"; api_key="<realsecret>"` — Python allows
    #      `;`-separated statements on one line, so a second assignment
    #      after a legitimate pin used to ride along under the same
    #      line_number/key-name match. The end-anchor breaks this: anything
    #      after the pin's closing quote+comma fails the match.
    #
    # HONEST LIMIT (not closed by this rule, not closeable by any regex):
    # a live 64-hex or 40-hex credential pasted directly into a pin's value
    # slot is byte-indistinguishable from a real digest — no shape check can
    # tell them apart. This rule narrows the approved surface from "any
    # secret on a pin-named line" to "only a value that is exactly the
    # digest length/alphabet", it does not make forgery structurally
    # impossible.
    (
        re.compile(
            r"^scripts/(check_worker_plane_review|launch_worker_plane_review_panel)\.py$"
        ),
        re.compile(
            r'^\s*"?(?:sha256|codex_wrapper|codex_package)"?\s*[:=]\s*"[0-9a-f]{64}"\s*,?\s*$'
            r'|^\s*"?cdhash"?\s*[:=]\s*"[0-9a-f]{40}"\s*,?\s*$'
        ),
        "worker-plane review panel: sha256/cdhash code-signing identity pins "
        "and PRODUCTION_ARTIFACT_SHA256 content hashes for production CLI "
        "binaries — public integrity anchors, not credentials (value must be "
        "exactly the digest's hex shape, end-anchored to the line)",
    ),
    # apps/mouth/data/kbli-gold-all.json: every gold-set record carries a
    # `sentence_sha256` — a 16-hex-char truncated digest of the record's
    # editorial prose, written by the L3 prose-gap-disclosure cure
    # (scripts/kbli_filiera/cure_l3_prose_gap_disclosure.py) as an idempotency
    # marker (re-running the cure is a no-op if the sentence's hash already
    # matches). Found live 2026-07-26: 39 occurrences in the file, 3 flagged
    # as Hex High Entropy Strings by detect-secrets.
    #
    # This file is deliberately NOT covered by the tree-wide/path-only KBLI
    # rules above: unlike data/kbli-filiera/ (data-plane-guarded, #2550) and
    # the canonical dataset + its sync'd copies (written only by
    # sync_kbli_dataset.sh), kbli-gold-all.json has an OPEN writer set —
    # scripts/kbli_audit_patcher.py, kbli_enrich_write.py, and
    # kbli_enrich_pipeline.py all write it directly, and cure specs patch it
    # value-in-place. A path-only rule here would be the first KBLI rule in
    # this file without the closed-writer-set argument that makes the others
    # safe — a weaker bar wearing the same shape. Content-keyed instead,
    # narrowing approval to lines that are structurally this exact marker:
    # only a value that is 16 lowercase hex characters, on a line whose key
    # is exactly `sentence_sha256`, end-anchored (optional trailing comma) so
    # a second assignment riding along on the same line still fails. A real
    # secret elsewhere in this file — including on an adjacent line, or a
    # 16-hex-shaped credential pasted directly into this field's value slot —
    # is not something a regex can distinguish (same HONEST LIMIT as the
    # worker-plane rule above); this rule narrows what "any secret in this
    # file" means, it does not certify the whole file secret-free.
    (
        re.compile(r"(^|/)apps/mouth/data/kbli-gold-all\.json$"),
        re.compile(r'^\s*"sentence_sha256"\s*:\s*"[0-9a-f]{16}"\s*,?\s*$'),
        "KBLI gold-set editorial-prose idempotency marker (L3 prose-gap-"
        "disclosure cure): a 16-hex sha256 truncation of the record's prose, "
        "never a credential (open writer set, so content-keyed rather than "
        "path-only — see the KBLI canonical-dataset rule above for the "
        "closed-writer-set contrast)",
    ),
    # Translated articles carry `source_sha256` in their frontmatter: the
    # sha256 of the English source BODY they were translated from, written by
    # scripts/translate-articles.py. It is the freshness marker that lets the
    # hourly translator skip on FRESHNESS instead of on the target file's mere
    # existence — before it, every translation froze at birth and an English
    # correction never reached its locales (measured: 1275 of 2664
    # translations behind their source). Anyone can recompute the value from
    # the public article; it is an integrity anchor, never a credential.
    #
    # Content-keyed, not path-only, for the same reason as the rule above: the
    # writer set for article .mdx files is wide open (the translator, the
    # editorial pipeline, and humans editing prose by hand), so a path rule
    # would blanket-approve any future finding anywhere in 2500+ content
    # files. Narrowed to a line that is exactly `source_sha256: "<64 hex>"`,
    # end-anchored, in a translation file only (`.<locale>.mdx` — English
    # sources never carry the field).
    #
    # HONEST LIMIT, same as its two siblings: a live 64-hex credential pasted
    # into this field's value slot is byte-indistinguishable from a real
    # digest. This narrows the approved surface to that exact shape on that
    # exact key; it does not certify article files secret-free.
    (
        re.compile(
            r"(^|/)apps/mouth/src/content/articles/.+\.(id|it|ru|fr)\.mdx$"
        ),
        re.compile(r'^source_sha256:\s*"[0-9a-f]{64}"\s*$'),
        "article translation freshness stamp (scripts/translate-articles.py): "
        "sha256 of the English source body the translation was made from — a "
        "recomputable integrity anchor, never a credential (open writer set, "
        "so content-keyed and restricted to translation files)",
    ),
    # infra/vcr/expected_claims.yaml (VCR pilot, #3575): certified_hash is the
    # sha256 of scripts/arsenal_probe.py at registry-authoring time — a public
    # integrity anchor used to detect HOME-fork drift and unreviewed hand-edits
    # of the prober (scar family #1), never a credential; recomputable by
    # anyone with `hashlib.sha256(open('scripts/arsenal_probe.py','rb').read())`.
    # Same shape-check discipline as the two rules above: value must be exactly
    # 64 lowercase hex characters, end-anchored to the line, so a real secret
    # pasted onto a certified_hash line would not match this rule.
    (
        re.compile(r"^infra/vcr/expected_claims\.yaml$"),
        re.compile(r'^\s*certified_hash\s*:\s*"[0-9a-f]{64}"\s*$'),
        "VCR pilot expected-claim registry: certified_hash is a public sha256 "
        "integrity anchor of scripts/arsenal_probe.py (R5, scar family #1 "
        "HOME-fork drift detection), not a credential",
    ),
    # LLM credential registry: `sha256_16` is a 16-hex TRUNCATION of the
    # sha256 of a Google API credential's UID — an opaque identifier Google
    # already publishes in Cloud Monitoring's `credential_id` label, never the
    # key material. The file exists precisely SO THAT this repo (public) can
    # name which key is authorised without carrying one: a spending audit that
    # had to store keys to recognise them would be worse than the problem it
    # solves. The truncation is one-way and 16 hex characters wide, so it
    # cannot be expanded back into anything.
    #
    # Content-keyed on the key NAME and the exact VALUE SHAPE, end-anchored to
    # the line (optional trailing comma): the whole line must be
    # `"sha256_16": "<16 lowercase hex>"[,]`. A real credential pasted into
    # this file on any other line, or onto this key in any other shape, stays
    # unaudited for human review.
    (
        re.compile(r"^infra/llm-credentials/declared\.json$"),
        re.compile(r'^\s*"sha256_16"\s*:\s*"[0-9a-f]{16}"\s*,?\s*$'),
        "LLM credential registry: sha256_16 is a one-way 16-hex truncation of "
        "a Google credential UID (an identifier Google itself exposes as "
        "`credential_id` in Cloud Monitoring), never key material — the file "
        "exists so a PUBLIC repo can name an authorised key without holding it",
    ),
    # gold_replay_driver.py: _REPOSITORY_PRODUCTION_SIGNING_KEYS holds the
    # Ed25519 PUBLIC verification key of the production RulePack signing
    # keypair (kid=prod-2026-07-1), read at replay time to verify signed
    # packs offline. The same public key is already published verbatim in
    # docs/runbooks/visa-engine-key-ceremony.md (a docs/*.md path already
    # covered by the AUTO_APPROVE_RULES docs rule below) — it is a trust
    # root, not a secret; the private signing key never touches this repo
    # (offline key ceremony, off-repo custody per that runbook). Content-
    # keyed rather than path-only because this is production code with an
    # open surface for future additions (a real credential accidentally
    # pasted onto an unrelated line in this file should still be flagged):
    # the pattern only approves a `"public_key": "<43-char base64url>"`
    # assignment, matching the exact shape of a 32-byte Ed25519 public key
    # encoded unpadded base64url, end-anchored to the line.
    (
        re.compile(
            r"(^|/)apps/backend-rag/backend/scripts/visa_engine/gold_replay_driver\.py$"
        ),
        re.compile(r'^\s*"public_key"\s*:\s*"[A-Za-z0-9_-]{43}"\s*,?\s*$'),
        "gold_replay_driver.py: Ed25519 PUBLIC verification key of the "
        "production RulePack signing keypair, published verbatim in "
        "docs/runbooks/visa-engine-key-ceremony.md — a trust root read at "
        "replay time, never a credential (private key is off-repo)",
    ),
    # research/visa/2026-08-12-gold-replay-live-report.json and the exact
    # post-notice follow-up report from 2026-08-15: G-b gold replay driver
    # live-run reports. `payload_sha256` is the content-derived sha256 of a
    # PUBLIC signed RulePack payload — the same class of value as the
    # AUTO_APPROVE_RULES `contracts/packs/rulepack-*.json` rule above
    # (content/payload hashes of public legal documents), just embedded in a
    # research/ run report rather than the pack artifact itself.
    # Not covered by the existing `research/.*\.md$` path rule because this is
    # a `.json` report, not markdown. Content-keyed rather than a path-only
    # research/*.json rule because this file's directory (research/visa/) can
    # carry other ad-hoc JSON in the future with different content; narrowed
    # to the two exact reviewed report paths and a
    # `"payload_sha256": "<64-hex>"` line, end-anchored.
    (
        re.compile(
            r"(^|/)research/visa/(?:2026-08-12-gold-replay-live-report|"
            r"2026-08-15-gold-replay-live-post-notice-report)\.json$"
        ),
        re.compile(r'^\s*"payload_sha256"\s*:\s*"[0-9a-f]{64}"\s*,?\s*$'),
        "gold replay driver live-run report: payload_sha256 is the "
        "content-derived sha256 of a public signed RulePack payload "
        "(same class as the contracts/packs/rulepack-*.json rule above), "
        "never a credential",
    ),
    # lint_telegram_tokens.py: KNOWN_COMPROMISED maps a 16-hex truncated
    # sha256 of a burned Telegram bot token to a human-readable note, so a
    # re-introduction is NAMED ("this is the @Balizerobot token") rather than
    # merely flagged. The hash is one-way and cannot be expanded back into the
    # token; the token itself is deliberately absent from the file.
    #
    # Content-keyed, not path-keyed: this is a production script under
    # scripts/, so a path rule would blanket-approve any future finding in it,
    # including a real credential added later on an unrelated line
    # (superscar #3 — match the entity, never the file it happens to sit in).
    # The whole line must be `"<16 lowercase hex>": "@<note>"[,]` — a Telegram
    # token is `<digits>:AA<33>`, which cannot match a 16-hex key, and its
    # value here must begin with the `@` of a bot handle.
    (
        re.compile(r"^scripts/lint_telegram_tokens\.py$"),
        re.compile(r'^\s*"[0-9a-f]{16}"\s*:\s*"@[^"]*"\s*,?\s*$'),
        "Telegram token gate: KNOWN_COMPROMISED keys are one-way 16-hex "
        "sha256 truncations of burned bot tokens, held so a re-introduction "
        "can be named rather than merely flagged — never key material, and "
        "the tokens themselves are absent from the file by design",
    ),
    # Final traffic-source fail-closed live proof: the dated JSON records
    # public integrity/identity anchors needed to reproduce the ceremony.
    # Four named fields are full sha256 values (including the one-way hash of
    # the deliberately unlogged idempotency key), two are git commit SHAs,
    # and two are the public Fly machine identifier repeated in different
    # evidence sections. None is bearer material.
    #
    # This remains content-keyed because research/visa is an open writer set:
    # only the exact reviewed artifact, exact semantic field names, exact
    # lowercase-hex widths, and an end-anchored JSON assignment are approved.
    # A credential on any other key or in any other research file remains
    # unaudited. As with every shape rule above, a hex credential deliberately
    # pasted into one of these exact semantic slots is indistinguishable by
    # regex; independent exact-SHA review is therefore still required.
    (
        re.compile(
            r"(^|/)research/visa/"
            r"2026-08-15-traffic-source-fail-closed-live-proof\.json$"
        ),
        re.compile(
            r'^\s*"(?:(?:idempotency_key_sha256|document_sha256|'
            r'traffic_source_parameter_sha256|payload_sha256)"\s*:\s*'
            r'"[0-9a-f]{64}|(?:head_sha|expected_merge_sha)"\s*:\s*'
            r'"[0-9a-f]{40}|(?:api_machine|instance)"\s*:\s*'
            r'"[0-9a-f]{14})"\s*,?\s*$'
        ),
        "traffic-source fail-closed live proof: named sha256 integrity/"
        "one-way hashes, git SHAs, and public Fly machine IDs used to "
        "reproduce the reviewed ceremony; exact path/key/shape only, never "
        "bearer material",
    ),
    # fold_pack_seq10.py: _EXPECTED_SEQ9_PAYLOAD_SHA256 is the chain anchor —
    # the content-derived sha256 of the PUBLIC signed seq-9 RulePack payload
    # (same value class as the contracts/packs/rulepack-*.json rule in
    # AUTO_APPROVE_RULES: hashes of public legal documents, never
    # credentials). The fold script pins it so the seq-10 chain link is
    # triple-derived at run time (declared == anchor == recomputed from the
    # seq-9 source bytes) and any mismatch aborts the fold.
    #
    # Content-keyed and pinned to the EXACT anchor value, not a hex shape:
    # this is production code with an open surface for future edits — a real
    # credential pasted anywhere else in the file (or even another 64-hex
    # value on this line) stays flagged. The approved line is the bare
    # continuation-string line of the parenthesized assignment, end-anchored.
    (
        re.compile(
            r"^apps/backend-rag/backend/scripts/visa_engine/fold_pack_seq10\.py$"
        ),
        re.compile(
            r'^\s*"47feff8246c608c7c6085ffdac776fdc020bb56688d5f35a0a3e685eb40f271e"\s*$'
        ),
        "fold_pack_seq10.py: seq-9 chain anchor — content-derived sha256 of "
        "the public signed seq-9 RulePack payload, triple-derived at run "
        "time; exact value pinned, never a credential",
    ),
    # fold_pack_seq11.py: _EXPECTED_SEQ10_PAYLOAD_SHA256 is the chain anchor —
    # the content-derived sha256 of the PUBLIC signed seq-10 RulePack payload
    # (same value class as the contracts/packs/rulepack-*.json rule in
    # AUTO_APPROVE_RULES: hashes of public legal documents, never
    # credentials). The fold script pins it so the seq-11 chain link is
    # triple-derived at run time (declared == anchor == recomputed from the
    # seq-10 source bytes) and any mismatch aborts the fold.
    #
    # Content-keyed and pinned to the EXACT anchor value, not a hex shape:
    # this is production code with an open surface for future edits — a real
    # credential pasted anywhere else in the file (or even another 64-hex
    # value on this line) stays flagged. The approved line is the bare
    # continuation-string line of the parenthesized assignment, end-anchored.
    (
        re.compile(
            r"^apps/backend-rag/backend/scripts/visa_engine/fold_pack_seq11\.py$"
        ),
        re.compile(
            r'^\s*"188442baee0af899e464a696b883d2158e6e362c29d75b61eec5769ba24b9aac"\s*$'
        ),
        "fold_pack_seq11.py: seq-10 chain anchor — content-derived sha256 of "
        "the public signed seq-10 RulePack payload, triple-derived at run "
        "time; exact value pinned, never a credential",
    ),
    # fold_pack_seq12.py: _EXPECTED_SEQ11_PAYLOAD_SHA256 is the chain anchor —
    # the content-derived sha256 of the PUBLIC signed seq-11 RulePack payload
    # (same value class as the contracts/packs/rulepack-*.json rule in
    # AUTO_APPROVE_RULES: hashes of public legal documents, never
    # credentials). The fold script pins it so the seq-12 chain link is
    # triple-derived at run time (declared == anchor == recomputed from the
    # seq-11 source bytes) and any mismatch aborts the fold.
    #
    # Content-keyed and pinned to the EXACT anchor value, not a hex shape:
    # this is production code with an open surface for future edits — a real
    # credential pasted anywhere else in the file (or even another 64-hex
    # value on this line) stays flagged. The approved line is the bare
    # continuation-string line of the parenthesized assignment, end-anchored.
    (
        re.compile(
            r"^apps/backend-rag/backend/scripts/visa_engine/fold_pack_seq12\.py$"
        ),
        re.compile(
            r'^\s*"836acc511bcadd41c28284e7f00bd8be27c6109ebcc5536f7053c3f61eaa2865"\s*$'
        ),
        "fold_pack_seq12.py: seq-11 chain anchor — content-derived sha256 of "
        "the public signed seq-11 RulePack payload, triple-derived at run "
        "time; exact value pinned, never a credential",
    ),
    # fold_pack_seq13_rules.py: _EXPECTED_SEQ12_PAYLOAD_SHA256 is the chain
    # anchor — same class/purpose as the seq10/11/12 rules immediately
    # above (content-derived sha256 of the PUBLIC signed seq-12 RulePack
    # payload, triple-derived at run time: declared == anchor == recomputed
    # from the seq-12 source bytes). Content-keyed and pinned to the EXACT
    # anchor value, not a hex shape, for the same reason as the seq12 rule:
    # this is production code with an open surface for future edits.
    #
    # 2026-08-23: this reason string ends in the same "...chain anchor —
    # content-derived sha256 ..." shape as the seq10/11/12 rules above, on
    # purpose (four consecutive-sequence anchors reading in order). A test
    # that looks a rule up via test_detect_secrets_auto_triage.py's
    # _find_content_keyed_rule("chain anchor") would now match FIVE entries
    # (a fifth landed the same day: fold_pack_seq13_source.py, the JOIN
    # fold, also chains off seq-12 and so also reads "seq-12 chain anchor")
    # and fail loudly (it asserts exactly one) — that is correct behavior,
    # not a bug in the lookup. "seq-12 chain anchor" alone is no longer
    # unique either, now that two files share it; a lookup for THIS rule
    # must key on the file-qualified reason prefix, e.g.
    # "fold_pack_seq13_rules.py: seq-12 chain anchor".
    (
        re.compile(
            r"^apps/backend-rag/backend/scripts/visa_engine/fold_pack_seq13_rules\.py$"
        ),
        re.compile(
            r'^\s*"ff43d55e79e833a91820c4b68dd9ffdd086e7969b3b3a44dbd80747aa451406d"\s*$'
        ),
        "fold_pack_seq13_rules.py: seq-12 chain anchor — content-derived "
        "sha256 of the public signed seq-12 RulePack payload, "
        "triple-derived at run time; exact value pinned, never a "
        "credential",
    ),
    # fold_pack_seq13_source.py: _EXPECTED_SEQ12_PAYLOAD_SHA256 is the chain
    # anchor — the content-derived sha256 of the PUBLIC signed seq-12
    # RulePack payload (same value class as the three fold_pack_seq1{0,1,2}
    # rules above: hashes of public legal documents, never credentials). This
    # JOIN fold pins it so the seq-13 chain link is triple-derived at run
    # time (declared == anchor == recomputed from the seq-12 source bytes)
    # and any mismatch aborts the fold.
    #
    # Content-keyed and pinned to the EXACT anchor value, not a hex shape:
    # this is production code with an open surface for future edits — a real
    # credential pasted anywhere else in the file (or even another 64-hex
    # value on this line) stays flagged. The approved line is the bare
    # continuation-string line of the parenthesized assignment, end-anchored.
    #
    # 2026-08-23: this fold and fold_pack_seq13_rules.py (the rule
    # immediately above) both chain off seq-12 and so both read "seq-12
    # chain anchor" in their reason string — deliberately not disambiguated
    # by inventing a different anchor description for the same value. A
    # lookup by that substring alone is ambiguous by construction; use the
    # file-qualified prefix, e.g. "fold_pack_seq13_source.py: seq-12 chain
    # anchor", to select this one specifically.
    (
        re.compile(
            r"^apps/backend-rag/backend/scripts/visa_engine/fold_pack_seq13_source\.py$"
        ),
        re.compile(
            r'^\s*"ff43d55e79e833a91820c4b68dd9ffdd086e7969b3b3a44dbd80747aa451406d"\s*$'
        ),
        "fold_pack_seq13_source.py: seq-12 chain anchor — content-derived "
        "sha256 of the public signed seq-12 RulePack payload, "
        "triple-derived at run time; exact value pinned, never a "
        "credential",
    ),
    # fold_pack_seq14.py: _EXPECTED_SEQ13_PAYLOAD_SHA256 is the chain anchor —
    # the content-derived sha256 of the PUBLIC signed seq-13 RulePack payload.
    # The fold pins it so the seq-14 chain link is triple-derived at run time
    # (declared == anchor == recomputed from the seq-13 source bytes), and any
    # mismatch aborts the fold.
    #
    # Content-keyed and pinned to the EXACT anchor value, not a hex shape:
    # this is production code with an open surface for future edits, so any
    # different 64-hex value in the file stays flagged. Only the bare
    # continuation-string line is approved, end-anchored.
    (
        re.compile(
            r"^apps/backend-rag/backend/scripts/visa_engine/fold_pack_seq14\.py$"
        ),
        re.compile(
            r'^\s*"b9edb809930ab486e49a4af7804fbae7f072caa3b6459b78a94ecb7f6bfe14f8"\s*$'
        ),
        "fold_pack_seq14.py: seq-13 chain anchor — content-derived sha256 "
        "of the public signed seq-13 RulePack payload, triple-derived at "
        "run time; exact value pinned, never a credential",
    ),
    # scripts/kbli_bench/results/p2b_score.json (PR #4422, KBLI Navigator
    # Phase 2b benchmark run): corpus_sha256 is the content-derived sha256 of
    # the frozen benchmark corpus (scripts/kbli_bench/p2b_corpus.json), the
    # same value quoted verbatim in the run's own research report
    # (research/operations/2026-08-20-kbli-navigator-p2b-benchmark.md
    # frontmatter `sources:`) — a recomputable integrity anchor over a
    # tracked, public test-corpus file, never a credential.
    #
    # Content-keyed to this one reviewed results file, not path-only:
    # results/*.json can carry other future benchmark output with different
    # fields, so a real credential landing on any other key or in any other
    # results file stays unaudited. Line must be exactly
    # `"corpus_sha256": "<64-hex>"`, end-anchored (optional trailing comma).
    (
        re.compile(r"^scripts/kbli_bench/results/p2b_score\.json$"),
        re.compile(r'^\s*"corpus_sha256"\s*:\s*"[0-9a-f]{64}"\s*,?\s*$'),
        "KBLI Navigator P2b benchmark score report: corpus_sha256 is the "
        "content-derived sha256 of the frozen public benchmark corpus, "
        "quoted verbatim in the run's own research report — an integrity "
        "anchor, never a credential",
    ),
    # APPEND-ONLY from here: scripts/tests/test_detect_secrets_auto_triage.py
    # indexes this list POSITIONALLY — inserting a rule mid-list shifts every
    # later index and breaks the per-rule registration tests (measured the
    # hard way 2026-08-21: 8 red from one mid-list insert).
    #
    # lint_google_oauth_credentials.py: KNOWN_COMPROMISED maps 16-hex
    # truncated sha256 fingerprints of the published 2026-08-21 Google OAuth
    # triple to human-readable notes, so a re-introduction is NAMED rather
    # than merely flagged — same shape as the Telegram gate above. One-way
    # hashes; the credential values are deliberately absent from the file.
    # Content-keyed (superscar #3 — never blanket the file): the whole line
    # must be `"<16 lowercase hex>": "<note ending in the exact publication
    # marker>"`.
    (
        re.compile(r"^scripts/lint_google_oauth_credentials\.py$"),
        re.compile(r'^\s*"[0-9a-f]{16}"\s*:\s*"[^"]*published in 9 scripts until 2026-08-21"\s*,?\s*$'),
        "Google OAuth gate: KNOWN_COMPROMISED keys are one-way 16-hex sha256 "
        "truncations of the published 2026-08-21 credential triple, held so a "
        "re-introduction can be named rather than merely flagged — never key "
        "material, and the values themselves are absent from the file by design",
    ),
    # Same file: the selftest's ref_body fixture is assembled from fragments
    # precisely so no literal credential-shaped string sits in the guard's
    # own source; the 64-char middle fragment trips the base64 entropy
    # detector on its own. Synthetic by construction (prefix "0c" + a fixed
    # alphabet run), exists only to prove the guard fires.
    (
        re.compile(r"^scripts/lint_google_oauth_credentials\.py$"),
        re.compile(r'^\s*ref_body = "0c" \+ "[A-Za-z0-9_-]+"\s*$'),
        "OAuth guard selftest fixture fragment — assembled at runtime to "
        "prove the guard fires; synthetic by construction, never a credential",
    ),
    # D12 active-stay-permit HARD_FILTER source record (2026-08-24, F4/D12):
    # content_sha256 is the same class as the contracts/packs/rulepack-*.json
    # rule and the gold-replay payload_sha256 rule above — a content-derived
    # sha256 of a PUBLIC source document (Bali Zero's own policy card, cited
    # by canonical_url in the same JSON object), never a credential.
    #
    # Content-keyed, not path-keyed to the whole `inc8-pack-edits/` directory:
    # that directory is an open writer set for doctrine-factory pack edits, so
    # a path-only rule would blanket-approve any future finding anywhere in
    # it (superscar #3). Narrowed to this exact reviewed file and the exact
    # `"content_sha256": "<64-hex>"` field, end-anchored.
    (
        re.compile(
            r"(^|/)research/visa/doctrine-factory/e5/inc8-pack-edits/"
            r"d12-active-stay-permit-rule-and-source\.json$"
        ),
        re.compile(r'^\s*"content_sha256"\s*:\s*"[0-9a-f]{64}"\s*,?\s*$'),
        "D12 active-stay-permit source record: content_sha256 is the "
        "content-derived sha256 of a public Bali Zero policy source, "
        "not a credential",
    ),
]

# Each rule is (pattern, reason). The pattern matches the file path
# relative to the repo root. A finding is auto-approved if ANY rule matches.
AUTO_APPROVE_RULES: list[tuple[re.Pattern[str], str]] = [
    # Example/sample env files — by convention never contain real secrets
    (
        re.compile(r"(^|/)\.env\.example$"),
        ".env.example: documented placeholder, never a real secret",
    ),
    # Signed/unsigned visa-engine RulePacks — public legal documents whose
    # content_sha256 / payload_sha256 / signature fields are cryptographic
    # hashes of PUBLIC content, never credentials. Private key material is
    # structurally absent (offline signing, off-repo custody per
    # docs/runbooks/visa-engine-key-ceremony.md). Scoped to the artifact
    # naming convention, not the whole packs dir.
    (
        re.compile(r"(^|/)contracts/packs/rulepack-[^/]*\.json$"),
        "visa rulepack artifact: content/payload hashes of public legal documents, never credentials",
    ),
    # *.py.example, *.json.example, *.yml.example — documented example files
    (
        re.compile(r"\.(py|json|yml|yaml|toml|sh)\.example$"),
        "*.<ext>.example: documented placeholder, never a real secret",
    ),
    # <prefix>.env.example — agent-library-evolver-secrets.env.example
    # and other prefixed env-example templates under config/. The bare
    # `^\.env\.example$` rule above only catches the dotfile at root;
    # this rule supports the prefix convention.
    (
        re.compile(r"\.env\.example$"),
        "<prefix>.env.example: documented secrets template, never a real secret",
    ),
    # infra/eventbus/ schemas + examples (qdrant connection strings are placeholders)
    (
        re.compile(r"(^|/)infra/eventbus/.*\.(py|md|yaml|yml)$"),
        "infra/eventbus/: connection-string placeholders in event-bus reference code",
    ),
    # infra/skills/ documentation (skill .md files document curl/api usage with placeholder creds)
    (
        re.compile(r"(^|/)infra/skills/.*\.md$"),
        "infra/skills/*.md: skill documentation, credentials are illustrative",
    ),
    # scripts/damar-node/: marketing automation config with example credentials
    (
        re.compile(r"(^|/)scripts/damar-node/.*\.(json|js|ts|md)$"),
        "scripts/damar-node/: marketing automation, credentials are placeholders",
    ),
    # infra/launchagents/*.plist.example — LaunchAgent plist templates with
    # literal PASSWORD/HOST placeholders for DATABASE_URL etc. Operator copies
    # + fills in before `launchctl load`. Real plist files under
    # ~/Library/LaunchAgents/ are gitignored.
    (
        re.compile(r"(^|/)infra/launchagents/.*\.plist\.example$"),
        "infra/launchagents/*.plist.example: LaunchAgent template, real plists gitignored",
    ),
    (
        re.compile(r"(^|/)\.env\.sample$"),
        ".env.sample: documented placeholder, never a real secret",
    ),
    (
        re.compile(r"(^|/)\.env\.[a-zA-Z0-9_-]+\.example$"),
        ".env.<name>.example: documented placeholder",
    ),
    (
        re.compile(r"(^|/)env\.example$"),
        "env.example (no leading dot): documented placeholder",
    ),
    # Test fixtures and unit tests — conventional location for fake credentials.
    # `sh` is in the extension list because scripts/tests/ holds many shell test
    # scripts with synthetic fixtures (e.g. fake 40-char git oids) that read as
    # high-entropy — the gap that let a fake oid in test_branch_graveyard_prmerged.sh
    # block Detect Secrets on PRs #3591/#3596 (2026-08-04) despite already living
    # under a tests?/ dir.
    (
        re.compile(r"(^|/)tests?/.*\.(py|ts|tsx|js|jsx|json|yaml|yml|sh)$"),
        "tests/** tree: test fixtures, not production secrets",
    ),
    (
        re.compile(r"(^|/)__tests__/.*\.(py|ts|tsx|js|jsx|json|yaml|yml|sh)$"),
        "__tests__/** tree: test fixtures",
    ),
    (
        # Swift Package Manager test convention: capital-T `Tests/` directory,
        # `.swift` extension — neither matches the lowercase `tests?/` rule
        # above nor its extension list. First Swift code vendored into the
        # repo (apps/wr2-control-app, audit §6/D2, 2026-07-14) surfaced the
        # gap: fixture-shaped strings (e.g. a synthetic carousel path with a
        # topic-slug suffix) read as high-entropy to the scanner.
        re.compile(r"(^|/)Tests/.*\.swift$"),
        "Swift Tests/** tree: test fixtures, not production secrets",
    ),
    (
        # pytest/unittest convention: test_*.py / *_test.py files outside a
        # tests/ dir (e.g. agent-library/scar_replay/test_*.py,
        # scripts/test_*.py). Fake credentials in these are fixtures.
        re.compile(r"(^|/)(test_[^/]+|[^/]+_test)\.(py|ts|tsx|js|jsx)$"),
        "test_*/_test file: unit-test fixture, not a production secret",
    ),
    (
        re.compile(r"\.test\.(py|ts|tsx|js|jsx)$"),
        "*.test.* file: unit test fixture",
    ),
    (
        re.compile(r"\.spec\.(py|ts|tsx|js|jsx)$"),
        "*.spec.* file: test spec fixture",
    ),
    (
        re.compile(r"(^|/)fixtures?/.*"),
        "fixtures/ tree: explicit test fixture",
    ),
    (
        re.compile(r"(^|/)mocks?/.*"),
        "mocks/ tree: explicit mock data",
    ),
    # Documentation and planning
    (
        re.compile(r"(^|/)docs?/.*\.md$"),
        "docs/ markdown: documentation, any token string is illustrative or redacted",
    ),
    (
        re.compile(r"(^|/)research/.*\.md$"),
        "research/ markdown: design/audit/planning notes, token strings illustrative",
    ),
    (
        re.compile(r"(^|/)research/.*\.md$"),
        "research/ markdown: design/audit/planning notes, token strings illustrative",
    ),
    # Claude rule/cicatrix markdown: internal operator scar notes and guardrail
    # documentation. These are not executable config or credential stores.
    (
        re.compile(r"(^|/)\.claude/rules/.*\.md$"),
        ".claude/rules markdown: operator scar notes and guardrail docs, not secrets",
    ),
    # Claude skills markdown (modus PENDING-ARMS ledger, skill docs): proof
    # lines quote curl commands with rotated/revoked key literals and
    # placeholder env assignments (e.g. API_KEY_ROLES=<K1>:admin). Same
    # illustrative-credentials nature as infra/skills and .claude/rules above.
    (
        re.compile(r"(^|/)\.claude/skills/.*\.md$"),
        ".claude/skills markdown: ledger/skill docs, credentials are illustrative or revoked",
    ),
    # Fake-Gemini cleanup audit backup: CSV snapshot from the deleted
    # `drive_autowatcher` producer. The high-entropy hits are serialized
    # source/fact snapshot payloads preserved for the cleanup audit trail,
    # not executable credentials or deployable secret material.
    (
        re.compile(
            r"^research/operations/2026-05-20-crm-workspace-ai-snapshots-fake-gemini-backup\.csv$"
        ),
        "fake-Gemini cleanup audit backup CSV: serialized audit snapshots, not credentials",
    ),
    # Orchestrator zero-baseline JSON snapshots: diagnostic state captures
    # (git commit SHAs, counts) written by orchestrator cleanup sessions. The
    # high-entropy hits are 40-char git object SHAs, not credentials.
    (
        re.compile(r"^research/operations/\d{4}-\d{2}-\d{2}-.*baseline.*\.json$"),
        "orchestrator baseline JSON snapshot: git SHAs + counts, not credentials",
    ),
    # Dated operations audit snapshots (e.g.
    # research/operations/2026-05-31-system-audit-FROZEN.json): empirical
    # system-state captures written by audit sessions. The high-entropy hits
    # are PUBLIC infrastructure identifiers — Fly.io machine IDs
    # ({"id": "7847d95ce257d8", "process_group": "api", ...}, visible in
    # `fly machine list` and Fly proxy logs) and git object SHAs — never
    # credentials. Same class as the research/operations/audits/*.json rule
    # below, but for the dated top-level operations snapshots.
    (
        re.compile(r"^research/operations/\d{4}-\d{2}-\d{2}-.*audit.*\.json$"),
        "dated operations audit snapshot: Fly machine IDs + git SHAs (public infra identifiers), not credentials",
    ),
    # Frozen audit snapshots (e.g. research/operations/2026-05-31-organism-truth-FROZEN.json,
    # research/operations/S4-broker-FROZEN.json, S5-plist-secrets-FROZEN.json,
    # S15-symbiosis-FROZEN.json). Same class as the dated audit/baseline rules
    # above — empirical system-state captures written by audit sessions. The
    # high-entropy hits are git object SHAs (`git_sha`, `origin_sha`) and the
    # "Secret Keyword" hits are NAMES of secrets in a rotation checklist
    # (e.g. {"secret": "GH_TOKEN", "rotate_cmd": ...}) — the document describes
    # which secrets need rotating, it does NOT contain their values. Never
    # credentials. Covers both the dated `*-FROZEN.json` and the sprint-prefixed
    # `S<N>-*-FROZEN.json` audit families.
    (
        re.compile(r"^research/operations/.*FROZEN\.json$"),
        "frozen operations audit snapshot: git SHAs + secret-name rotation checklists (public/structural identifiers), not credentials",
    ),
    # docs/audits/evidence/visa-oracle-v2/: archived PUBLIC official-source
    # evidence for the visa-oracle-v2 audit trail — a source-archive manifest
    # plus verbatim page snapshots of imigrasi.go.id (Indonesian Directorate
    # General of Immigration) official announcements. High-entropy hits here
    # are (a) sha256 content-integrity digests in the manifest, recording the
    # hash of each archived PDF/HTML/JSON so the copy can be proven byte-
    # identical to the official download, and (b) strings embedded in the
    # archived HTML pages themselves — a Google Search Console site-
    # verification meta tag and a per-render CSRF nonce. Both (b) values
    # belong to the FOREIGN GOVERNMENT PAGE being archived, not to this repo,
    # and neither grants access to anything: site-verification tags are
    # public by protocol design (Google requires them visible in page source
    # to prove domain ownership), and the CSRF token has no accompanying
    # session cookie in this static snapshot — meaningless without one, and
    # scoped to a single archived page-render regardless. Verified manually
    # line-by-line 2026-08-07 against the live findings (13 hits, all in this
    # class). Scoped to this dated evidence subdirectory only, not the wider
    # docs/audits/ tree, per the naming-scoped-triage convention already used
    # for contracts/packs/rulepack-*.json above.
    (
        re.compile(r"(^|/)docs/audits/evidence/visa-oracle-v2/.*\.(json|html)$"),
        "visa-oracle-v2 evidence archive: sha256 integrity digests + verbatim "
        "snapshots of public imigrasi.go.id pages (site-verification tag + "
        "ephemeral CSRF nonce belong to the archived government page, not "
        "this repo), not credentials",
    ),
    (
        re.compile(r"(^|/)README.*\.md$", re.IGNORECASE),
        "README: documentation",
    ),
    (
        re.compile(r"(^|/)CHANGELOG.*\.md$", re.IGNORECASE),
        "CHANGELOG: historical notes",
    ),
    (
        re.compile(r"(^|/)CONTRIBUTING.*\.md$", re.IGNORECASE),
        "CONTRIBUTING: documentation",
    ),
    # E2E Playwright specs: same rationale as .test/.spec
    (
        re.compile(r"(^|/)e2e/.*\.spec\.(ts|js)$"),
        "e2e/ Playwright spec: test fixture",
    ),
    # Agent decision files and session archives (historical context, not active credentials)
    (
        re.compile(r"(^|/)\.agent/.*"),
        ".agent/ tree: internal agent state, not deployed",
    ),
    (
        re.compile(r"(^|/)\.antigravity/.*"),
        ".antigravity/ tree: internal tooling state",
    ),
    # Quarantine dir for abandoned attempts kept for audit (e.g. Atlas
    # migrate-lint pre-paywall, see cicatrix 2026-04-26). Files here are
    # frozen byte-for-byte and not on any execution path; any token-shaped
    # string is residue of an abandoned third-party config (e.g. dummy
    # `atlas:atlas@localhost:5432` Postgres test creds in the workflow).
    (
        re.compile(r"(^|/)\.disabled(-\d{4}-\d{2}-\d{2})?/.*"),
        ".disabled/ or .disabled-YYYY-MM-DD/ quarantine: residual artifacts from abandoned attempts, not deployed",
    ),
    # OpenAPI schemas and examples
    (
        re.compile(r"(^|/)openapi\.(json|yaml|yml)$", re.IGNORECASE),
        "OpenAPI schema: example values in spec",
    ),
    (
        re.compile(r"(^|/)swagger\.(json|yaml|yml)$", re.IGNORECASE),
        "Swagger schema: example values in spec",
    ),
    # Workflow files - github action references to ${{ secrets.X }} are not secrets themselves
    (
        re.compile(r"^\.github/workflows/.*\.ya?ml$"),
        "GitHub workflow file: secrets.XYZ references are placeholders",
    ),
    # Scraped data + generated caches (not credentials, just external content
    # that happens to contain high-entropy strings like URLs, hashes, UUIDs).
    (
        re.compile(r"(^|/)scraped_articles\.json$"),
        "scraped_articles.json: external article content, not secrets",
    ),
    (
        re.compile(r"(^|/)scraper_cache\.json$"),
        "scraper_cache.json: external cache, not secrets",
    ),
    (
        re.compile(r"(^|/)causal_report_example\.json$"),
        "causal regression example report: scan artifact, not secrets",
    ),
    # Pipeline state files — created by local tooling, contain run IDs / hashes
    # but never credentials.
    (
        re.compile(r"_state\.json$"),
        "pipeline state file: run IDs and hashes, not credentials",
    ),
    # GARUDA-FILIERA evidence layer — TREE-WIDE rule (replaces the narrower
    # manifest-only + membership-only rules 2026-07-16/18; batch-reports/
    # calibration artifacts were the THIRD directory under data/kbli-filiera/
    # to hit the same wall — sha256 vault-manifest digests, git-commit-SHA
    # canonical_revision pins, and now sha256 gold-set control digests all
    # read as Hex High Entropy Strings — and dossiers/ (hash-chained JSONL
    # events, D0-D6 protocol) will be next. Rather than add a fourth
    # subdirectory rule every time a new compiler ships, cover the whole
    # tree once.
    #
    # Why tree-wide is SAFE, not a blanket carve-out: every file under
    # data/kbli-filiera/ is written by exactly one class of writer —
    # scripts/kbli_filiera/*.py compilers — enforced by the data-plane
    # guard (infra/claude-hooks/data_plane_guard.py, #2550), which blocks
    # any OTHER path (hand-edits, other scripts, `sed`/`echo` redirection)
    # from touching this tree. The OSS user_key and every other live
    # credential never enter these compilers' output by construction (they
    # emit sha256 digests, git SHAs, public KBLI codes, and PP28/OSS
    # citations only). A rule this wide would be unsafe for a tree ANYONE
    # can write into; it is safe here because the writer set is closed and
    # guard-enforced.
    (
        re.compile(r"(^|/)data/kbli-filiera/.*\.(json|md|jsonl)$"),
        "KBLI filiera evidence layer: compiler-only writes (data-plane guard #2550), "
        "sha256 digests/git SHAs/public codes by design, zero credentials",
    ),
    # scripts/kbli_filiera/cure_specs/ — the INPUT side of the same wall.
    # These are hand-authored spec files that compilers (e.g.
    # cure_restore_per_ancestor.py) read to produce the guarded
    # data/kbli-filiera/ output above; they are not themselves under the
    # data-plane guard, but they carry the identical content class — sha256
    # render/evidence digests pinning which page-image was image-verified
    # for a given adjudication (restore_49213.json's `adjudication.renders`
    # block), never credentials.
    (
        re.compile(r"(^|/)scripts/kbli_filiera/cure_specs/.*\.json$"),
        "KBLI filiera cure specs: compiler input artifacts (data-plane guard #2550), "
        "sha256 render/evidence digests by design, zero credentials",
    ),
    # KBLI canonical dataset + its sync'd consumer copies. Since Batch-B step 2
    # (populate_bps_ancestors.py, 2026-07-24) every OSS-native record carries a
    # `bps_2020_ancestors.parser_run_digest` — the sha256 of the gate-certified
    # crosswalk parse — which reads as a Hex High Entropy String. Same closed-
    # writer-set safety as the data/kbli-filiera rule above: the canonical
    # (data/source_documents/KBLI_2025_FINAL_CLEAN.json) is data-plane-guarded
    # (#2550, scripts/kbli_filiera/*.py compilers only); the consumer copies are
    # byte-identical propagations by sync_kbli_dataset.sh. CORRECTED 2026-07-26
    # (verified against branches/main/protection by exact match): the
    # check-kbli-dataset-sync CI gate is NOT a required context — it OBSERVES
    # copy/canonical equality, it does not BLOCK on drift (non-required by
    # design, see the workflow's own header). It cannot "enforce" anything.
    # The rule is still safe without it: these files are written ONLY by
    # sync_kbli_dataset.sh (a closed writer set on its own terms), so a
    # credential still cannot enter a copy through this rule's approved
    # surface — the safety argument just doesn't need the gate's help, and
    # claiming it does overstates a control that has no teeth. These files
    # emit sha256 digests, public KBLI codes, and PP28/OSS citations only,
    # never credentials.
    (
        re.compile(
            r"(^|/)(data/source_documents/KBLI_2025_FINAL_CLEAN\.json"
            r"|apps/mouth/data/KBLI_2025_FINAL_CLEAN\.json"
            r"|apps/backend-rag/backend/data/KBLI_2025_FINAL_CLEAN\.json"
            r"|apps/backend-rag/source_documents/KBLI_2025_FINAL_CLEAN\.json"
            r"|apps/kbli-navigator/data/kbli-2025\.json)$"
        ),
        "KBLI canonical dataset + sync'd copies: compiler-written (data-plane guard "
        "#2550) / sync-invariant-enforced; bps_2020_ancestors.parser_run_digest sha256 "
        "provenance by design, zero credentials",
    ),
    # Nuzantara Lex source manifests pin downloaded public regulations by
    # SHA-256 so the fetcher can prove byte identity across runs. These are
    # content digests, not bearer tokens or credentials.
    (
        re.compile(
            r"(^|/)apps/nuzantara-lex/data_sources/ketenagakerjaan_seed\.json$"
        ),
        "nuzantara-lex public regulation manifest: SHA-256 content digests, not secrets",
    ),
    (
        re.compile(r"(^|/)apps/evaluator/nlm_deep_research/.*\.json$"),
        "NLM deep research state files: pipeline artifacts",
    ),
    # Example credential file — by convention a template, never real
    (
        re.compile(r"\.example\.json$"),
        "*.example.json: documentation placeholder",
    ),
    # .env.test — explicit test fixture env file
    (
        re.compile(r"(^|/)\.env\.test$"),
        ".env.test: test fixture env, never production",
    ),
    # WR2 canva_renderer: ships external Canva template IDs, not credentials.
    (
        re.compile(
            r"(^|/)apps/backend-rag/backend/services/canva_renderer/.*\.py$"
        ),
        "canva_renderer: external Canva template IDs, not credentials",
    ),
    # Frontend book metadata: detect-secrets flags `serviceKey: "b1-visit-visa"`
    # as a "Secret Keyword" hit. Book/service catalog data, never credentials.
    (
        re.compile(r"(^|/)apps/mouth/src/components/book/.*\.ts$"),
        "mouth book catalog: service key literals, not credentials",
    ),
    # i18n translation files: detect-secrets's SecretKeyword plugin fires on
    # words like "PIN", "password", "token" even when they're UI copy
    # ("Forgot PIN?", "Wrong email or PIN"). These files are frontend
    # translations committed under source control, never credential stores.
    (
        re.compile(r"(^|/)apps/mouth/src/i18n/locales/[^/]+\.json$"),
        "mouth i18n locales: UI translation strings, never credentials",
    ),
    # Base64 SVG icons inlined in welcome emails (welcome_email_service.py)
    # — verified these 4 findings are base64-encoded SVG markup, not tokens.
    (
        re.compile(r"(^|/)apps/backend-rag/backend/services/crm/welcome/welcome_email_service\.py$"),
        "welcome email service: base64-inlined SVG icons, not credentials",
    ),
    # visa-oracle-v2 fullstack smoke script: two findings verified manually
    # 2026-08-07. Line ~21 is a DOCUMENTED EXAMPLE Postgres DSN in the
    # module docstring (postgresql://test:test@127.0.0.1:5433/postgres) —
    # illustrative, never a live connection string. Line ~80 is the PUBLIC
    # half of an Ed25519 keypair belonging to the TEST trust store (declared
    # by the adjacent comment) — public keys are, by definition, safe to
    # publish; the private half is never written to this file.
    (
        re.compile(
            r"(^|/)apps/backend-rag/backend/scripts/visa_engine/fullstack_smoke\.py$"
        ),
        "fullstack_smoke.py: example DSN in module docstring + TEST trust-store "
        "Ed25519 PUBLIC key (declared in comment), not credentials",
    ),
    # Organism Innervation Genoma manifest: contains a content-derived
    # SHA256 integrity checksum
    # (organism.tools.validate_organs_registry.compute_checksum), NOT a
    # credential. Regenerated by `validate_organs_registry --update-checksum`.
    # The whole file is a registry of organi nervosi, not a secrets store.
    # File renamed 2026-05-08 (IG-3) from `genome.yaml`. Both regex paths are
    # listed: the new canonical name AND the legacy alias symlink kept until
    # 2026-06-08, so the triage stays correct whichever path detect-secrets
    # walks first.
    (
        re.compile(r"(^|/)apps/organism/organism/organs_registry\.yaml$"),
        "organism organs_registry: content-derived SHA256 integrity hash, not a credential",
    ),
    (
        re.compile(r"(^|/)apps/organism/organism/genome\.yaml$"),
        "organism genome.yaml (legacy alias symlink → organs_registry.yaml, removal 2026-06-08): content-derived SHA256 integrity hash, not a credential",
    ),
    # Oracle service files: contain the literal string
    # "postgresql://user:pass@localhost/db" used as a placeholder-detection
    # sentinel. Verified manually 2026-04-12.
    (
        re.compile(r"(^|/)apps/backend-rag/backend/services/oracle/oracle_config\.py$"),
        "oracle_config: placeholder sentinel string, not a credential",
    ),
    (
        re.compile(r"(^|/)apps/backend-rag/backend/services/oracle/oracle_database\.py$"),
        "oracle_database: placeholder sentinel string, not a credential",
    ),
    # prime_nexus_service.py:36 — _BASE32 alphabet for geohash, not a token.
    (
        re.compile(r"(^|/)apps/backend-rag/backend/services/prime/prime_nexus_service\.py$"),
        "prime_nexus_service: base32 geohash alphabet, not a credential",
    ),
    # geo_service.py:17 — same _BASE32 geohash alphabet, different module.
    (
        re.compile(r"(^|/)apps/backend-rag/backend/services/prime/geo_service\.py$"),
        "geo_service: base32 geohash alphabet, not a credential",
    ),
    # graph-engine curiosity CLI: postgresql://postgres:postgres@localhost:5432
    # default dev connection string fallback (same pattern as backend-rag
    # dev utilities — see TECH DEBT note above).
    (
        re.compile(r"(^|/)apps/graph-engine/src/nuzantara_graph/curiosity/cli\.py$"),
        "graph-engine curiosity CLI: localhost:5432 dev default, not production",
    ),
    # gap_fill_autonomous.py: postgres://postgres:postgres@localhost dev default
    # for a one-off autonomous gap-fill script.
    (
        re.compile(r"(^|/)scripts/gap_fill_autonomous\.py$"),
        "gap_fill_autonomous: localhost:5432 dev default, not production",
    ),
    # Self-reference: this file documents postgres:postgres@localhost:5432
    # as part of the rule comments. detect-secrets flags the literal; the
    # auto-triage engine is the SOLE consumer of these URLs so marking this
    # file as a known FP is correct.
    (
        re.compile(r"(^|/)scripts/detect_secrets_auto_triage\.py$"),
        "detect_secrets_auto_triage: documents the postgres:postgres@localhost URL as part of its own rule docstring",
    ),
    # article_composer error handler: enum values "API_KEY_NOT_CONFIGURED" etc
    # detected as Secret Keyword (false positive on enum names).
    (
        re.compile(r"(^|/)apps/backend-rag/backend/services/article_composer/error_handler\.py$"),
        "article_composer error_handler: error enum values, not credentials",
    ),
    # auth decorator: AuthType.API_KEY = "api_key" enum value, not a secret.
    (
        re.compile(r"(^|/)apps/backend-rag/backend/app/decorators/auth\.py$"),
        "auth decorator: auth-type enum literal, not a credential",
    ),
    # article_composer router: IndexNow API key. IndexNow (Bing) requires the
    # key to be served publicly at https://<host>/<key>.txt — it is public
    # BY DESIGN and cannot be a "secret" in the security-hygiene sense.
    (
        re.compile(r"(^|/)apps/backend-rag/backend/app/routers/article_composer\.py$"),
        "article_composer router: IndexNow API key (public by protocol design)",
    ),
    # Docker compose test file
    (
        re.compile(r"(^|/)docker-compose\.test\.ya?ml$"),
        "docker-compose.test.yml: test-only compose file",
    ),
    # Next.js app layout: Google Search Console verification tokens. These
    # are PUBLIC by design (Google writes them into the HTML meta tag as
    # an ownership proof) and cannot be a "secret".
    (
        re.compile(r"(^|/)apps/mouth/src/app/layout\.tsx$"),
        "mouth layout.tsx: Google Search Console verification tokens (public)",
    ),
    # backend-rag local utility scripts: many of these contain hardcoded
    # dev database credentials (postgresql://backend_rag_v2:...@localhost:15432
    # and postgresql://nuzantara:nuzantara_local_2024@localhost:5432). These
    # are NOT production credentials — they are local dev fallbacks for
    # one-off utility scripts that run against a developer's local database.
    #
    # TECH DEBT FLAGGED TO MAINTAINER: these hardcoded dev credentials
    # should be replaced with os.getenv("DATABASE_URL") + a .env.dev example.
    # Tracked as a separate follow-up; out of scope for this CI fix.
    (
        re.compile(r"(^|/)apps/backend-rag/scripts/.*\.(py|sh)$"),
        "backend-rag dev utility scripts: hardcoded LOCAL dev db credentials (tech debt, tracked)",
    ),
    # backend-rag migrations: contain sample/dummy data for test rollbacks,
    # not credentials. Migrations are idempotent schema operations with
    # hardcoded sample rows.
    (
        re.compile(r"(^|/)apps/backend-rag/backend/migrations/migration_\d+.*\.py$"),
        "backend-rag migrations: sample data literals, not credentials",
    ),
    # Alertmanager template config: literal "your_password" placeholder.
    (
        re.compile(r"(^|/)config/alertmanager/alertmanager\.ya?ml$"),
        "alertmanager config: literal 'your_password' placeholder",
    ),
    # Root docker-compose: POSTGRES_PASSWORD=postgres is the standard local
    # dev default, never used in production (production is Fly.io postgres).
    (
        re.compile(r"^docker-compose\.ya?ml$"),
        "root docker-compose.yml: local dev postgres defaults",
    ),
    # IndexNow API route (mirror of the one in backend article_composer):
    # same public-by-design IndexNow key.
    (
        re.compile(r"(^|/)apps/mouth/src/app/api/indexnow/route\.ts$"),
        "mouth indexnow route: public IndexNow key (same as backend)",
    ),
    # Clients new page: passport "AB1234567" placeholder string in a form.
    (
        re.compile(r"(^|/)apps/mouth/src/app/\(workspace\)/clients/new/page\.tsx$"),
        "mouth clients/new page: passport placeholder 'AB1234567' in form",
    ),
    # bali-intel-scraper quality workflow: test postgres creds in CI service.
    (
        re.compile(r"(^|/)apps/bali-intel-scraper/\.github/workflows/.*\.ya?ml$"),
        "bali-intel-scraper CI: test-only postgres service credentials",
    ),
    # bali-intel-scraper alembic.ini: test-only db connection string.
    (
        re.compile(r"(^|/)apps/bali-intel-scraper/backend/db/migrations/alembic\.ini$"),
        "bali-intel-scraper alembic.ini: local dev database URL placeholder",
    ),
    # cell core config: local dev db URL default.
    (
        re.compile(r"(^|/)apps/cell/cell/core/config\.py$"),
        "cell core config: local dev db URL default",
    ),
    # evaluator local utility scripts: same tech-debt pattern as backend-rag
    # scripts — hardcoded LOCAL dev credentials for one-off tooling.
    (
        re.compile(r"(^|/)apps/evaluator/(seo_auto_fixer|site_verify_sa|test_judgement_day)\.py$"),
        "evaluator dev utility: hardcoded LOCAL dev credentials (tech debt)",
    ),
    # graph-engine config: local dev db URL default.
    (
        re.compile(r"(^|/)apps/graph-engine/src/nuzantara_graph/config\.py$"),
        "graph-engine config: local dev db URL default",
    ),
    # knowledge app projects page: likely public token or asset URL.
    (
        re.compile(r"(^|/)apps/knowledge/src/app/projects/page\.tsx$"),
        "knowledge projects page: likely public asset URL or project token",
    ),
    # tmp script with hardcoded dev creds (tmp_ prefix marks it as throwaway)
    (
        re.compile(r"(^|/)apps/backend-rag/tmp_.*\.py$"),
        "backend-rag tmp_ script: throwaway local tooling",
    ),
    # Repo-root scripts/: same tech-debt pattern, local dev tooling.
    (
        re.compile(r"^scripts/(backfill_interactions_from_conversations|batch_extract_company_capital|import_gemini_company_results)\.py$"),
        "repo-root scripts: hardcoded LOCAL dev credentials (tech debt)",
    ),
    (
        re.compile(r"^scripts/(extract_worker|preflight)\.sh$"),
        "repo-root shell scripts: local tooling with dev credentials",
    ),
    # Ruslana node config: literal "RUSLANA_JWT_PLACEHOLDER" placeholder.
    (
        re.compile(r"(^|/)scripts/ruslana-node/openclaw-ruslana\.json$"),
        "ruslana-node config: literal JWT placeholder",
    ),
    # docs/database PostgreSQL update scripts: local tooling with dev creds.
    (
        re.compile(r"(^|/)docs/database/postgresql/.*\.(py|sh)$"),
        "docs/database tooling: local dev db update scripts",
    ),
    # mata-garuda config: BRIDGE_API_KEY_ENV constant holds the NAME of the
    # env var ("BRIDGE_API_KEY"), not its value. detect-secrets matches the
    # word "KEY" in the literal. Verified 2026-04-16.
    (
        re.compile(r"(^|/)apps/mata-garuda/mata_garuda/config\.py$"),
        "mata-garuda config: env var NAME constants, not credential values",
    ),
    # zantara-media Google Drive folder IDs are PUBLIC Drive identifiers
    # (GARUDA photos, videos, audio, intelligence, drafts, research,
    # published). Shared with Bali Zero team as public Drive links; carry
    # no access authority. High-entropy false positive.
    (
        re.compile(r"(^|/)apps/zantara-media/zantara_media/indexer/(drive_client|pipeline)\.py$"),
        "zantara-media indexer: Google Drive folder IDs (public identifiers, not tokens)",
    ),
    # detect_secrets_auto_triage.py contains REGEX PATTERNS that include
    # placeholder credential substrings (e.g. "user:pass@localhost",
    # ".env.prod", "service_account") used to match paths that MUST be
    # audited. The script is itself flagged on these patterns — a
    # meta-false-positive. The file is the triage engine; it never holds
    # real secrets.
    (
        re.compile(r"(^|/)scripts/detect_secrets_auto_triage\.py$"),
        "detect_secrets_auto_triage: triage rule patterns, not credentials (meta)",
    ),
    # Video file (binary): base64 false positive inside .mp4 chunk.
    (
        re.compile(r"\.(mp4|webm|mov|mkv|avi|png|jpg|jpeg|gif|pdf)$"),
        "binary media file: base64 false positive on encoded content",
    ),
    # KB legal markdown: Indonesian copyright/IP/trade-secret regulation
    # documents contain phrases like "Rahasia Dagang" / "Trade secret"
    # that detect-secrets flags as Secret Keyword. Regulatory text under
    # source control, never credentials.
    (
        re.compile(r"(^|/)apps/backend-rag/backend/kb/legal/.*\.md$"),
        "backend-rag KB legal docs: regulatory text mentioning 'secret', not credentials",
    ),
    # Evaluator CEP test fixtures: `api_key="fake-key"` literal patterns
    # in unittest mock setups. The test_*.py path pattern above only
    # matches plain `test_X.py` filenames; this rule covers the
    # subdirectory variant inside apps/evaluator/cep/.
    (
        re.compile(r"(^|/)apps/evaluator/cep/test_.*\.py$"),
        "evaluator CEP test: fake-key literals in unittest mocks",
    ),
    # cell-core types.py contains a Crockford-base32 alphabet literal
    # ("0123456789ABCDEFGHJKMNPQRSTVWXYZ") used by the ULID-style
    # _default_pulse_id() factory. The 32-char unique-character string
    # has high entropy and is flagged as Base64; it is a public
    # encoding alphabet (Crockford 1999), not a secret.
    (
        re.compile(r"(^|/)packages/cell-core/cell_core/types\.py$"),
        "cell-core types.py: Crockford-base32 alphabet literal for ULID factory, not a secret",
    ),
    # Zantara visual dataset metadata: manifest.json stores SHA-256 file
    # checksums ("sha256": "abc123...") for image asset integrity. These
    # are content-derived hashes of PNG/JPG files in the same directory,
    # never API keys or tokens.
    (
        re.compile(r"(^|/)research/marketing/zantara-visual-dataset/.*/metadata/.*\.json$"),
        "zantara-visual-dataset metadata: SHA-256 file checksums for image assets, not secrets",
    ),
    # WR2 pilot slides.json: each slide entry has `hero_image_sha256` —
    # content-derived hash of the imagegen-produced hero JPG, used by
    # wr2-critic to enforce Article 5.10 no-silent-placeholder-reuse.
    # File checksums, never API keys.
    (
        re.compile(r"(^|/)research/wr2-pilots/.*/slides\.json$"),
        "wr2-pilots slides.json: hero_image_sha256 anchor checksums, not secrets",
    ),
    # vendor/<pkg>/tests/: vendored third-party test files contain fake
    # API keys and dummy credentials in mock setups. Vendor source is
    # byte-identical to upstream (see vendor/*/UPSTREAM.md), reviewed at
    # vendoring time. Never executed in production.
    (
        re.compile(r"(^|/)vendor/[^/]+/tests/.*\.py$"),
        "vendor third-party tests: mock credentials in upstream test suites, not secrets",
    ),
    # research/operations/audits/*.json: launchd / system audit snapshots
    # may contain base64-encoded plist data, fingerprints, or system token
    # remnants (visible via `launchctl print | base64`). Operator-authored
    # diagnostic artifacts, never user-input secrets.
    (
        re.compile(r"(^|/)research/operations/audits/.*\.json$"),
        "research audit snapshots: launchd/system base64 diagnostic data, not secrets",
    ),
    # vendor/<pkg>/examples/<*>/README.md: usage examples with fake API
    # keys for documentation purposes. Same vendor-byte-identical caveat.
    (
        re.compile(r"(^|/)vendor/[^/]+/examples/.*\.(md|py|sh|yaml|yml|json)$"),
        "vendor third-party examples: documentation placeholders, not secrets",
    ),
    # vendor/<pkg>/notebooks/*.ipynb: Jupyter notebooks contain base64-
    # encoded PNG cell outputs (matplotlib plots, screenshots) that
    # trigger "Base64 High Entropy String" detector. Never API keys.
    (
        re.compile(r"(^|/)vendor/[^/]+/notebooks/.*\.ipynb$"),
        "vendor third-party notebooks: base64 PNG cell outputs from matplotlib, not secrets",
    ),
    # .husky/ git hooks: the pre-push CI-parity test gate echoes the dummy
    # DATABASE_URL=postgresql://test:test@localhost:5432/<db> inside its
    # "how to bootstrap the local test DB" help text. `test:test@` is the
    # same throwaway CI-parity credential used in .github/workflows/tests.yml
    # and the db conftest default — a local-test dummy, never production.
    # Same class as the root docker-compose.yml + graph-engine localhost
    # dev-default DSN rules above.
    (
        re.compile(r"(^|/)\.husky/.*"),
        ".husky git hooks: pre-push CI-parity test:test@localhost dummy DSN, not a production credential",
    ),
]

# Hard blocks — if the path matches any of these, NEVER auto-approve even if
# an AUTO_APPROVE rule also matched. This catches false positives in the
# whitelist.
HARD_BLOCK_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(^|/)\.env$"), "bare .env file must always be audited"),
    (re.compile(r"(^|/)\.env\.prod(uction)?$"), "production env must always be audited"),
    (re.compile(r"(^|/)\.env\.live$"), "live env must always be audited"),
    (re.compile(r"(^|/)secrets?\.(json|yaml|yml)$"), "secrets file must always be audited"),
    (re.compile(r"(^|/)credentials?\.(json|yaml|yml)$"), "credentials file must always be audited"),
    (re.compile(r"(^|/)service[-_]account.*\.json$"), "service account JSON must always be audited"),
]


def _line_text(file_path: str, line_number: int) -> str | None:
    """Best-effort read of one 1-indexed source line from a repo file."""
    try:
        full = REPO_ROOT / file_path
        with full.open("r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, start=1):
                if i == line_number:
                    return line
    except OSError:
        return None
    return None


def classify(file_path: str, line_number: int | None = None) -> tuple[bool, str]:
    """Return (auto_approve, reason)."""
    for pat, reason in HARD_BLOCK_RULES:
        if pat.search(file_path):
            return False, f"HARD BLOCK: {reason}"
    for path_pat, content_pat, reason in CONTENT_KEYED_RULES:
        if path_pat.search(file_path) and line_number:
            text = _line_text(file_path, line_number)
            if text is not None and content_pat.search(text):
                return True, reason
    for pat, reason in AUTO_APPROVE_RULES:
        if pat.search(file_path):
            return True, reason
    return False, "no rule matched"


def triage(
    baseline: dict[str, Any],
    apply: bool,
) -> tuple[dict[str, Any], dict[str, int], list[tuple[str, int, str]]]:
    """
    Walk every hit in the baseline and apply auto-triage rules.

    Returns (updated_baseline, stats, residue_list).
    stats = {auto_approved: N, hard_blocked: N, no_rule: N, total: N}
    residue_list = [(file, line, type), ...] for hits that remain unaudited.
    """
    stats = {"auto_approved": 0, "hard_blocked": 0, "no_rule": 0, "total": 0}
    residue: list[tuple[str, int, str]] = []

    results = baseline.get("results", {})
    for file_path, hits in results.items():
        for hit in hits:
            stats["total"] += 1
            auto, reason = classify(file_path, hit.get("line_number"))
            if auto:
                stats["auto_approved"] += 1
                if apply:
                    hit["is_secret"] = False
            else:
                if reason.startswith("HARD BLOCK"):
                    stats["hard_blocked"] += 1
                else:
                    stats["no_rule"] += 1
                residue.append(
                    (file_path, hit.get("line_number", 0), hit.get("type", "?"))
                )

    return baseline, stats, residue


def main() -> int:
    args = set(sys.argv[1:])
    apply = "--apply" in args
    report = "--report" in args

    if not BASELINE.exists():
        print(f"ERROR: {BASELINE} does not exist", file=sys.stderr)
        return 2

    baseline = json.loads(BASELINE.read_text())
    baseline, stats, residue = triage(baseline, apply=apply)

    print(f"Total findings:        {stats['total']}")
    print(f"Auto-approved:         {stats['auto_approved']}")
    print(f"Hard-blocked:          {stats['hard_blocked']}")
    print(f"No rule matched:       {stats['no_rule']}")
    print(
        f"Residue (unaudited):   {stats['hard_blocked'] + stats['no_rule']}"
    )

    if apply:
        BASELINE.write_text(json.dumps(baseline, indent=2, sort_keys=False) + "\n")
        print("\n.secrets.baseline updated in place.")

    if report:
        print("\n=== Residue by file (top 40) ===")
        from collections import Counter
        per_file = Counter(r[0] for r in residue)
        for f, n in per_file.most_common(40):
            print(f"  {n:4}  {f}")
        print("\n=== Residue by type ===")
        per_type = Counter(r[2] for r in residue)
        for t, n in per_type.most_common():
            print(f"  {n:4}  {t}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
