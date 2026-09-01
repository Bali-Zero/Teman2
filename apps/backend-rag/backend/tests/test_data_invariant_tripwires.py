"""Tripwire tests for the two data-invariants that have NO other guard.

These are the "silent corruption" class (CLAUDE.md §9): a plausible change
passes every other test and CI-green while breaking something expensive.
Because the repo runs on `required-checks + auto-merge, no human review`, the
gate for this class must be a test, not a reviewer.

Born 2026-07-16 from two real gaps found the same day:
  1. The homepage_hero LeadSource drift 422'd the primary CTA for 10 days
     (#2495) — nothing linked the frontend `source=` to the backend enum.
  2. The FROZEN embedding model had no test pinning it, though a change
     silently invalidates 93,283 vectors.
"""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path

from backend.core import embeddings
from backend.services.lead_capture.source import LeadSource, PublicLeadSource


def _repo_root() -> Path:
    """Walk up from this file until the dir that contains apps/."""
    p = Path(__file__).resolve()
    while p != p.parent:
        if (p / "apps").is_dir():
            return p
        p = p.parent
    raise AssertionError("repo root (dir containing apps/) not found from test file")


# ---------------------------------------------------------------------------
# Invariant 1 — frontend lead sources ⊆ backend LeadSource enum
# ---------------------------------------------------------------------------

_SOURCE = re.compile(r'source="([a-z_]+)"')


def _frontend_lead_sources() -> dict[str, str]:
    """Every literal `source="..."` in mouth's non-test .tsx → the file it's in.

    NOT anchored to one component name. There are several lead-capture CTAs
    (WhatsAppLeadButton, AppWhatsAppCTA, ServicePricing, KBLIConsultationCTA,
    ...); anchoring to any single one would be an under-match (scar W82) that
    silently misses a value sent from a component the anchor forgot. Verified
    2026-07-16: EVERY `source="..."` literal in mouth (tests excluded) is a
    lead source — there is no unrelated `source=` prop — so a full scan is both
    complete and false-positive-free today. If a future non-lead `source=`
    prop appears, this test fails LOUDLY (clear message, add-to-enum or exclude)
    rather than a component-anchored scan failing SILENTLY — loud-wrong beats
    silent-blind for a tripwire.

    Test files are excluded: they carry deliberately-invalid sources.
    Only literals are covered — `source={variable}` is out of reach and is a
    separate, harder contract (documented limitation, not a silent hole).
    """
    mouth_src = _repo_root() / "apps" / "mouth" / "src"
    assert mouth_src.is_dir(), f"mouth src missing at {mouth_src}"
    found: dict[str, str] = {}
    for tsx in mouth_src.rglob("*.tsx"):
        if tsx.name.endswith(".test.tsx"):
            continue
        text = tsx.read_text(encoding="utf-8")
        for m in _SOURCE.finditer(text):
            found.setdefault(m.group(1), str(tsx.relative_to(_repo_root())))
    return found


def test_public_lead_source_is_a_subset_of_lead_source() -> None:
    """Every public value must decode to a persisted one, or capture 500s.

    ``PublicLeadSource.to_persisted()`` does ``LeadSource(self.value)``: a public
    member with no ``LeadSource`` twin raises ValueError at request time, AFTER
    validation has passed. It is also what makes the tripwire below sufficient —
    checking the public enum alone covers the persistence enum only while this
    containment holds.
    """
    missing = {s.value for s in PublicLeadSource} - {s.value for s in LeadSource}
    assert not missing, (
        f"PublicLeadSource members with no LeadSource twin: {sorted(missing)}. "
        "to_persisted() raises ValueError on these — a 500 after a valid request."
    )


def test_frontend_lead_sources_are_accepted_by_the_public_capture_api() -> None:
    """A frontend source the PUBLIC enum lacks = 422 on every click, silent.

    This is the exact gap that hid the homepage_hero bug for 10 days (#2495).

    Renamed and re-pointed 2026-08-28. It previously compared against
    ``LeadSource``, which is NOT the enum the route validates:
    ``LeadCaptureRequest.source`` is typed ``PublicLeadSource``, and the two
    differ. So a value present in ``LeadSource`` but absent from
    ``PublicLeadSource`` passed this tripwire green while still 422'ing in
    production — and the test's own failure message ("add the value to the
    enum") walked the reader into exactly that trap: following it literally
    turned the test green and left the POST broken.

    That was not hypothetical. ``garuda_voa`` sat in precisely that gap between
    2026-08-25 and this commit, armed to bite on the VOA funnel's go-live day
    (see PublicLeadSource's docstring). The guard now measures the thing that
    actually rejects the request.
    """
    found = _frontend_lead_sources()

    # Blindness guard (scars W82/W97): a scan that finds ~nothing must FAIL, not
    # pass green. There are 7 lead sources across the site today; a drop below 3
    # means the `source=` pattern stopped matching (prop renamed / files moved)
    # and the test went blind, not that the site lost its CTAs.
    assert len(found) >= 3, (
        f"Only {len(found)} frontend lead source(s) found ({sorted(found)}) — "
        "expected the site's several lead-capture CTAs. The scan looks blind: "
        "did the `source` prop get renamed or the CTAs move? Fix this test "
        "before trusting a green."
    )

    accepted = {s.value for s in PublicLeadSource}
    unknown = {v: f for v, f in found.items() if v not in accepted}
    assert not unknown, (
        "Frontend sends lead source(s) the public capture API does not accept "
        "→ POST /api/lead/capture returns 422, AppWhatsAppCTA swallows it, and "
        "the visitor lands on the BARE wa.me link with no prefilled message and "
        f"no lead row: {unknown}.\n"
        "Fix in apps/backend-rag/backend/services/lead_capture/source.py — the "
        "value must be in PublicLeadSource (what the route validates) AND in "
        "LeadSource with its two @property entries (what persists it). Adding "
        "it to LeadSource ALONE turns this test green while the POST keeps "
        "422'ing — that is the bug this message used to cause.\n"
        "Or fix the frontend: if the CTA is a branch of an existing funnel, "
        "reuse that funnel's source and carry the distinction in `context`."
    )


# ---------------------------------------------------------------------------
# Invariant 2 — OpenAI embedding model is FROZEN (text-embedding-3-small / 1536)
# ---------------------------------------------------------------------------


