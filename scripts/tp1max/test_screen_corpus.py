"""Schema test for the TP1 input-screen corpus (spec: docs/specs/tp1-input-screen.md).

The screen this corpus drives is not built yet. Until it is, this keeps the corpus honest: every row
parses and reconstructs, carries the fields its kind needs, holds the shape its expected_reason claims,
and the declared limits are exactly the rows the spec names. The corpus file is scanned by the repo's
secret guards, so it must never hold a token-, DSN- or phone-shaped literal: rows build them by concatenation.
"""
import base64
import html
import re
import unicodedata
import urllib.parse
from pathlib import Path

import pytest
import yaml

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "screen_corpus.yaml"
SPEC = HERE.parent.parent / "docs" / "specs" / "tp1-input-screen.md"
DATA = yaml.safe_load(CORPUS.read_text(encoding="utf-8"))
ROWS = DATA["rows"]
ROW_KEYS = {"id", "kind", "category", "text", "construct", "setup", "expected_reason", "source", "limit", "rule"}
SETUP_TYPES = {"regular", "symlink", "linked_directory", "vanish_before_open", "hardlink", "fifo", "socket",
               "directory", "injected_exception", "replace_before_open", "parent_swapped_to_symlink"}
CONTENT_REASONS = {"secret", "phone", "email", "id_number", "crm_name", "pii_other"}
CANONICAL_REASONS = CONTENT_REASONS | {"symlink", "not_regular", "oversized", "empty", "binary", "unsafe_path",
                                       "unreadable", "screen_error", "excluded_path"}


def build(node, plain=False):
    """Materialise a construct; plain=True skips the encodings so the claim check sees the payload."""
    if isinstance(node, str):
        return node
    if "repeat" in node:
        return node["repeat"] * node["count"]
    if "hex" in node:
        return bytes.fromhex(node["hex"])
    op = node["op"]
    if op == "concat":
        return "".join(build(p, plain) for p in node["parts"])
    if op == "bytes_concat":
        return b"".join(x if isinstance(x, bytes) else x.encode("utf-8") for x in (build(p, plain) for p in node["parts"]))
    if op == "base64":
        raw = build(node["value"], plain)
        if plain:
            return raw
        raw = raw.encode("utf-8") if isinstance(raw, str) else raw
        enc = (base64.urlsafe_b64encode if node.get("urlsafe") else base64.b64encode)(raw).decode("ascii")
        w = node.get("wrap", 0)
        return "\n".join(enc[i:i + w] for i in range(0, len(enc), w)) if w else enc
    if op == "unicode_digits":
        zero = int(node["zero_codepoint"], 16)
        return "".join(chr(zero + int(c)) if c.isdigit() else c for c in build(node["value"], plain))
    raise ValueError("unknown construct op " + repr(op))


def materialise(row, plain=False):
    return build(row["construct"], plain) if "construct" in row else row["text"]


def views(value):
    if isinstance(value, bytes):
        value = "".join(ch for ch in value.decode("latin-1") if ch >= " " or ch in "\t\n\r")
    v = unicodedata.normalize("NFKC", value)
    v = re.sub(r"\\(?:u([0-9a-fA-F]{4})|U([0-9a-fA-F]{8})|x([0-9a-fA-F]{2}))",
               lambda m: chr(int(m.group(1) or m.group(2) or m.group(3), 16)), v)
    return {v, urllib.parse.unquote(v), html.unescape(v), html.unescape(urllib.parse.unquote(v))}


