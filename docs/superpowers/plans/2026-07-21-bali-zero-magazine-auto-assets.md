# Bali Zero Magazine Automatic Assets Implementation Plan

**Goal:** Close the approved Magazine media-resolver gap so standard morning editions and qualified Breaking stories can obtain one original, verified editorial hero automatically on Pro, while quiet editions and failed gates fall back to typography.

**Architecture:** Keep the existing content-addressed Sites upload and story binding contract unchanged. Add a Pro-local resolver in `zantara_media.magazine` that selects the canonical lead story, builds a non-sensitive editorial prompt from already-sanitized packet fields, invokes the existing FlowKit CLI without a shell, validates the returned raster with Pillow, runs local vision/DLP checks, rejects duplicate or unsafe output, and writes an `asset-intents.v1` manifest. The publisher then uses the existing upload and canonical-digest binding path. Generation failure is explicit and non-fatal: the packet remains image-free and the Site renders its typographic fallback.

**Tech stack:** Python 3.11, Pydantic v2, Pillow, asyncio subprocess, existing `scripts/flowkit_cli.py`, pytest.

---

## Task 1: Resolver contract and selection

**Files:**

- Create: `apps/zantara-media/zantara_media/magazine/media_resolver.py`
- Create: `apps/zantara-media/tests/magazine/test_media_resolver.py`

1. Write failing tests for one lead asset in a standard edition, one asset for Breaking, and no asset for a quiet edition.
2. Implement deterministic target selection and a bounded prompt derived only from title, deck, domain, and why-it-matters.
3. Verify the tests turn green.

## Task 2: Generation and fail-closed media verification

**Files:**

- Modify: `apps/zantara-media/zantara_media/magazine/media_resolver.py`
- Modify: `apps/zantara-media/tests/magazine/test_media_resolver.py`

1. Write failing tests for FlowKit failure, malformed JSON, unsupported/animated/oversized raster, DLP indeterminate, detected PII, and duplicate output.
2. Implement shell-free async FlowKit invocation, Pillow decode/format/size checks, local vision extraction plus DLP, SHA-256 and perceptual duplicate checks, and generated provenance.
3. Keep failures explicit and return an empty manifest so the approved typographic fallback remains available.

## Task 3: Publisher and schedule integration

**Files:**

- Modify: `apps/zantara-media/zantara_media/cli/magazine_publish.py`
- Modify: `infra/launchagents/wrappers/bali-zero-magazine-publish.sh`
- Modify: `apps/zantara-media/tests/magazine/test_cli.py`
- Modify: `apps/zantara-media/tests/magazine/test_magazine_prepare_cli.py`
- Modify: `docs/runbooks/bali-zero-magazine.md`

1. Write failing CLI/wrapper tests proving automatic resolution is enabled on Pro, can be disabled with `MAGAZINE_AUTO_ASSETS=false`, and never runs for dry-run unless explicitly requested.
2. Resolve an empty asset manifest immediately after packet composition and before the existing upload/bind sequence.
3. Preserve explicit pre-bound manifests and never overwrite approved operator assets.

## Task 4: Verification and handoff

1. Run the media-resolver and CLI tests first.
2. Run the full `apps/zantara-media/tests/magazine` suite and Ruff for changed Python files.
3. Run wrapper syntax and contract checks.
4. Review the diff for PII, secrets, shell injection, logging, and unrelated changes.
5. Commit and push the feature branch; open a PR for independent Claude review. Do not merge, deploy, or arm LaunchAgents from this session.