def test_openai_embedding_model_is_frozen() -> None:
    """text-embedding-3-small @ 1536 dims is FROZEN — a change invalidates the
    93,283 existing vectors with no other test failure (CLAUDE.md §9).

    This is a canary on the OpenAI init path specifically (the Sentence
    Transformers fallback deliberately uses a different model/dims). If you are
    running a real re-index, update this test in the SAME PR — that conscious
    edit is the whole point of the guard.
    """
    src = inspect.getsource(embeddings.EmbeddingsGenerator._init_openai)
    assert '"text-embedding-3-small"' in src, (
        "The OpenAI embedding default model changed away from the FROZEN "
        "text-embedding-3-small. This invalidates 93,283 existing vectors. If "
        "intentional, it needs a re-index plan and this test updated together."
    )
    assert "1536" in src, (
        "The OpenAI embedding dimensions changed away from the FROZEN 1536. "
        "Mismatched dims corrupt every similarity search against the existing "
        "index."
    )


# ---------------------------------------------------------------------------
# Invariant 3 — authoritative pricing JSON never regresses to the retired
# WhatsApp/location contact block (2026-07-18)
# ---------------------------------------------------------------------------

_RETIRED_WHATSAPP = "+62 813 3805 1876"
_RETIRED_LOCATION = "Canggu, Bali, Indonesia"

def test_authoritative_pricing_json_never_reintroduces_retired_contact() -> None:
    """``bali_zero_official_prices_2026.json`` — the file `PricingService`
    loads and ``scripts/prepare_payloads.py`` embeds into
    ``bali_zero_pricing_hybrid`` — must never regress to the retired
    WhatsApp/location.

    That retired string lived for months as stale text inside
    ALREADY-UPSERTED Qdrant vectors (payload-only patched 2026-07-18 by
    ``scripts/patch_pricing_contact_block.py``) even though this JSON's
    generator had already moved on to the correct contact info — the JSON
    was never the bug. A regression here would silently re-poison the
    collection on the next `prepare_payloads.py` regeneration.

    Deliberately does NOT check ``bali_zero_official_prices_2025.json`` —
    that file is an intentionally-frozen rollback artefact (see
    ``apps/backend-rag/backend/data/PRICING_DEPRECATED_2025.md``) and is
    excluded from every production code path by contract, not by accident.
    """
    import sys

    repo_root = _repo_root()
    if str(repo_root / "scripts") not in sys.path:
        sys.path.insert(0, str(repo_root / "scripts"))
    from pricelist_2026.schema import CANONICAL_CONTACT

    data_path = (
        repo_root / "apps/backend-rag/backend/data/bali_zero_official_prices_2026.json"
    )
    assert data_path.exists(), f"authoritative pricing JSON missing at {data_path}"

    contact = json.loads(data_path.read_text(encoding="utf-8"))["metadata"]["contact"]

    # The sheet must match its GENERATOR, not the bot's inbound number.
    #
    # This assertion used to read `contact["whatsapp"] == settings.SUPPORT_WHATSAPP`,
    # and that pin was wrong in a way that actively caused harm: on 2026-08-31 a
    # PR fixing a real defect (the two contact halves named different numbers)
    # resolved the tie toward SUPPORT_WHATSAPP *because this test said it had
    # to*, and shipped the bot's inbound number onto the client-facing price
    # list. The owner reversed it on 2026-09-01 ("lascia ari").
    #
    # They are different things and must be free to differ:
    #   - `settings.SUPPORT_WHATSAPP` is the Meta-verified number the BOT
    #     RECEIVES on — its inbound identity, which no human answers.
    #   - `contact.whatsapp` is the number a CLIENT is invited to write to.
    #     The lead-capture and document surfaces already use Ari's line: the
    #     IT and ID notification templates, the lead-capture deeplink, the
    #     welcome-practice and welcome-email services, the Canva renderer, the
    #     rendered public price list and the whole apps/mouth frontend. Among
    #     THOSE, the price sheet was the only one that disagreed.
    #
    #     NOT "every surface in the repo": a further eleven client-facing
    #     surfaces — the CRM/invoice/birthday/welcome email footers, the shared
    #     notification footer, the chat sanitizer's CTA and the website-widget
    #     prompt — still emit SUPPORT_WHATSAPP to clients. They are measured,
    #     listed by file:line in .claude/skills/modus/PENDING-ARMS.md, and left
    #     to the owner: who answers a client's invoice reply is a business
    #     decision, not a code cleanup.
    #
    # What is worth pinning is that the sheet cannot drift from the generator
    # that produces it, and that its two halves cannot name different numbers —
    # which is the defect the 2026-08-31 PR correctly identified.
    assert contact == CANONICAL_CONTACT, (
        f"{data_path.name} metadata.contact has drifted from CANONICAL_CONTACT "
        "in scripts/pricelist_2026/schema.py. Change the generator's "
        "_CANONICAL_WHATSAPP_DIGITS and regenerate, never hand-edit the sheet — "
        "hand-editing is how `whatsapp` and `wa_link` came to name different "
        "numbers in the first place. Do NOT resolve a mismatch here by copying "
        "settings.SUPPORT_WHATSAPP: that is the bot's inbound number, not the "
        "client-facing one (owner ruling 2026-09-01)."
    )
    assert contact["whatsapp"] != _RETIRED_WHATSAPP
    assert contact.get("location") != _RETIRED_LOCATION


def test_client_contact_whatsapp_matches_the_price_list_generator():
    """The two sides of the system must name the SAME client-facing number.

    `settings.CLIENT_CONTACT_WHATSAPP` is what the backend hands a client when
    the price sheet fails to load (pricing_plugin / zantara_tools fallback);
    `_CANONICAL_WHATSAPP_DIGITS` in scripts/pricelist_2026/schema.py is what
    the sheet and the rendered price list print. They live in different trees
    and neither imports the other, so nothing but this test stops them from
    drifting — and a client who reads one number on the PDF and is given a
    different one by the bot has no way to tell which is real.

    This does NOT pin either of them to `settings.SUPPORT_WHATSAPP`: that is
    the bot's inbound identity, a deliberately different number (owner ruling
    2026-09-01). See the comment on CLIENT_CONTACT_WHATSAPP in config.py.
    """
    import sys

    from backend.app.core.config import settings

    repo_root = _repo_root()
    if str(repo_root / "scripts") not in sys.path:
        sys.path.insert(0, str(repo_root / "scripts"))
    from pricelist_2026.schema import CANONICAL_CONTACT

    assert CANONICAL_CONTACT["whatsapp"] == settings.CLIENT_CONTACT_WHATSAPP, (
        f"price-list generator says {CANONICAL_CONTACT['whatsapp']!r} but "
        f"settings.CLIENT_CONTACT_WHATSAPP says "
        f"{settings.CLIENT_CONTACT_WHATSAPP!r} — change BOTH, or the sheet "
        "and the bot's own fallback will invite clients to different lines."
    )
    assert settings.CLIENT_CONTACT_WHATSAPP != settings.SUPPORT_WHATSAPP, (
        "CLIENT_CONTACT_WHATSAPP has collapsed onto SUPPORT_WHATSAPP. That is "
        "the 2026-08-31 regression: the bot's inbound number, which no human "
        "answers, handed to clients as the line to write to."
    )