SEP = re.compile(r"[\s().\-/‐-― ]")
CLAIM = {
    "secret": lambda v: re.search(
        r"(?im)gh[pousr]_\w{20}|github_pat_|glpat-|npm_\w{20}|[sr]k_live_|sk-|xkeysib-|SG\.\w|hf_\w{20}|xox[abprs]-\d"
        r"|EAA[A-Za-z0-9]{20}|tskey-[a-z]+-[A-Za-z0-9]+-[A-Za-z0-9]{16}|gsk_[A-Za-z0-9]{20}|vendorz_[A-Za-z0-9]{20}"
        r"|AIza|GOCSPX-|ya29\.|AKIA|ASIA|FlyV1|f[mo][12]_|AGE-SECRET-KEY-|whsec_|eyJ\w+\.\w+\.|PRIVATE[ _]KEY(?: BLOCK)?-----"
        r"|webhooks/\d|hooks\.slack\.com/services/T|AccountKey=\w|\d{6,}:AA"
        r"|os\.environ\.setdefault\([^\n]+|\bsetenv(?:\s+|\s*\()\W{0,2}\w*(?:pass|secret|token|key)\w*[^\n]+"
        r"|<password>[^<]+</password>|\bpassword=\"[^\"]+\"|\"auth\"\s*:\s*\"[^\"]+\"|_auth(?:Token)?\s*=\s*\S+"
        r"|(?:pass|pwd|_pw\b|secret|token|api_?key|_key|auth)\w*\W{0,3}\s*[:=]\s*(?:[|>]-?\s+)?\(?\W{0,2}[^\s'\"$\\]"
        r"|--(?:http-|ftp-|proxy-)?pass(?:word|wd)?[=\s]+\S|\blogin\s+\S+\s+password\s+\S|^\s*password\s+\S+\s*$"
        r"|(?<![\w-])-[pu]\s?['\"]?[^\s'\"]|--user\W|://[^\s/:@]*:[^\s@{]+@|\bredis-cli\b[^\n]*\s-a\s?\S|^[^:\s]+:\d+:[^:\s]+:[^:\s]+:\S+$", v),
    "phone": lambda v: re.search(
        r"(?i)(?:phone|telephone|telepon|whatsapp|wa|mobile|cell|hp|telp?|no_hp)\W*(?:\d\D*){7,15}|(?:\+|00)?\d{9,15}",
        SEP.sub("", v)),
    "email": lambda v: re.search(r"(?:\"[^\"]+\"|[^\s@<>\"]+)@[^\s@<>\"]+\.[A-Za-z]{2,}", re.sub(
        r"\s*\.\s*|\s*[\[(]dot[\])]\s*|\s+dot\s+", ".", re.sub(r"\s*[\[(]at[\])]\s*|\s+at\s+", "@", v))),
    "id_number": lambda v: re.search(
        r"(?i)(?:passport|paspor|kitas|kitap|document|dokumen|nomor|national)\w*\W*(?=(?:[A-Z]*\d){6})[A-Z0-9]{6,16}\b"
        r"|(?:nik|ktp|kk|npwp)\W*\d{6,16}\b|(?:card|card_number|cc|pan|kartu|nomor_kartu)\W*(?:\d[ -]*){13,19}"
        r"|(?<!\d)(?:4|5[1-5]|2[2-7]|3[47]|60|62|64|65|35)\d{11,18}(?!\d)"
        r"|(?<!\d)\d{15,16}(?!\d)|\b[A-Z]\d{7}\b"
        r"|\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]){11,30}\b",
        re.sub(r"(?<=\d)[.\- ](?=\d)", "", v)),
    "crm_name": lambda v: re.search(r"[A-Z][a-z]+ [A-Z][a-z]+", v),
    "pii_other": lambda v: re.search(
        r"(?i)(?<![\w])(?:tanggal_lahir|tgl_lahir|dob|birthdate|birth_date|alamat|address|telegram|ig_handle|instagram|social)"
        r"\s*[:=]\s*[\"']?(?!<?(?:YYYY|placeholder))\S|\b(?:B|DK|AB|AD|L|N|KB|DA|PA|PB) \d{1,4} [A-Z]{1,3}\b", v),
}


def test_header_and_row_schema():
    assert DATA["schema"] == "tp1-screen-corpus/v1"
    assert DATA["cap_bytes"] == 512 * 1024
    reasons = set(DATA["reason_enum"])
    assert reasons == CANONICAL_REASONS, reasons ^ CANONICAL_REASONS
    summary = SPEC.read_text(encoding="utf-8").split("The builder prints one summary line", 1)[1].split("Invariant:", 1)[0]
    assert set(re.findall(r'"([a-z_]+)": 0', summary)) == CANONICAL_REASONS | {"short"}
    ids = [r["id"] for r in ROWS]
    assert len(ids) == len(set(ids)), "duplicate row ids"
    for r in ROWS:
        assert set(r) <= ROW_KEYS, (r["id"], set(r) - ROW_KEYS)
        assert re.fullmatch(r"[a-z0-9_]+", r["id"]), r["id"]
        assert r["kind"] in ("guilt", "innocence"), r["id"]
        assert isinstance(r["text"], str) and isinstance(r["category"], str) and r["source"], r["id"]
        if r["kind"] == "guilt":
            assert r.get("expected_reason") in reasons, r["id"]
        else:
            assert "expected_reason" not in r, r["id"]
        if "limit" in r:
            assert r["limit"] is True and r["kind"] == "guilt", r["id"]


