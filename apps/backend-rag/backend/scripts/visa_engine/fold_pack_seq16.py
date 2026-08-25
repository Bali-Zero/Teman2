"""fold_pack_seq16.py — assemble ``rulepack-prod-016.source.json`` from seq-15
by adding ``TOURISM`` to E23's two ELIGIBILITY rules. Nothing else changes.

V1/E23-purpose-coverage lane (2026-08-26), owner GO. Cures gold persona #15 —
the one divergence `contracts/gold-accepted-explanations.json` deliberately
leaves unexplained.

**This fold edits ONE PRODUCT and TWO RULES: 111 rules in, 111 out, 38 products
in, 38 out, zero added, zero removed.** The product is not incidental — see the
compiler note below: widening the rules alone produces a pack that validates and
does not compile.

WHY, WITH THE PRIMARY SOURCE READ AT THE SOURCE

Persona #15 declares two purposes, ``TOURISM`` + ``EMPLOYMENT``, and wants E23.
The engine answers ``NEEDS_INPUT`` because ``evaluator.py`` requires EVERY
declared purpose to be covered by the union of the ``covered_purposes`` of the
product's TRUE eligibility rules, and both of E23's declare ``["EMPLOYMENT"]``
alone. So a person who works in Indonesia and also intends to see the island
falls out of the funnel.

That is the pack under-declaring, not the corpus over-asking. Keputusan Menteri
Imigrasi dan Pemasyarakatan No. M.IP-08.GR.01.01 Tahun 2025 (*Klasifikasi
Visa*), Lampiran, "Klasifikasi Visa Tinggal Terbatas", row **E23**, column
**Hak**, item **4**, verbatim::

    Melakukan kegiatan yang berhubungan dengan wisata, melakukan pembelian
    barang, serta mengunjungi keluarga dan teman

An E23 holder has an EXPLICIT right to tourism activity. Provenance, because a
regulatory edit deserves it — anchored to a HASH, not to a path or a byte count,
so it stays checkable after every scratch directory is gone::

    sha256  b8e326667c892ab2dfb52be220c82a0716bab6a516fe925c5e45096e9ef81c33
    size    1,906,368 bytes   pages 80   magic %PDF

Validated by MAGIC BYTES (``od -c -N4`` == ``%PDF``), never by HTTP status — that
portal answers 200 with an HTML error page. The row was extracted independently
FOUR times: three by the authoring session (the last from the owner's own copy of
the file, confirmed byte-identical by sha256), and once by an independent second
reader dispatched to REFUTE the reading rather than confirm it.

That second reader established the column boundaries by a better method than the
first: this table interleaves Hak / Kewajiban / Larangan on the same physical
lines under ``pdftotext -layout``, but **each column runs its own independent
numbered list** (Hak 1)-5), Kewajiban 1)-4), Larangan 1)-4)), so the numbering
resets — not horizontal position — are the unambiguous column marker. It
confirmed all five Hak items verbatim.

The row is on **page 35**, where ``wisata`` occurs exactly once (checked for
hyphen-split fragments too). Caveat carried rather than smoothed: the PDF was
produced by a merge/split tool, and each page's own "- N -" label sits at the TOP
of its extraction; no off-by-one was detected across pages 34/35/36, but the
label's provenance is a tool artifact. An earlier internal factbase estimated
pages 37-38 and NB-2 said "Lampiran B.1" — both wrong on the coordinate while
right on the substance.

The pack's OWN convention already does this everywhere else: ``el.e33g
.remote-work`` declares ``["REMOTE_WORK", "TOURISM", "FAMILY"]``, and four more
rules pair ``SECOND_HOME`` with ``TOURISM``. Measured on seq-15, the bare
``["EMPLOYMENT"]`` appears exactly TWICE — and both are E23's.

DO NOT read that as "the Kepmen singles out E23". It does the opposite: the
second reader found item 4 is BOILERPLATE across dozens of visa codes (verbatim
on D14, D17, E23A, E23U; ``pembelian barang`` occurs 114 times in the 80-page
document). E23 is the outlier IN OUR PACK, not in the regulation — it is simply
the product where a gold persona happened to expose the gap. Measured on this
same payload, **23 of 38 products declare no TOURISM at all**, including E23U
and E23V whose identical Hak item the reader verified. Whether the others are
under-declared too is UNVERIFIED — each needs its own row read before anyone
touches it, which is precisely the discipline this fold followed for E23 and
refused to shortcut for FAMILY. Recorded as a lane in the modus ledger, not
silently widened here.

WHY ``FAMILY`` IS NOT ADDED — the full cell says something different

Reading the complete Hak column, not just the one item, settles this against a
widening. The five entries are NOT of one kind:

* item **1** — work in an employment relationship: the holder's own activity.
* item **2** — ``Membawa keluarga untuk tinggal di wilayah Indonesia SEPANJANG
  memenuhi ketentuan peraturan perundang-undangan di bidang keimigrasian``:
  bringing dependants to reside, **conditional**, and the condition defers to
  OTHER immigration provisions — in this engine, the family products (E31*),
  which is where a dependant's own permit comes from. The second reader
  specifically checked that ``sepanjang`` belongs to item 2's own four-line text
  block and is not bleeding in from the neighbouring Kewajiban column (which at
  that point reads an unrelated sentence ending ``...di bidang ketenagakerjaan``)
  — that was the crux of the reading and it holds. It also found the identical
  clause verbatim on E23A and E23U, so the conditional is a REGIME-WIDE template,
  not an E23 peculiarity: the conditional-family / unconditional-tourism
  asymmetry is systematic, which strengthens this reading rather than weakening
  it.
* item **3** — re-entry while the Izin Masuk Kembali is valid.
* item **4** — tourism, shopping, and visiting family and friends: the holder's
  own activity, stated with **no condition attached**. This is the one folded in.
* item **5** — receiving remuneration for the work.

``covered_purposes`` answers "which purposes DECLARED BY THE APPLICANT does this
product satisfy". Item 2 is a derived, conditional right to bring OTHERS, not a
purpose the E23 applicant pursues — someone whose declared purpose is ``FAMILY``
is coming FOR family reasons, which is E31's shape. Item 4's own "mengunjungi
keluarga dan teman" is VISITING inside a tourism right, not residing for family.

An earlier draft of this docstring argued the opposite from the E33A/E33G analogy
("they carry FAMILY beside the primary purpose, so E23 wants it too"). That
analogy is weaker than it read: those are DIFFERENT rows with their own Hak
columns, which this session has not opened. The tourism widening does not lean on
it — item 4 is unconditional on its own terms — but the FAMILY case did, and it
does not survive the full text. Left to the owner (Legge 5) with the reading
above rather than silently dropped.

    PYTHONPATH=. python -m backend.scripts.visa_engine.fold_pack_seq16
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

from backend.scripts.visa_engine.compile_pack import wrap_as_unsigned_pack
from backend.services.visa_engine.bundle import canonicalize_json
from backend.services.visa_engine.compiler import build_compiled_pack
from backend.services.visa_engine.fact_registry import DEFAULT_FACT_REGISTRY
from backend.services.visa_engine.models import RulePackPayload

_THIS_FILE = Path(__file__).resolve()
_BACKEND_ROOT = _THIS_FILE.parents[2]
_REPO_ROOT = _THIS_FILE.parents[5]

_PACKS_DIR = _BACKEND_ROOT / "services" / "visa_engine" / "contracts" / "packs"
_SEQ15_SOURCE = _PACKS_DIR / "rulepack-prod-015.source.json"
_SEQ15_SIGNED = _PACKS_DIR / "rulepack-prod-015.signed.json"
_SEQ16_OUT = _PACKS_DIR / "rulepack-prod-016.source.json"

_PRETTIER_BIN = _REPO_ROOT / "node_modules" / ".bin" / "prettier"

_SEQ16_SEQUENCE = 16
_SEQ16_VERSION = "2026.8.26"
_SEQ16_RULE_PACK_ID_URL = (
    "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/16"
)
_SEQ16_CREATED_AT = "2026-08-26T06:00:00Z"
_SEQ16_CREATED_BY = "agent.pro.visa-oracle.e23-tourism-coverage.fold-2026-08-26"

_IDENTITY_KEYS = frozenset(
    {"sequence", "version", "rule_pack_id", "previous_payload_sha256", "created_at", "created_by"}
)

# fmt: off
_EXPECTED_SEQ15_PAYLOAD_SHA256 = (
    "08ba8b09729590ccbabc111c6fa9126dd8c22d8b58e7be799ff2a329e488bdbd"
)
# fmt: on

#: The two rules this fold edits. Both are E23 ELIGIBILITY SUPPORT rules; both
#: declare ``covered_purposes: ["EMPLOYMENT"]`` on seq-15.
_EDITED_RULE_IDS = (
    "el.e23-employment-support",
    "el.e23-operational-work-boundary",
)

#: The one PRODUCT this fold edits. Widening the rules alone does NOT compile:
#: ``compile_rule_pack`` rejects a SUPPORT rule claiming a purpose the product
#: does not declare (``SUPPORT_RULE_PURPOSE_NOT_ON_PRODUCT``). The product's
#: own ``covered_purposes`` is the outer bound, so both move together or the
#: pack is not buildable — measured, not assumed: the first draft of this fold
#: edited only the rules and the compiler refused it.
_EDITED_PRODUCT_CODE = "E23"

#: NOT edited, deliberately: E23U and E23V also declare ``["EMPLOYMENT"]``, but
#: each carries exactly ONE rule and it is ``REQUIRE_REVIEW`` at HUMAN_REVIEW,
#: never ``SUPPORT`` — so neither the compiler bound nor ``evaluator``'s
#: purpose-coverage requirement (which reads TRUE *ELIGIBILITY* rules) ever
#: engages for them. Verified on seq-15 before writing this line.
#:
#: BE PRECISE ABOUT WHY, because the normative half points the other way: the
#: independent reader confirmed E23U's Hak item 4 is VERBATIM IDENTICAL to
#: E23's, so E23U is under-declared in exactly the same sense E23 was. The
#: reason to leave it is ENGINE-shaped, not law-shaped — the widening would have
#: no consumer today. ``test_the_review_only_siblings_were_not_widened`` is the
#: tripwire: the day either product gains a SUPPORT rule, it goes red and this
#: decision has to be retaken.
_UNTOUCHED_SIBLING_PRODUCTS = ("E23U", "E23V")

_BEFORE = ["EMPLOYMENT"]
_AFTER = ["EMPLOYMENT", "TOURISM"]


class FoldPackError(RuntimeError):
    """A fail-loud gate inside the fold tripped — never silently degrade."""


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _verify_rule_pack_id() -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, _SEQ16_RULE_PACK_ID_URL)


def _verify_chain(seq15_source: dict[str, Any]) -> str:
    """seq-15 IS signed — verify against the signature's own declaration, not
    just against the source bytes."""
    recomputed = hashlib.sha256(canonicalize_json(seq15_source)).hexdigest()
    if recomputed != _EXPECTED_SEQ15_PAYLOAD_SHA256:
        raise FoldPackError(
            f"seq-15 SOURCE re-hashes to {recomputed}, expected "
            f"{_EXPECTED_SEQ15_PAYLOAD_SHA256} — not the pack this fold was authored against"
        )
    if _SEQ15_SIGNED.exists():
        declared = _load_json(_SEQ15_SIGNED).get("payload_sha256")
        if declared != recomputed:
            raise FoldPackError(
                f"{_SEQ15_SIGNED} declares payload_sha256={declared!r} but the source "
                f"hashes to {recomputed} — signed/source mismatch, refusing to chain"
            )
    else:
        raise FoldPackError(
            f"{_SEQ15_SIGNED} is missing — seq-16 chains to a SIGNED predecessor by "
            "design; refusing to chain to an unverifiable one"
        )
    return recomputed


def _apply_edits(payload: dict[str, Any]) -> None:
    products = [p for p in payload["products"] if p["product_code"] == _EDITED_PRODUCT_CODE]
    if len(products) != 1:
        raise FoldPackError(
            f"expected exactly 1 product {_EDITED_PRODUCT_CODE!r} in seq-15, found {len(products)}"
        )
    product = products[0]
    if product.get("covered_purposes") != _BEFORE:
        raise FoldPackError(
            f"product {_EDITED_PRODUCT_CODE!r} declares "
            f"covered_purposes={product.get('covered_purposes')!r}, expected {_BEFORE!r}"
        )
    product["covered_purposes"] = list(_AFTER)

    by_id = {r["rule_id"]: r for r in payload["rules"]}
    for rule_id in _EDITED_RULE_IDS:
        rule = by_id.get(rule_id)
        if rule is None:
            raise FoldPackError(f"rule {rule_id!r} not found in seq-15 — cannot edit")
        effect = rule.get("effect") or {}
        if effect.get("type") != "SUPPORT":
            raise FoldPackError(
                f"{rule_id!r} has effect type {effect.get('type')!r}; this fold only "
                "widens the purpose coverage of a SUPPORT rule"
            )
        current = effect.get("covered_purposes")
        if current != _BEFORE:
            raise FoldPackError(
                f"{rule_id!r} declares covered_purposes={current!r}, expected {_BEFORE!r} "
                "— seq-15 is not in the state this fold was authored against"
            )
        effect["covered_purposes"] = list(_AFTER)


def _assert_untouched(payload: dict[str, Any], seq15: dict[str, Any]) -> None:
    for key in set(seq15) | set(payload):
        if key in _IDENTITY_KEYS or key in {"rules", "products"}:
            continue
        if _canon(payload.get(key)) != _canon(seq15.get(key)):
            raise FoldPackError(
                f"top-level payload key {key!r} drifted from seq-15 — this fold declares "
                "no edit there (products/source_records untouched)"
            )

    seq15_rules = {r["rule_id"]: r for r in seq15["rules"]}
    new_rules = {r["rule_id"]: r for r in payload["rules"]}
    if set(new_rules) != set(seq15_rules):
        added = sorted(set(new_rules) - set(seq15_rules))
        removed = sorted(set(seq15_rules) - set(new_rules))
        raise FoldPackError(f"membership changed — added={added} removed={removed}")
    if len(payload["rules"]) != len(seq15["rules"]):
        raise FoldPackError("rule count changed; this fold adds and removes nothing")

    for rid, rule in new_rules.items():
        if rid in _EDITED_RULE_IDS:
            continue
        if _canon(rule) != _canon(seq15_rules[rid]):
            raise FoldPackError(f"rule {rid!r} drifted — this fold edits exactly two rules")

    seq15_products = {p["product_code"]: p for p in seq15["products"]}
    new_products = {p["product_code"]: p for p in payload["products"]}
    if set(new_products) != set(seq15_products):
        raise FoldPackError("product membership changed; this fold adds and removes no product")
    for code, product in new_products.items():
        if code == _EDITED_PRODUCT_CODE:
            continue
        if _canon(product) != _canon(seq15_products[code]):
            raise FoldPackError(f"product {code!r} drifted — this fold edits exactly one product")
    for code in _UNTOUCHED_SIBLING_PRODUCTS:
        if new_products[code].get("covered_purposes") != _BEFORE:
            raise FoldPackError(
                f"product {code!r} was widened; it is deliberately out of scope "
                "(review-only, no SUPPORT rule)"
            )


def _assert_edit_is_only_the_purpose_list(payload: dict[str, Any], seq15: dict[str, Any]) -> None:
    """The two edited rules must differ from seq-15 in ONE key and no other:
    ``effect.covered_purposes``. A widened ``when``, a changed reason_code or a
    new stage would all be regulatory changes this fold does not declare."""
    seq15_rules = {r["rule_id"]: r for r in seq15["rules"]}
    new_rules = {r["rule_id"]: r for r in payload["rules"]}
    for rid in _EDITED_RULE_IDS:
        before, after = copy.deepcopy(seq15_rules[rid]), copy.deepcopy(new_rules[rid])
        if after["effect"].get("covered_purposes") != _AFTER:
            raise FoldPackError(f"{rid!r} did not receive {_AFTER!r}")
        before["effect"]["covered_purposes"] = None
        after["effect"]["covered_purposes"] = None
        if _canon(before) != _canon(after):
            raise FoldPackError(
                f"{rid!r} changed somewhere other than effect.covered_purposes — "
                "this fold declares exactly one edited key per rule"
            )

    seq15_products = {p["product_code"]: p for p in seq15["products"]}
    new_products = {p["product_code"]: p for p in payload["products"]}
    before = copy.deepcopy(seq15_products[_EDITED_PRODUCT_CODE])
    after = copy.deepcopy(new_products[_EDITED_PRODUCT_CODE])
    if after.get("covered_purposes") != _AFTER:
        raise FoldPackError(f"product {_EDITED_PRODUCT_CODE!r} did not receive {_AFTER!r}")
    before["covered_purposes"] = None
    after["covered_purposes"] = None
    if _canon(before) != _canon(after):
        raise FoldPackError(
            f"product {_EDITED_PRODUCT_CODE!r} changed somewhere other than "
            "covered_purposes — pricing_key, stay_policy and sponsor_types are untouched"
        )


def _write_pack(payload: dict[str, Any], out_path: Path) -> None:
    if not _PRETTIER_BIN.exists():
        raise FoldPackError(f"prettier binary not found at {_PRETTIER_BIN} — run `npm install`")
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        prefix=f"{out_path.stem}.tmp.", suffix=out_path.suffix, dir=str(out_path.parent)
    )
    tmp_path = Path(tmp_name)
    try:
        with open(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        result = subprocess.run(
            [str(_PRETTIER_BIN), "--write", str(tmp_path)],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise FoldPackError(
                f"prettier --write {tmp_path} failed (rc={result.returncode}):\n"
                f"{result.stdout}\n{result.stderr}"
            )
        tmp_path.replace(out_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def assemble_payload() -> dict[str, Any]:
    seq15 = _load_json(_SEQ15_SOURCE)
    previous_sha = _verify_chain(seq15)
    payload = copy.deepcopy(seq15)

    _apply_edits(payload)

    payload["sequence"] = _SEQ16_SEQUENCE
    payload["version"] = _SEQ16_VERSION
    payload["rule_pack_id"] = str(_verify_rule_pack_id())
    payload["previous_payload_sha256"] = previous_sha
    payload["created_at"] = _SEQ16_CREATED_AT
    payload["created_by"] = _SEQ16_CREATED_BY

    _assert_untouched(payload, seq15)
    _assert_edit_is_only_the_purpose_list(payload, seq15)

    try:
        validated = RulePackPayload.model_validate(payload)
    except Exception as exc:
        raise FoldPackError(
            f"assembled seq-16 payload failed RulePackPayload validation: {exc}"
        ) from exc

    # SCHEMA-VALID IS NOT SEMANTICALLY VALID. `RulePackPayload` accepts a
    # SUPPORT rule claiming a purpose its product does not declare; only
    # `compile_rule_pack` refuses it (SUPPORT_RULE_PURPOSE_NOT_ON_PRODUCT).
    # The first draft of this fold widened the two rules alone, passed the
    # schema check, and produced a pack no consumer could build. The compile
    # gate below is what caught it — it belongs INSIDE the fold, not only in
    # the test, so an uncompilable pack can never reach disk.
    try:
        build_compiled_pack(wrap_as_unsigned_pack(validated), fact_registry=DEFAULT_FACT_REGISTRY)
    except Exception as exc:
        raise FoldPackError(f"assembled seq-16 payload does not compile: {exc}") from exc
    return payload


def main(argv: list[str] | None = None) -> int:
    del argv
    try:
        payload = assemble_payload()
    except FoldPackError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    _write_pack(payload, _SEQ16_OUT)
    print(
        f"wrote {_SEQ16_OUT} — {len(payload['rules'])} rule(s), "
        f"{len(payload['products'])} product(s), {len(payload['source_records'])} source_record(s)"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