def test_pricing_fallback_contacts_read_the_setting_and_never_a_literal():
    """The degraded path is the one nobody reads, so pin it by AST.

    Both pricing entry points return a `fallback_contact` when the sheet fails
    to load. Those two blocks carried a hand-typed number until 2026-09-01 and
    were missed by every earlier contact-number sweep, because nothing pointed
    at them.

    This asserts on the PARSED SOURCE, not on text, after two earlier drafts
    were broken by adversarial review in both directions:

      - A phone-SHAPE regex over-matched an IDR price literal like
        "18 500 000" and under-matched the same number in single quotes, split
        across adjacent literals, or written with dots.
      - Matching known DIGIT RUNS over raw text fixed those, and was still
        wrong twice over: it false-flagged a docstring that merely MENTIONS the
        bot's number, and it happily allowed any wrong number not on the list —
        including a typo of Ari's own, and including hard-coding Ari's number
        instead of reading the setting, which is what put the wrong number here
        in the first place.

    The question actually worth asking is not "does a forbidden number appear
    in this file" but "is the value this dict hands a client computed from the
    single source of truth". That has an exact answer in the AST: the value
    bound to `whatsapp` inside a `fallback_contact` dict must be the
    `settings.CLIENT_CONTACT_WHATSAPP` attribute — never a constant, never a
    join, never an f-string. No text obfuscation can satisfy it, and prose that
    merely names a number cannot violate it.
    """
    import ast

    root = _repo_root() / "apps/backend-rag/backend"
    sources = [
        root / "plugins/bali_zero/pricing_plugin.py",
        root / "services/misc/zantara_tools.py",
    ]
    for src in sources:
        assert src.exists(), f"pricing fallback source moved: {src}"
        tree = ast.parse(src.read_text(encoding="utf-8"), filename=str(src))

        # `settings.CLIENT_CONTACT_WHATSAPP` is only the right value if
        # `settings` is the real one. The AST sees SHAPE, not resolution, so a
        # local shim — a `class _Shadow: CLIENT_CONTACT_WHATSAPP = "<wrong>"`
        # bound to the name `settings` — produces a byte-identical node and
        # would ship the wrong number through a green suite. Contrived as a
        # typo, entirely plausible as a leftover test shim or a bad merge, and
        # cheap to close: require the real import, and require nothing to
        # rebind the name afterwards.
        imported = any(
            isinstance(n, ast.ImportFrom)
            and n.module == "backend.app.core.config"
            and any(a.name == "settings" and a.asname is None for a in n.names)
            for n in ast.walk(tree)
        )
        assert imported, (
            f"{src.name} does not import `settings` from backend.app.core.config, "
            "so `settings.CLIENT_CONTACT_WHATSAPP` below means something else."
        )
        rebound = [
            n
            for n in ast.walk(tree)
            if isinstance(n, (ast.Assign, ast.AnnAssign, ast.ClassDef, ast.FunctionDef))
            and (
                (isinstance(n, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == "settings" for t in n.targets
                ))
                or (isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
                    and n.target.id == "settings")
                or (isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name == "settings")
            )
        ]
        assert not rebound, (
            f"{src.name}:{rebound[0].lineno} rebinds the name `settings` — the "
            "AST check below would then be satisfied by a shim carrying any "
            "number at all."
        )

        found = 0
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            for key, value in zip(node.keys, node.values, strict=True):
                if not (isinstance(key, ast.Constant) and key.value == "whatsapp"):
                    continue
                found += 1
                assert isinstance(value, ast.Attribute) and (
                    value.attr == "CLIENT_CONTACT_WHATSAPP"
                    and isinstance(value.value, ast.Name)
                    and value.value.id == "settings"
                ), (
                    f"{src.name}:{getattr(value, 'lineno', '?')} binds "
                    '"whatsapp" to '
                    f"{ast.dump(value)[:80]} instead of "
                    "settings.CLIENT_CONTACT_WHATSAPP. A literal here — even "
                    "the RIGHT number today — is how the wrong one survived "
                    "the 2026-09-01 ruling's predecessor."
                )
        assert found >= 1, (
            f'{src.name} no longer contains a dict with a "whatsapp" key — the '
            "fallback_contact block was renamed or removed, and this guard has "
            "silently stopped guarding anything."
        )



# ── shared machinery for the two inbound-number guards below ────────────────
#
# Module scope on purpose. The name guard's first draft did its own bare
# `node.value == "SUPPORT_WHATSAPP"` check while the digit guard had a folder,
# and an independent reviewer walked through the name guard with
# `getattr(settings, "SUPPORT" + "_WHATSAPP")` — a one-line change a bored
# refactor could produce. Two guards against the same defect must not disagree
# about what a string IS.

_WA_FORBIDDEN_RUNS = ("628213465159", "08213465159")


def _wa_collapse(text: str) -> str:
    """Drop every dash and space, in any Unicode spelling, plus the ASCII
    punctuation a phone number is written with."""
    import unicodedata

    out = []
    for ch in unicodedata.normalize("NFKC", text):
        if ch in '.()+"\'' or ch == "\t":
            continue
        if unicodedata.category(ch) in ("Pd", "Zs", "Cf"):
            continue
        out.append(ch)
    return "".join(out)


def _wa_fold(node) -> str | None:
    """Best-effort constant fold to the string a node PRODUCES.

    Handles the shapes a hard-coded value can hide in without any single
    literal containing it: a plain constant, a `+` chain (Python only
    auto-concatenates ADJACENT literals, not ones joined by an operator),
    `SEP.join([...])` over constants, and `str(<literal>)` — which a reviewer
    used to walk a whole number past the first version of the fold as
    `"+62 821 3465 " + str(159)`.

    Returns None for anything it cannot resolve, deliberately: an unresolvable
    node is not reported innocent OR guilty by this helper, it simply is not
    folded, and its own constants are still visited by the caller's walk.
    """
    import ast

    if isinstance(node, ast.Constant):
        if isinstance(node.value, str):
            return node.value
        return None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _wa_fold(node.left), _wa_fold(node.right)
        return None if left is None or right is None else left + right
    if isinstance(node, ast.Call):
        func = node.func
        # str(<literal>) — the fold's own blind spot, closed. Only a bare
        # `str` NAME with one literal argument; anything with keywords, star-args
        # or a shadowed name is left unresolved rather than guessed at.
        if (
            isinstance(func, ast.Name)
            and func.id == "str"
            and len(node.args) == 1
            and not node.keywords
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, (str, int, float))
        ):
            return str(node.args[0].value)
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "join"
            and len(node.args) == 1
            and isinstance(node.args[0], (ast.List, ast.Tuple))
        ):
            sep = _wa_fold(func.value)
            if sep is None:
                return None
            parts = [_wa_fold(el) for el in node.args[0].elts]
            return None if any(part is None for part in parts) else sep.join(parts)
    return None