@pytest.mark.parametrize("row", ROWS, ids=[r["id"] for r in ROWS])
def test_every_row_reconstructs(row):
    value = materialise(row)
    assert isinstance(value, (str, bytes))
    setup = row.get("setup")
    if setup is None:
        assert value, "a content row must not be empty"
        return
    assert setup["type"] in SETUP_TYPES
    cap, size = DATA["cap_bytes"], setup.get("size")
    if row.get("expected_reason") == "oversized":
        assert size is not None and size > cap
    if row.get("expected_reason") == "empty":
        assert size == 0 and row["text"] == ""
    if size is not None and row["kind"] == "innocence":
        assert 0 < size <= cap
    if "path_construct" in setup:
        assert build(setup["path_construct"])


# A remainder or catch-all row may sit outside the finite claim regexes; its `rule:` phrase pins it instead.
GUILT_CONTENT = [r for r in ROWS if r["kind"] == "guilt" and r.get("expected_reason") in CONTENT_REASONS
                 and not (r.get("limit") and "rule" in r) and r["id"] != "lim_01"]


@pytest.mark.parametrize("row", GUILT_CONTENT, ids=[r["id"] for r in GUILT_CONTENT])
def test_a_guilt_row_holds_the_shape_its_reason_claims(row):
    value = materialise(row, plain=True)
    setup = row.get("setup") or {}
    if "path_construct" in setup:
        value = build(setup["path_construct"]) + "\n" + value
    assert any(CLAIM[row["expected_reason"]](v) for v in views(value)), row["id"]


def _decode(node, value):
    if isinstance(node, dict) and node.get("op") == "base64":
        raw = "".join(value.split())
        dec = (base64.urlsafe_b64decode if node.get("urlsafe") else base64.b64decode)(raw.encode("ascii"))
        inner = node["value"]
        if isinstance(inner, dict) and inner.get("op") == "base64":
            return _decode(inner, dec.decode("ascii"))
        return dec
    return value


ENCODED = [r for r in ROWS if r.get("construct", {}).get("op") == "base64"]


@pytest.mark.parametrize("row", ENCODED, ids=[r["id"] for r in ENCODED])
def test_an_encoded_row_decodes_back_to_its_payload(row):
    payload = build(row["construct"], plain=True)
    payload = payload.encode("utf-8") if isinstance(payload, str) else payload
    assert _decode(row["construct"], materialise(row)) == payload


def test_the_claim_check_refuses_operand_free_prose():
    for prose in ("Set the password in the vault; never inline the token.",
                  "Authorization headers carry a Bearer token.", "The api_key field is required."):
        assert not CLAIM["secret"](prose), prose


def test_receipt_coverage_and_declared_limits_match_the_spec():
    by_source = {}
    for r in ROWS:
        by_source[r["source"]] = by_source.get(r["source"], 0) + 1
    assert by_source.get("gate-7927:B1") == 31
    assert by_source.get("gate-7971:B1") == 16
    assert by_source.get("gate-7971-r2:B1-r2") == 12
    assert by_source.get("gate-7971-r2:N1") == 6
    assert by_source.get("gate-7988") == 33
    assert by_source.get("gate-7988-r2") == 36
    assert sum(1 for r in ROWS if r["kind"] == "innocence" and r["category"] != "structural") >= 30
    spec = SPEC.read_text(encoding="utf-8")
    limits = {r["id"] for r in ROWS if r.get("limit")}
    named = set(re.findall(r"`limit:([a-z0-9_]+)`", spec))
    assert limits and limits == named, (sorted(limits), sorted(named))
    assert len(limits) == 21, len(limits)
    assert len(ROWS) == 370, len(ROWS)


ADOPTED = {"lim_pan": "id_number", "lim_iban": "id_number", "lim_01": "pii_other",
           "rem_pii_other": "pii_other", "rem_pii_other_address": "pii_other",
           "rem_pii_other_messaging": "pii_other", "rem_pii_other_social": "pii_other",
           "rem_pii_other_plate": "pii_other", "adopt_pan_hyphen": "id_number",
           "adopt_pan_label_contiguous": "id_number", "adopt_pan_unlabelled_grouped": "id_number",
           "adopt_pan_amex_grouped": "id_number", "adopt_pan_19_grouped": "id_number",
           "adopt_iban_unspaced": "id_number", "adopt_iban_lowercase": "id_number"}