def _wa_string_values(node):
    """Yield (text, lineno) for every string this node can produce."""
    import ast

    folded = _wa_fold(node)
    if folded is not None:
        yield folded, node.lineno
    if isinstance(node, ast.JoinedStr):
        # an f-string's literal segments, so `f"...{x}... +62 821 3465 159"` is
        # seen even though the whole f-string is not a constant
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                yield value.value, node.lineno


def _wa_scan(path, rel):
    """Return the sorted DISTINCT line numbers at which `path` produces a string
    carrying a forbidden run.

    DISTINCT is load-bearing. `ast.walk` visits a JoinedStr AND each of its
    Constant children, so a single f-string with the number in it was counted
    two or three times — harmless for a pass/fail check, but the budget below
    pins an exact number, and a maintainer chasing `found 3, expected 1` would
    be chasing an AST-shape artefact rather than three occurrences.

    Exceptions are caught by CLASS, not by the one class that first came to
    mind: a >2000-term `+` chain raises RecursionError out of ast.parse, a
    deep chain raises it out of the fold itself, and a mis-encoded file raises
    UnicodeDecodeError out of read_text. None of the three is a SyntaxError,
    and any of them would otherwise abort BOTH guards for the whole PR with an
    opaque traceback instead of skipping one unparseable file.
    """
    import ast

    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), rel)
        hits = set()
        for node in ast.walk(tree):
            for text, lineno in _wa_string_values(node):
                if any(run in _wa_collapse(text) for run in _WA_FORBIDDEN_RUNS):
                    hits.add(lineno)
                    break
    except (SyntaxError, RecursionError, UnicodeDecodeError, ValueError):
        # pragma: no cover - an unreadable file fails its own tests elsewhere
        return []
    return sorted(hits)

def test_no_backend_module_hands_a_client_the_bots_inbound_number():
    """The whole-backend version of the fallback guard, buildable only now.

    Until 2026-09-01 this could not exist: eleven client-facing surfaces —
    the CRM, invoice, birthday and welcome email footers, the shared
    notification footer, the chat sanitizer's CTA and the website-widget
    prompt — legitimately still carried `settings.SUPPORT_WHATSAPP`, because
    whether a client replying to an invoice should reach Ari or the bot was an
    open BUSINESS question, not a code defect. A repo-wide ban would have had
    to encode an answer nobody had given. The owner gave it ("metti ari anche
    in quelle"), every one of those surfaces now reads
    `settings.CLIENT_CONTACT_WHATSAPP`, and the ban becomes statable.

    So: no STRING a module under backend/ can produce may contain the bot's
    inbound digits, UNLESS the module is listed below — each of which needs the
    number for INBOUND IDENTITY (matching what Meta delivers, or hashing a
    phone for log correlation), never to tell a client where to write.

    WHY THE AST AND NOT THE TEXT. The first version of this guard read the file
    line by line and collapsed a fixed set of ASCII separators. An independent
    reviewer broke it three ways in one pass, all reproduced before this
    rewrite:

      * a NON-BREAKING HYPHEN (U+2011) is not U+002D, so `+62 821‑3465‑159`
        collapsed to `62821‑3465‑159` and the forbidden run was not a substring;
      * a literal WRAPPED ACROSS TWO LINES by a formatter — `"…+62 821 3465 "`
        then `"159"` — put the two halves on different lines, and a per-line
        scan sees neither;
      * a COMMENT narrating the history ("before the fix this read …") failed
        the build for prose that emits nothing. This file, and `config.py`,
        write exactly that kind of comment.

    Walking the AST answers all three at once and is not a patch on a patch:
    Python concatenates adjacent string literals at parse time, so the wrapped
    case arrives as ONE constant; comments are not in the tree at all; and the
    separator class is now defined by Unicode category (Pd dash punctuation, Zs
    space separator) rather than by a list of characters somebody remembered.

    The cross-family reviewer then demonstrated four ways to assemble the
    number from pieces no single constant contains. Two of them are cheap to
    fold and are folded here — `"+62 821 3465 " + "159"` (a `BinOp` chain of
    constants) and `"".join(["+62 821", " 3465 159"])`. The other two need real
    dataflow (values bound to separate names, then interpolated) and are a
    NAMED RESIDUAL LIMIT rather than an oversight: closing them means a
    constant-propagation pass in a tripwire, which is a larger and more
    fragile instrument than the defect warrants. What makes that acceptable is
    that the realistic version of the hole — reaching the value without any
    digits at all, by reading the setting — is closed completely by the twin
    guard below, and that guard now catches the name as a string too.

    KNOWN OVER-MATCH, measured rather than argued. Any string that contains the
    bot's twelve digits in order fails, including a contrived one that is not a
    phone number at all (the reviewer offered `"IDR 628.213.465.159"` and a UUID
    beginning `62821346-5159`). No such string exists anywhere in this tree —
    the guard is green across the whole backend today — and the digits are
    specific enough that a collision is a thing somebody would have to write on
    purpose. Narrowing it (refusing to collapse dots, or demanding a phone-like
    prefix) would buy that back by reintroducing a spelling the reviewer
    already broke this guard with, which is a trade, not a fix. The escape for
    a genuine collision is one allowlist row carrying its reason.

    The allowlist is the whole point. A new file that hard-codes the number
    fails until somebody adds it here WITH a reason, which is the moment to
    ask whether it is an inbound-identity surface at all.
    """
    #: file -> (how many strings in it may carry the number, and why).
    #:
    #: A BUDGET, not a pass. The first version skipped these files whole, and
    #: the cross-family reviewer priced that correctly: 5,132 lines nothing
    #: looked at, so a CTA growing inside `whatsapp_chat.py` would ship. Pinning
    #: the COUNT keeps the legitimate occurrences and still fails the build the
    #: moment one more appears — the same deliberate act as adding a row, and
    #: the moment to ask whether the new one is an invitation rather than an
    #: identity.
    #:
    #: Two files the first version exempted are NOT here any more, because
    #: measuring them returned zero: `whatsapp_chat.py` and `_memory_identity.py`
    #: name the number only in `#` comments, which an AST walk never sees. They
    #: are now fully guarded rather than trusted. (`whatsapp_chat.py` still needs
    #: its row in the READER allowlist below — that is a different question.)
    INBOUND_IDENTITY_BUDGET = {
        "backend/app/core/config.py": (
            1,
            "line 28 IS the definition — SUPPORT_WHATSAPP's literal default",
        ),
        "backend/security/pii_log_identifier.py": (
            2,
            "two docstrings (module, and the normaliser at ~182) listing the "
            "spellings that must collapse to one HMAC digest",
        ),
        "backend/services/integrations/wa_outbox_worker.py": (
            1,
            "module docstring names the Meta Business number whose send-intent "
            "queue it drains — inbound identity, and written +62 821-3465-159 "
            "with dashes, which a plain grep for the spaced form did not find. "
            "That one line is why this guard collapses separators.",
        ),
    }

    root = _repo_root() / "apps/backend-rag"

    offenders = []
    counted: dict[str, list[int]] = {}
    for path in sorted((root / "backend").rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        # Tests legitimately exercise the inbound number. The exclusion is the
        # DIRECTORY and nothing else: a `name.startswith("test_")` heuristic
        # also excluded seven real production modules under backend/agents/ and
        # backend/scripts/ that merely carry that prefix (test_guardian.py is an
        # autonomous agent, not a test — zero `def test_` functions in six of
        # the seven), and it made this guard disagree with its twin below about
        # what a test IS. None of those seven names the number today, so
        # narrowing the rule costs nothing and closes a dormant blind spot.
        if rel.startswith("backend/tests/"):
            continue
        for lineno in _wa_scan(path, rel):
            if rel in INBOUND_IDENTITY_BUDGET:
                counted.setdefault(rel, []).append(lineno)
            else:
                offenders.append(f"{rel}:{lineno}")

    assert not offenders, (
        "these backend modules build a STRING carrying the bot's INBOUND "
        f"WhatsApp number, which no human answers: {offenders}. If the surface "
        "is client-facing, read settings.CLIENT_CONTACT_WHATSAPP instead. If it "
        "genuinely needs the inbound identity, give it a row in "
        "INBOUND_IDENTITY_BUDGET above with a count and the reason — and be "
        "sure it is not simply telling a client where to write."
    )

    # A budgeted file must spend exactly its budget: no more (a new occurrence
    # is the CTA this guard exists to stop), and no fewer (a budget nothing uses
    # is a standing exemption for whatever lands there next).
    for rel, (expected, reason) in INBOUND_IDENTITY_BUDGET.items():
        assert (root / rel).exists(), (
            f"{rel} has an inbound-number budget but no longer exists — drop the "
            "row rather than leaving a name nothing checks."
        )
        found = counted.get(rel, [])
        assert len(found) == expected, (
            f"{rel} carries {len(found)} strings with the bot's inbound number "
            f"(lines {found}), budgeted for {expected} — {reason}. If the new "
            "one is a client-facing CTA, read settings.CLIENT_CONTACT_WHATSAPP. "
            "If the occurrence legitimately went away, lower the number here. "
            "Note the lines are where each STRING STARTS, so a multi-line "
            "docstring reports its opening quotes, not the line you can see the "
            "number on."
        )


def test_only_the_meta_webhook_router_reads_the_bots_inbound_number():
    """The twin of the guard above, and the one that would have caught the miss.

    The literal guard matches DIGITS. It is blind to the other half of the same
    defect: a module that reads `settings.SUPPORT_WHATSAPP` by NAME and puts the
    result in front of a client. That is precisely what
    `pricing_service.py::_support_contacts` did — it returned
    `(SUPPORT_EMAIL, SUPPORT_WHATSAPP)` and three call sites shipped the second
    element to clients, in two `fallback_contact` blocks and in the `Contact:`
    line of the LLM pricing context. No digits appeared anywhere in that file,
    so the digit guard passed it, and the cross-family reviewer found it instead.

    So this guard walks the AST rather than the text and asserts that
    `settings.SUPPORT_WHATSAPP` is READ in exactly one non-test module: the Meta
    webhook router, where the value is an inbound routing identity compared
    against `display_phone_number`. config.py defines it and is exempt as the
    definition site.

    AMENDED after the cross-family reviewer broke the first draft: it matched
    only `ast.Attribute`, so `getattr(settings, "SUPPORT_WHATSAPP")` and
    `os.getenv("SUPPORT_WHATSAPP")` walked through BOTH guards — no attribute
    node for this one to see, and no digits for the other one to see. The name
    is now also treated as a string: any constant equal to `"SUPPORT_WHATSAPP"`
    counts as a read, wherever it appears. That over-matches slightly (a module
    that merely mentions the name in a string fails), which is the right
    direction here — the escape is one allowlist row with a reason, while the
    miss it replaces is a client silently handed the wrong number.
    """
    import ast

    #: file -> why it may READ the bot's inbound identity setting.
    READERS_ALLOWLIST = {
        "backend/app/core/config.py":
            "the definition site — declares SUPPORT_WHATSAPP, does not consume it",
        "backend/app/routers/whatsapp_chat.py":
            "_is_meta_inbox_public_number compares it with the webhook's "
            "display_phone_number (the 2026-08-25 double-reply defense). This is "
            "the ONLY legitimate consumer: it is routing, not an invitation.",
    }

    root = _repo_root() / "apps/backend-rag"
    offenders = []
    for path in sorted((root / "backend").rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        if rel.startswith("backend/tests/"):
            continue
        if rel in READERS_ALLOWLIST:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), rel)
        except (SyntaxError, RecursionError, UnicodeDecodeError, ValueError):
            continue  # pragma: no cover - an unreadable file fails elsewhere
        for node in ast.walk(tree):
            # settings.SUPPORT_WHATSAPP
            if isinstance(node, ast.Attribute) and node.attr == "SUPPORT_WHATSAPP":
                offenders.append(f"{rel}:{node.lineno}")
                continue
            # getattr(settings, "SUPPORT_WHATSAPP"), os.getenv("SUPPORT_WHATSAPP"),
            # or the same name ASSEMBLED — "SUPPORT" + "_WHATSAPP",
            # "".join(["SUPPORT", "_WHATSAPP"]). The first draft compared a bare
            # Constant and a reviewer walked straight through it with the `+`
            # form, so this reuses the digit guard's folder rather than keeping
            # a second, weaker idea of what a string is.
            folded = _wa_fold(node)
            if folded == "SUPPORT_WHATSAPP":
                offenders.append(f"{rel}:{node.lineno}")

    assert not offenders, (
        "these backend modules read settings.SUPPORT_WHATSAPP, the bot's INBOUND "
        f"identity that no human answers: {offenders}. If the value reaches a "
        "client — a fallback_contact block, an email footer, a prompt, an LLM "
        "context line — read settings.CLIENT_CONTACT_WHATSAPP instead. If it is "
        "genuinely inbound routing, add the file to READERS_ALLOWLIST with the "
        "reason. The name is the trap: 'support' reads like the number a client "
        "contacts for support, and it is the one number that is not."
    )

    for rel in READERS_ALLOWLIST:
        assert (root / rel).exists(), (
            f"{rel} is allow-listed as a SUPPORT_WHATSAPP reader but no longer "
            "exists — drop the row rather than leaving a name nothing checks."
        )