ADOPTED_INNOCENCE = {"innocent_15", "adopt_innocent_pan", "adopt_innocent_iban", "adopt_innocent_dob",
                     "adopt_innocent_timestamp", "adopt_innocent_zero_pan", "adopt_innocent_ip_address",
                     "adopt_innocent_mac_address", "adopt_innocent_bind_address", "adopt_innocent_decorator",
                     "adopt_innocent_npm_scope", "adopt_innocent_plate_prose"}


def test_the_adopted_pii_scopes_are_asserted_guilt_with_an_innocence_row_each():
    by_id = {r["id"]: r for r in ROWS}
    for rid, reason in ADOPTED.items():
        row = by_id[rid]
        assert row["kind"] == "guilt" and "limit" not in row and row["expected_reason"] == reason, rid
    assert len(ADOPTED) == 15 and len(ADOPTED_INNOCENCE) == 12
    assert all(by_id[i]["kind"] == "innocence" for i in ADOPTED_INNOCENCE)


PAN_GUILT = {"lim_pan", "rem_card_label", "adopt_pan_hyphen", "adopt_pan_label_contiguous",
             "adopt_pan_unlabelled_grouped", "adopt_pan_amex_grouped", "adopt_pan_19_grouped"}
IBAN_GUILT = {"lim_iban", "adopt_iban_unspaced", "adopt_iban_lowercase"}


def _digits(row):
    return "".join(re.findall(r"\d", materialise(row)))


def _luhn(value):
    digits = [int(c) for c in value]
    total = sum((n * 2 - 9 if n > 4 else n * 2) if (len(digits) - i) % 2 == 0 else n
                for i, n in enumerate(digits))
    return total % 10 == 0


def _major_card_issuer(value):
    prefix2, prefix3, prefix4, prefix6 = (int(value[:n]) for n in (2, 3, 4, 6))
    return (value.startswith("4") or 51 <= prefix2 <= 55 or 2221 <= prefix4 <= 2720
            or prefix2 in {34, 37, 62, 65} or prefix4 == 6011 or 622126 <= prefix6 <= 622925
            or 644 <= prefix3 <= 649 or 3528 <= prefix4 <= 3589)


def _iban(row):
    value = materialise(row)
    match = re.search(r"(?i)\b([A-Z]{2}\d{2}(?: ?[A-Z0-9]){11,30})\b", value)
    assert match, row["id"]
    return match.group(1).replace(" ", "").upper()


def _mod97(iban):
    rearranged = iban[4:] + iban[:4]
    numeric = "".join(str(ord(c) - 55) if c.isalpha() else c for c in rearranged)
    return int(numeric) % 97 == 1


def test_pan_and_iban_checksum_contracts_and_innocent_exclusions():
    by_id = {r["id"]: r for r in ROWS}
    assert all(_luhn(_digits(by_id[rid])) for rid in PAN_GUILT)
    assert all(_major_card_issuer(_digits(by_id[rid])) for rid in PAN_GUILT)
    assert not _luhn(_digits(by_id["adopt_innocent_pan"]))
    assert all(_luhn(_digits(by_id[rid])) for rid in
               {"innocent_15", "adopt_innocent_timestamp", "adopt_innocent_zero_pan"})
    assert not any(_major_card_issuer(_digits(by_id[rid])) for rid in
                   {"innocent_15", "adopt_innocent_timestamp", "adopt_innocent_zero_pan"})
    assert all(_mod97(_iban(by_id[rid])) for rid in IBAN_GUILT)
    assert not _mod97(_iban(by_id["adopt_innocent_iban"]))


def test_the_adoption_decision_and_financial_id_grammars_are_normative():
    spec = " ".join(SPEC.read_text(encoding="utf-8").split())
    assert "8. Decision (2026-10-10): items 6 and 7 were adopted" in spec
    assert "A PAN is 13–19 digits, passes the Luhn check, has a major-network issuer prefix" in spec
    assert "An IBAN is two ASCII letters, two check digits and 11–30 ASCII letters or digits" in spec
    assert "`card_number`, `cc`, `pan`, `kartu`, `nomor_kartu` and `iban`" in spec
    assert "`dob`, `birthdate`, `birth_date`, `alamat`, `address`, `telegram`, `ig_handle`, `instagram` and `social`" in spec
    assert "personal data outside this label list and the examples above is GUILTY rather than a declared remainder" in spec