def test_every_repo_side_copy_of_the_client_number_agrees():
    """One number, six places that spell it out — pinned to each other.

    The adversarial seat's sharpest finding: introducing
    `settings.CLIENT_CONTACT_WHATSAPP` does NOT create a single source of truth
    while the same digits are independently typed in the price-list generator,
    the Qdrant contact-patch script and the Visa Oracle's handoff URL. Change
    Ari's line correctly in three of them and the other two go stale with every
    test still green — which is precisely the failure mode this whole PR exists
    to close, reproduced one layer up.

    There is no import path that would let the backend read the two `scripts/`
    modules at runtime, so they cannot share a constant. What they CAN share is
    a test that fails the moment they disagree.
    """
    import re
    import sys

    from backend.app.core.config import settings

    repo_root = _repo_root()
    if str(repo_root / "scripts") not in sys.path:
        sys.path.insert(0, str(repo_root / "scripts"))
    from pricelist_2026.schema import CANONICAL_CONTACT

    canonical = settings.CLIENT_CONTACT_WHATSAPP
    digits = re.sub(r"\D", "", canonical)

    assert CANONICAL_CONTACT["whatsapp"] == canonical, (
        "scripts/pricelist_2026/schema.py disagrees with "
        f"settings.CLIENT_CONTACT_WHATSAPP: {CANONICAL_CONTACT['whatsapp']!r} != {canonical!r}"
    )
    assert CANONICAL_CONTACT["wa_link"] == f"https://wa.me/{digits}", (
        "the generator's wa_link does not carry the same digits as its own "
        f"display string: {CANONICAL_CONTACT['wa_link']!r}"
    )

    # Import and compare the VALUES. A substring match on source text was the
    # first draft and it couples the guard to incidental formatting: adding a
    # `: str` annotation, or a formatter moving the assignment, breaks the test
    # without anything being wrong. Both modules are importable — the patch
    # script has no import-time side effects, only `async def` bodies do I/O.
    from patch_pricing_contact_block import CANONICAL_WHATSAPP

    from backend.services.visa_oracle.visa_oracle_service import WHATSAPP_BASE_URL

    assert CANONICAL_WHATSAPP == canonical, (
        "scripts/patch_pricing_contact_block.py's CANONICAL_WHATSAPP is stale "
        f"({CANONICAL_WHATSAPP!r}) — it would rewrite the LIVE Qdrant pricing "
        "payloads to a number that is no longer the client-facing one."
    )
    assert WHATSAPP_BASE_URL == f"https://wa.me/{digits}", (
        f"visa_oracle_service.py's WHATSAPP_BASE_URL is {WHATSAPP_BASE_URL!r} — "
        "the Visa Oracle handoff deeplink and the price list would send a "
        "client to two different numbers."
    )

    # Sixth copy, added 2026-09-01 after an independent reviewer found it. This
    # one was ALREADY correct, which is exactly why it is dangerous: a
    # hand-typed duplicate that agrees today drifts silently on the next move,
    # with the whole suite green. It is the same shape as the five above and
    # gets the same treatment. It is now derived rather than typed, so this
    # assertion pins the DERIVATION, not a literal — it goes red if somebody
    # types the digits back in.
    from backend.services.crm.welcome.welcome_email_service import _BZ_WHATSAPP

    assert _BZ_WHATSAPP == digits, (
        "welcome_email_service.py's _BZ_WHATSAPP is "
        f"{_BZ_WHATSAPP!r} — the welcome email's WhatsApp CTA button and its "
        "footer link would send a client to a different number from every "
        "other surface. Derive it from settings.CLIENT_CONTACT_WHATSAPP."
    )


def test_kbli_documents_queries_read_metadata_not_flat_business_columns() -> None:
    """`kbli_documents` (Postgres) has exactly 6 columns — `kode_kbli`, `judul`,
    `content`, `metadata` (jsonb), `created_at`, `updated_at` — verified live
    2026-07-21 via `information_schema.columns`. Business fields (`sektor_id`,
    `pma_status`, `per_skala`, ...) live INSIDE `metadata`, which is under
    active, evolving cure work by the kbli-navigator lane — this test does
    NOT pin metadata's internal keys (a moving target), only the container
    shape the router's queries depend on.

    CLAUDE.md §9 used to claim this table was flat with literal `sektor_id`/
    `pma_status`/`skala_usaha`/`kategori_risiko` columns — false; it was
    conflating this table with the genuinely-flat Qdrant KBLI payload (see
    `reindex_kbli_2025_final.py::build_payload`, "KBLI flat-payload golden
    rule"), an unrelated store. `kbli_notebook_chat.py` already queries this
    table correctly (`metadata` jsonb, not flat columns) — this test pins
    that contract so a future edit trusting the old (wrong) invariant can't
    silently reintroduce a query for a column that doesn't exist here.
    """
    router_path = (
        _repo_root() / "apps/backend-rag/backend/app/routers/kbli_notebook_chat.py"
    )
    assert router_path.exists(), f"kbli_notebook_chat.py router missing at {router_path}"
    src = router_path.read_text(encoding="utf-8")

    queries = re.findall(r"SELECT\s+([^\"']*?)\s+FROM\s+kbli_documents", src)
    assert queries, (
        "No `SELECT ... FROM kbli_documents` found in kbli_notebook_chat.py — "
        "the router stopped reading this table, or the query moved elsewhere. "
        "Update this test's target file if the query relocated."
    )

    false_flat_columns = {"sektor_id", "pma_status", "skala_usaha", "kategori_risiko"}
    for q in queries:
        selected = {c.strip() for c in q.split(",")}
        bad = selected & false_flat_columns
        assert not bad, (
            f"Query selects {bad} as if they were flat top-level columns on "
            f"kbli_documents — they don't exist there (nested inside `metadata` "
            f"jsonb, if present at all). Query: SELECT {q} FROM kbli_documents. "
            "This is the exact mistake CLAUDE.md §9's old invariant would cause "
            "— see lever #8, research/operations/2026-07-19-balizero-kb-"
            "activation-plan.md."
        )

    assert any("metadata" in q for q in queries), (
        "None of the kbli_documents queries select `metadata` — either the "
        "router no longer reads business fields from this table (fine, update "
        "this test), or it started assuming a flat schema that doesn't exist."
    )


# ---------------------------------------------------------------------------
# Invariant 4 — the committed team roster carries NO plaintext login PIN
# ---------------------------------------------------------------------------
#
# Added 2026-07-27. Until that day both roster files in backend/data/ carried a
# plaintext `pin` for all 19 team members, and backend/scripts/seed_users.py
# hashed it straight into `team_members.pin_hash` — the column
# app/routers/auth.py authenticates against. This repository is PUBLIC: those
# were not fixtures, they were published live credentials, and the chain from
# committed file to working login was complete.
#
# Removal alone does not hold: the field is convenient, and the next person who
# wants a one-command local seed will put it back. These assertions are what
# makes the removal survive.


def _roster_json_entries() -> list[dict]:
    path = _repo_root() / "apps/backend-rag/backend/data/team_members.json"
    assert path.exists(), f"team roster missing at {path}"
    entries = json.loads(path.read_text(encoding="utf-8"))
    # Blindness guard (W97): an empty/renamed roster must fail, not pass green.
    assert len(entries) >= 10, (
        f"Only {len(entries)} roster entries parsed from {path} — the roster "
        "moved or changed shape and this tripwire went blind, which is not the "
        "same thing as the roster being clean."
    )
    return entries


def test_team_roster_json_carries_no_plaintext_pin() -> None:
    """A `pin` key here is a published credential, not a fixture."""
    offenders = [e.get("email", "<no email>") for e in _roster_json_entries() if "pin" in e]
    assert not offenders, (
        f"{len(offenders)} roster entries in team_members.json carry a plaintext "
        f"`pin` field: {offenders[:5]}. That file is committed to a PUBLIC repo "
        "and seed_users.py hashes this value into team_members.pin_hash, which "
        "is what /api/auth/login checks — so it is a live credential. PINs "
        "belong outside the repo (TEAM_PINS_FILE); see seed_users.load_pins()."
    )


def test_team_roster_python_module_carries_no_plaintext_pin() -> None:
    """Same invariant on the .py twin — curing one copy of two cures neither."""
    from backend.data.team_members import TEAM_MEMBERS

    assert len(TEAM_MEMBERS) >= 10, (
        f"Only {len(TEAM_MEMBERS)} entries in team_members.py — tripwire blind."
    )
    offenders = [m.get("email", "<no email>") for m in TEAM_MEMBERS if "pin" in m]
    assert not offenders, (
        f"{len(offenders)} entries in backend/data/team_members.py carry a "
        f"plaintext `pin`: {offenders[:5]}. See the JSON twin's message."
    )


def test_collaborator_profile_cannot_serialize_a_pin() -> None:
    """The profile that fans out to tools/routers must not be able to emit one.

    Before 2026-07-27 `CollaboratorProfile` had a `pin` field and `to_dict()`
    serialized it. No route returned that dict at the time — it was one wiring
    away, which is exactly the state that turns into an incident later.
    """
    import dataclasses

    from backend.services.crm.collaborator_service import CollaboratorProfile

    field_names = {f.name for f in dataclasses.fields(CollaboratorProfile)}
    assert "pin" not in field_names, (
        "CollaboratorProfile grew a `pin` field again. This object is built "
        "from the committed roster and serialized by to_dict(); a credential "
        "must not be reachable from it."
    )
    # Blindness guard: prove we are looking at the real profile, not a stub.
    assert {"email", "role", "department"} <= field_names, (
        f"CollaboratorProfile fields look wrong ({sorted(field_names)}) — the "
        "class moved or was replaced and this tripwire is checking a phantom."
    )

    profile = CollaboratorProfile(
        id="t1",
        email="t@balizero.com",
        name="T",
        role="Member",
        department="Ops",
        team="Ops",
        language="en",
    )
    assert "pin" not in profile.to_dict(), "to_dict() emits a `pin` key again."


def test_seeder_does_not_read_a_pin_from_the_committed_roster() -> None:
    """The seeder is what made those PINs *live*. Keep its source out of them."""
    path = _repo_root() / "apps/backend-rag/backend/scripts/seed_users.py"
    assert path.exists(), f"seed_users.py missing at {path}"
    src = path.read_text(encoding="utf-8")

    for pattern in ('user["pin"]', "user['pin']", 'user.get("pin")', "user.get('pin')"):
        assert pattern not in src, (
            f"seed_users.py reads {pattern} again — that re-arms the chain "
            "committed roster -> pin_hash -> /api/auth/login. PINs must come "
            "from TEAM_PINS_FILE, outside the repository."
        )

    assert "load_pins" in src, (
        "seed_users.py no longer has load_pins() — the out-of-repo PIN source "
        "was removed. If it was replaced, point this test at the replacement "
        "rather than deleting the check."
    )