def test_every_rule_phrase_is_in_the_spec_and_every_remainder_carries_one():
    spec = " ".join(SPEC.read_text(encoding="utf-8").split())
    not_once = [(r["id"], spec.count(" ".join(r["rule"].split()))) for r in ROWS
                if "rule" in r and spec.count(" ".join(r["rule"].split())) != 1]
    assert not not_once, not_once
    unpinned = [r["id"] for r in ROWS if r.get("limit") and r["source"] == "gate-7988-r2" and "rule" not in r]
    assert not unpinned, unpinned


def test_the_vocabulary_table_declares_an_outside_outcome_for_each_of_its_21_vocabularies():
    section = SPEC.read_text(encoding="utf-8").split("## Closed vocabularies and their remainders", 1)[1].split("\n## ", 1)[0]
    table = [line for line in section.splitlines() if line.startswith("| ") and not line.startswith(("| Vocabulary", "| ---"))]
    limits = {r["id"] for r in ROWS if r.get("limit")}
    outcomes = [line.split("|")[3] for line in table]
    named = [set(re.findall(r"`([a-z0-9_]+)`", outcome)) for outcome in outcomes]
    assert len(table) == 21, len(table)
    assert all((ids and ids <= limits | {"pii_other"}) or "GUILTY" in outcome or "innocent" in outcome
               for ids, outcome in zip(named, outcomes)), list(zip(named, outcomes))


BARE_TOKEN_FAMILY = re.compile(
    r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_\w{20,}|xkeysib-\w{20,}|AKIA[0-9A-Z]{16}|AIza[\w-]{30,}"
    r"|-----BEGIN[A-Z ]*PRIVATE KEY(?: BLOCK)?-----|\d{8,10}:AA[\w-]{30,}|sk_live_\w{20,}|SG\.[\w-]{20,}\.[\w-]{20,}"
    r"|hf_\w{30,}|(?<![\w-])eyJ[\w-]{10,8192}\.[\w-]{10,8192}\.[\w-]{10,8192}"
    r"|npm_\w{30,}|glpat-\w{20,}|xox[abprs]-\d{6,}|AGE-SECRET-KEY-1\w{20,}|whsec_\w{20,}|GOCSPX-\w{20,}"
    r"|sk-proj-\w{20,}|f[mo][12]_\w{20,}|AccountKey=[\w+/]{20,}|hooks\.slack\.com/services/T\w+/B|webhooks/\d{10,}/"
    r"|EAA[A-Za-z0-9]{20,}|tskey-[\w-]{20,}|gsk_[A-Za-z0-9]{20,}|vendorz_[A-Za-z0-9]{20,}", re.I)

ID_MOBILE = re.compile(r"(?:\+?62|\b0)8\d{2}[ -]?\d{3,4}[ -]?\d{3,4}")

TOKEN_SHAPED = re.compile(
    BARE_TOKEN_FAMILY.pattern
    + r"|://[^\s/:@\"'{}$]+:[^\s@\"'{}$]{2,}@"
    + "|" + ID_MOBILE.pattern + r"|\+\d{1,3}(?:[ .-]?\d{2,4}){3}", re.I)


@pytest.mark.parametrize("row", [r for r in ROWS if r["kind"] == "innocence"],
                         ids=[r["id"] for r in ROWS if r["kind"] == "innocence"])
def test_materialised_innocence_matches_no_credential_family(row):
    value = materialise(row)
    value = value.decode("latin-1") if isinstance(value, bytes) else value
    assert BARE_TOKEN_FAMILY.search(value) is None, row["id"]
    assert ID_MOBILE.search(value) is None, row["id"]


def test_the_corpus_file_holds_no_token_dsn_or_phone_shaped_literal():
    raw = CORPUS.read_text(encoding="utf-8")
    assert TOKEN_SHAPED.findall(raw) == []
    hits = [r["id"] for r in ROWS if r["kind"] == "guilt" and "construct" in r
            and isinstance(materialise(r), str) and TOKEN_SHAPED.search(materialise(r))]
    assert len(hits) >= 30, hits