def test_the_voa_prices_are_the_ones_the_owner_ruled():
    """e-VOA 750.000 IDR, extension 850.000 IDR — ruled by the owner on
    2026-08-31, reversing his own 2026-07-24 directive that had moved issuance
    to 790.000. Both stores now say 750.000; migration 303 is what moved the
    table, migration 302 (already applied in production) is what had moved it
    to 790.000 hours earlier, and both stay in the frozen set below because
    both really do assign this column.

    This is a value tripwire, not a style check. `practice_types.base_price`
    defaults a client quote (`crm_practices.py`), the JSON drives GARUDA and
    the visa_engine adapter at request time, and nothing reconciles the two —
    so a silent edit to either figure re-opens the divergence migrations 302
    and 303 closed. If the owner rules a new price, change it here in the same commit.
    """
    import json
    import re
    from pathlib import Path

    from backend.services.pricing.pricing_service import _PRICING_FILENAME

    backend_dir = Path(__file__).resolve().parents[1]

    # --- side 1: the JSON sheet the live pricing service loads.
    # The filename comes from the service, never typed here: a tripwire that
    # watches a path the service has stopped reading is worse than none.
    sheet = json.loads(
        (backend_dir / "data" / _PRICING_FILENAME).read_text(encoding="utf-8")
    )
    single = sheet["services"]["single_entry_visas"]
    assert single["B1 Visa on Arrival (VOA)"]["price"] == "750.000 IDR"
    assert single["B1 Visa on Arrival Extension"]["price"] == "850.000 IDR"

    # --- side 2: practice_types.base_price, which is the half that was WRONG.
    # There is no live database in a unit test, and regex-parsing SQL to work
    # out a column's final value would be a second, worse implementation of
    # the migration runner. So this is a RATCHET, not a parser: the set of
    # migrations that touch each code is frozen, and the ruled figure must
    # appear in the newest of them. A future migration that moves either
    # price cannot do so silently — it enters the set, the set stops matching,
    # and whoever wrote it has to come here and say what the new price is.
    ruled = {
        "visa_b1_voa": (750000, {"221_practice_types_b1_voa.sql",
                                 "302_practice_types_voa_price_790.sql",
                                 "303_practice_types_voa_price_750.sql"}),
        "ext_b1_voa": (850000, {"221_practice_types_b1_voa.sql"}),
    }
    migrations = sorted(
        (backend_dir / "db" / "migrations_v2").glob("*.sql"),
        key=lambda f: int(f.name.split("_", 1)[0]),
    )
    assert migrations, "no migrations_v2/*.sql found — the glob is watching nothing"

    def _forward_body(path: Path) -> str:
        """Executable lines of the forward section — comments narrate history."""
        forward = path.read_text(encoding="utf-8").split("-- === ROLLBACK ===")[0]
        return "\n".join(
            line for line in forward.splitlines()
            if not line.lstrip().startswith("--")
        )

    def _base_price_assignments(body: str, code: str) -> tuple[list[int], list[str]]:
        """Every site that assigns base_price, and every site not readable.

        Returns (values, unreadable). A shape this cannot parse lands in
        `unreadable` and reddens the test — silence is never the answer.
        """
        values: list[int] = []
        unreadable: list[str] = []
        consumed: list[tuple[int, int]] = []

        for m in re.finditer(r"\bSET\s+base_price\s*=\s*(\d+)", body, re.I):
            values.append(int(m.group(1)))
            consumed.append(m.span())

        # The upsert idiom: `INSERT ... ON CONFLICT DO UPDATE SET base_price =
        # EXCLUDED.base_price` (migration 221). It carries no figure of its own
        # — it forwards the VALUES tuple, which the INSERT branch below reads —
        # so it is RECOGNISED and contributes nothing, rather than being
        # mistaken for an unreadable spelling.
        for m in re.finditer(r"\bbase_price\s*=\s*EXCLUDED\.base_price", body, re.I):
            consumed.append(m.span())

        # `SET (col, col) = (val, val)` — read base_price's value positionally.
        for m in re.finditer(r"\bSET\s*\(([^)]*)\)\s*=\s*\(([^)]*)\)", body, re.I):
            cols = [c.strip().lower() for c in m.group(1).split(",")]
            vals = [v.strip() for v in m.group(2).split(",")]
            consumed.append(m.span())
            if "base_price" not in cols:
                continue
            raw = vals[cols.index("base_price")] if len(vals) == len(cols) else None
            if raw is not None and raw.isdigit():
                values.append(int(raw))
            else:
                unreadable.append(f"tuple SET with non-literal base_price: {m.group(0)[:80]}")

        if not values and f"'{code}'" in body:
            # An INSERT rather than an UPDATE: 221 seeds both codes positionally.
            start = body.index(f"'{code}'")
            tuple_text = body[start:body.index(")", start)]
            values = [int(v) for v in re.findall(r"\b(\d{5,})\b", tuple_text)]

        # Any remaining `base_price ... =` outside a site already consumed is a
        # spelling this function does not know. Red, not silent.
        for m in re.finditer(r"\bbase_price\b\s*=", body, re.I):
            if not any(a <= m.start() < b for a, b in consumed):
                unreadable.append(
                    "unrecognised assignment near: "
                    f"{body[max(0, m.start() - 40):m.start() + 40]!r}"
                )
        return values, unreadable

    # A migration may only move base_price on rows it names LITERALLY. The same
    # seat measured the second bypass: a migration whose predicate is
    # `WHERE code LIKE 'visa_b1_vo%'` never enters the frozen setter set below,
    # because the set is keyed on the literal code — so it can move a ruled
    # price without any of this noticing. A pattern predicate is therefore
    # refused outright rather than parsed: this tripwire is not a SQL engine and
    # must not pretend to be one.
    _OPAQUE_PREDICATE = re.compile(
        r"\bcode\s*(?:LIKE|SIMILAR\s+TO|~\*?|!~|<>|!=)|\bcode\s+IN\s*\(\s*SELECT",
        re.I,
    )
    for path in migrations:
        body = _forward_body(path)
        if "base_price" not in body:
            continue
        hit = _OPAQUE_PREDICATE.search(body)
        assert hit is None, (
            f"{path.name} assigns base_price while selecting rows by a "
            f"NON-LITERAL code predicate: {hit.group(0) if hit else ''!r}. A "
            "migration that moves a price must name the codes it targets "
            "literally, or this "
            "ratchet cannot see it move — which is precisely the bypass this "
            "check exists to close."
        )

    for code, (expected, expected_files) in ruled.items():
        touching = []
        for path in migrations:
            forward = path.read_text(encoding="utf-8").split("-- === ROLLBACK ===")[0]
            # Comments narrate history — 302's header quotes the OLD price —
            # so only executable lines count as touching the code.
            body = "\n".join(
                line for line in forward.splitlines()
                if not line.lstrip().startswith("--")
            )
            if f"'{code}'" in body and "base_price" in body:
                touching.append((path.name, body))

        assert {name for name, _ in touching} == expected_files, (
            f"the set of migrations that set base_price for {code!r} has "
            f"changed: expected {sorted(expected_files)}, found "
            f"{sorted(name for name, _ in touching)}. If a new migration "
            "moves this price, update the ruled figure here in the same "
            "commit — that is what this ratchet is for."
        )
        newest_name, newest_body = touching[-1]

        # Read the value out of the ASSIGNMENT, never "the figure appears
        # somewhere in the file". 302's guard clause and its exception message
        # both contain the literal 790000, so a substring check is satisfied by
        # a file whose SET clause says something else entirely — measured: the
        # gate mutated only `SET base_price = 790000` to 750000 and the earlier
        # version of this assertion stayed green.
        #
        # But reading ONE spelling of the assignment is the other half of the
        # same defect, and the codex-gpt-5.6-sol seat measured it: appending
        #
        #     UPDATE practice_types
        #        SET (base_price, updated_at) = (790000, CURRENT_TIMESTAMP)
        #      WHERE code = 'visa_b1_voa';
        #
        # leaves the database at 790000 while `assigned` still reads only the
        # earlier scalar SET and the test stays GREEN. So the rule here is not
        # "recognise the shapes I thought of" but "every assignment site must be
        # READABLE, or the test goes red": an unparsed spelling is a failure,
        # never a pass. Under-match is the quieter twin of over-match
        # (superscar #3 / W82) and it is the one that lets a wrong price ship.
        assigned, unreadable = _base_price_assignments(newest_body, code)
        assert not unreadable, (
            f"{newest_name} assigns base_price in a form this tripwire cannot "
            f"read: {unreadable}. That is a RED, not a pass — an unrecognised "
            "spelling is exactly how a wrong price would slip past. Either "
            "write the assignment as `SET base_price = <n>`, or teach "
            "_base_price_assignments the new shape in the same commit."
        )

        assert assigned, (
            f"{newest_name} is the newest migration touching base_price for "
            f"{code!r}, but no assignment could be read out of it. The shape "
            "changed; re-read the file rather than loosening this check."
        )
        assert set(assigned) == {expected}, (
            f"{newest_name} is the newest migration setting base_price for "
            f"{code!r}, and it assigns {sorted(set(assigned))} rather than the "
            f"ruled {expected}. The database half of the price has drifted "
            "from the sheet half — exactly the divergence migration 302 closed."
        )
