#!/usr/bin/env python3
"""F4 — the OSS refresh loop: re-ask OSS about every licensing gap, notice when a
scope is published, propose it. Never write it.

WHY THIS EXISTS. The licensing axis of the scoreboard is honest but not complete:
~219 codes carry no OSS-2025 risk rows (declared gaps + PP28 vintage-pending),
because OSS answered 404 for them when the snapshot was taken. Those gaps close
only when OSS publishes the scope (kbli-navigator corner §5.5 F4). Nobody looks
by hand, so this loop does: once a week it re-fetches exactly the gap
population and reports what moved.

THE POPULATION IS COMPUTED, NEVER LISTED. Gap codes = every code the scoreboard
(`kbli_coverage_scoreboard.build_scoreboard`) does NOT count as holding the
strong licensing state. A hand list would rot the first time a cure lands.

WHAT IT NEVER DOES. It never writes the canonical, a mirror, or any runtime
store. A published scope becomes a cure SPEC under cure_specs/ carrying the
rows the L2 transform itself would write (`build_kbli_l2_oss_risk.
parse_per_skala` + `merge_per_skala`, imported, not re-derived) and the
`premises` old/new sha256 pins the hardened compilers judge. Codes quarantined
by a later cure (`per_skala_disputed_*`) are routed to their quarantine owner,
never to the L2 transform. A gap that stays 404 stays an honest gap.

A RUN THAT SAW NOTHING IS NOT A CLEAN RUN (superscar #2). Two positive controls
(codes that DO hold OSS rows) are fetched first: if the endpoint cannot say yes
for them, 219 × "still 404" means nothing and the run exits 4. Measured
2026-09-22: OSS serves this endpoint with or without `user_key`, so an auth
failure is recognised by the 401/403 it would return, never guessed from the
variable being unset.

USAGE
    python3 scripts/kbli_filiera/oss_refresh_loop.py                 # dry-run: fetch + print, write nothing
    python3 scripts/kbli_filiera/oss_refresh_loop.py --only 64995,65123
    python3 scripts/kbli_filiera/oss_refresh_loop.py --apply         # also write report (+ cure spec if any)
    python3 scripts/kbli_filiera/oss_refresh_loop.py --apply --out-root ~/nuzantara-vault-evidence/oss-refresh

OUTPUTS (--apply, relative to --out-root, default the repo root)
    data/kbli-filiera/oss-refresh/<UTC date>.json    machine report
    data/kbli-filiera/oss-refresh/<UTC date>.md      human summary
    scripts/kbli_filiera/cure_specs/oss_refresh_<UTC date>.json   only when a scope was proposed

EXIT CODES
    0  ran, nothing new
    1  new scopes proposed (published / changed vs canonical)
    2  usage error (e.g. --only names a code outside the gap population)
    4  cannot verify: canonical unreadable, empty population, no trustworthy
       answer, positive control failed, or OSS refused auth
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import importlib.util
import json
import os
import re
import ssl
import sys
import tempfile
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable, Protocol

_FILIERA_DIR = Path(__file__).resolve().parent
if str(_FILIERA_DIR) not in sys.path:
    sys.path.insert(0, str(_FILIERA_DIR))

import _hardened_cure_io as H  # noqa: E402
import vault_common as common  # noqa: E402
import vault_to_risk_jsonl as ground_truth  # noqa: E402
from _coverage_basis import AXES, CODE_FIELD  # noqa: E402
from kbli_coverage_scoreboard import build_scoreboard, load_records  # noqa: E402

REPO_ROOT = _FILIERA_DIR.parents[1]
DEFAULT_CANONICAL = REPO_ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json"
DEFAULT_GROUND_TRUTH = REPO_ROOT / "data/source_documents/KBLI_2025_OSS_GROUND_TRUTH.json"
REPORT_REL = Path("data/kbli-filiera/oss-refresh")
SPEC_REL = Path("scripts/kbli_filiera/cure_specs")
L2_TRANSFORM = REPO_ROOT / "scripts/build_kbli_l2_oss_risk.py"

OSS_HOST = "gw.oss.go.id"
SCOPE_PATH = "/v2/portal/kbli/ruang-lingkup/"
ENDPOINT = f"https://{OSS_HOST}{SCOPE_PATH}<uuid>"
USER_KEY_ENV = "OSS_RBA_USER_KEY"
QUARANTINE_PREFIX = "per_skala_disputed"
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
# A header value http.client will send without raising — its ValueError would
# quote the value, i.e. print the key (Codex red-team finding 2).
USER_KEY_RE = re.compile(r"[\x21-\x7e]{1,256}")

# Sizing, measured from Mini and M5 on 2026-09-22: first request ~4 s (TLS),
# then 0.05-0.95 s per answer on the reused connection. 3 req/s is the pace
# vault_fetch_oss.py already uses against the same host. 221 fetches then take
# ~2-4 min; the deadline leaves the wrapper's 900 s timeout a wide margin and
# turns a slow OSS into "deferred" codes in the report instead of a kill.
RATE_S = 1.0 / 3.0
DEFAULT_DEADLINE_S = 600.0
REQUEST_TIMEOUT_S = 20.0
RETRIES = 3
BACKOFF_S = 1.5
MAX_RETRY_AFTER_S = 30.0
CONTROL_COUNT = 2

EXIT_NOTHING_NEW = 0
EXIT_PROPOSED = 1
EXIT_USAGE = 2
EXIT_CANNOT_VERIFY = 4

STILL_404 = "still_404"
PUBLISHED = "published"
CHANGED = "changed"
UNCHANGED = "unchanged"
MALFORMED = "malformed"
FETCH_ERROR = "fetch_error"
AUTH_FAILED = "auth_failed"
DEFERRED = "deferred"
CLASSES = (STILL_404, PUBLISHED, CHANGED, UNCHANGED, MALFORMED, FETCH_ERROR, AUTH_FAILED, DEFERRED)
PROPOSAL_CLASSES = frozenset({PUBLISHED, CHANGED})
# An answer the loop can vouch for. `malformed` is an HTTP answer but not a
# trustworthy one: an HTML maintenance page served as 200 on every code must
# end as "cannot verify", never as "nothing new".
TRUSTED_CLASSES = frozenset({STILL_404, PUBLISHED, CHANGED, UNCHANGED})
CONTROL_PASS = frozenset({UNCHANGED, CHANGED})


def _load_l2_transform():
    """The L2 transform lives outside any package; load it by path so no other
    `scripts` package on sys.path can shadow it."""
    spec = importlib.util.spec_from_file_location("_kbli_l2_oss_risk_transform", L2_TRANSFORM)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load the L2 transform from {L2_TRANSFORM}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


L2 = _load_l2_transform()


# --------------------------------------------------------------------------- fetch


@dataclass
class Answer:
    status: int  # HTTP status; 0 = no HTTP answer at all
    body: bytes = b""
    error: str | None = None
    attempts: int = 1


class ScopeFetcher(Protocol):
    def get(self, uuid: str) -> Answer: ...

    def close(self) -> None: ...


class OssSession:
    """One persistent keep-alive HTTPS connection for the whole run (superscar
    #8): a flap drops the socket, the next attempt reconnects, the run goes on.
    http.client never consults the system proxy, which is the urllib trap
    vault_common works around. 404 and 401/403 are terminal (P3: a 404 is a
    signal, never a transient to hammer); 429/5xx/network errors are retried
    with linear backoff, honouring a bounded Retry-After."""

    TERMINAL = frozenset({404, 401, 403})

    def __init__(
        self,
        user_key: str = "",
        *,
        timeout: float = REQUEST_TIMEOUT_S,
        retries: int = RETRIES,
        backoff: float = BACKOFF_S,
        sleep: Callable[[float], None] = time.sleep,
        connection_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._user_key = user_key
        self._retries = retries
        self._backoff = backoff
        self._sleep = sleep
        self._factory = connection_factory or (
            lambda: http.client.HTTPSConnection(OSS_HOST, timeout=timeout, context=ssl.create_default_context())
        )
        self._conn = None

    def _reset(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except OSError:
                pass
        self._conn = None

    def close(self) -> None:
        self._reset()

    def get(self, uuid: str) -> Answer:
        headers = {**common.DEFAULT_HEADERS, "accept": "application/json", "Connection": "keep-alive"}
        if self._user_key:
            headers["user_key"] = self._user_key
        last = Answer(0, error="exhausted", attempts=self._retries)
        for attempt in range(1, self._retries + 1):
            retry_after = None
            try:
                if self._conn is None:
                    self._conn = self._factory()
                self._conn.request("GET", SCOPE_PATH + uuid, headers=headers)
                response = self._conn.getresponse()
                body = response.read()
                status = response.status
                retry_after = response.getheader("Retry-After")
                if (response.getheader("Connection") or "").lower() == "close":
                    self._reset()
            except (http.client.HTTPException, OSError) as exc:
                self._reset()
                last = Answer(0, error=f"{type(exc).__name__}: {exc}", attempts=attempt)
            except ValueError as exc:
                # an unsendable header: the message would quote its value, so it is not echoed
                self._reset()
                return Answer(0, error=f"{type(exc).__name__}: request header refused (value not printed)",
                              attempts=attempt)
            else:
                if status == 200 or status in self.TERMINAL:
                    return Answer(status, body, attempts=attempt)
                last = Answer(status, error=f"HTTP {status}", attempts=attempt)
            if attempt < self._retries:
                self._sleep(_retry_delay(retry_after, self._backoff * attempt))
        return last


def _retry_delay(retry_after: str | None, default: float, now: Callable[[], datetime] | None = None) -> float:
    """Retry-After as delta-seconds or HTTP-date (RFC 9110 §10.2.3), capped."""
    if not retry_after:
        return default
    try:
        seconds = float(retry_after)
    except ValueError:
        try:
            when = parsedate_to_datetime(retry_after)
        except (TypeError, ValueError):
            return default
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        seconds = (when - (now or (lambda: datetime.now(timezone.utc)))()).total_seconds()
    return min(max(seconds, 0.0), MAX_RETRY_AFTER_S)


# ------------------------------------------------------------------ classification


def payload_identity_mismatch(payload: dict, code: str, uuid: str) -> str | None:
    """Pure. None when every scope names the code that was asked for.

    `success:true` is the payload vouching for itself; it says nothing about
    WHICH code it describes. Measured 2026-09-22: every scope carries
    `Kbli.id` == the requested uuid and every risk row a `kode` of the form
    `<code>-NN-NN`, so a scope served for the wrong code (a remapped uuid, a
    cache in front of the gateway) is detectable, and must never become a
    proposal for the code we asked about."""
    for scope in payload["data"]:
        kbli = scope.get("Kbli") if isinstance(scope, dict) else None
        scope_uuid = kbli.get("id") if isinstance(kbli, dict) else None
        if scope_uuid != uuid:
            return f"scope names uuid {scope_uuid!r}, asked {uuid}"
        for row in scope.get("KbliResikos") or []:
            kode = row.get("kode") if isinstance(row, dict) else None
            if kode is not None and not str(kode).startswith(f"{code}-"):
                return f"risk row kode {kode!r} is not code {code}"
    return None


def incomplete_risk_row(payload: dict) -> str | None:
    """Pure. parse_per_skala silently drops a row with no scale and keeps one
    with no risk as null; either would turn into a proposal that is not what
    OSS published (Codex red-team finding 4). Every row must name both."""
    for si, scope in enumerate(payload["data"]):
        rows = scope.get("KbliResikos")
        if not isinstance(rows, list):
            return f"scope {si} has no KbliResikos list"
        for ri, row in enumerate(rows):
            if not isinstance(row, dict):
                return f"scope {si} risk row {ri} is not an object"
            for field in ("SkalaUsaha", "Resiko"):
                value = L2.loc(row.get(field))
                if not (isinstance(value, str) and value.strip()):
                    return f"scope {si} risk row {ri} has no {field}"
    return None


def classify_answer(answer: Answer, current_rows: list, code: str, uuid: str,
                    gap: bool = True) -> tuple[str, str, list | None]:
    """Pure. (class, reason, proposed per_skala or None).

    The proposal is the per_skala the L2 transform would write for this code
    today: its own parser, then its own merge policy against the canonical rows
    (for an empty gap that merge only applies the fresh-row jangka rule)."""
    if answer.status in OssSession.TERMINAL - {404}:
        return AUTH_FAILED, f"HTTP {answer.status}", None
    if answer.status == 404:
        return STILL_404, "HTTP 404", None
    if answer.status != 200:
        return FETCH_ERROR, answer.error or f"HTTP {answer.status}", None
    try:
        payload = json.loads(answer.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return MALFORMED, "HTTP 200 body is not JSON", None
    if not isinstance(payload, dict):
        return MALFORMED, "HTTP 200 payload is not an object", None
    if payload.get("success") is not True:
        return MALFORMED, "HTTP 200 without success:true", None
    if not isinstance(payload.get("data"), list):
        return MALFORMED, "HTTP 200 data is not a list", None
    mismatch = payload_identity_mismatch(payload, code, uuid)
    if mismatch:
        return MALFORMED, f"payload is not this code's: {mismatch}", None
    incomplete = incomplete_risk_row(payload)
    if incomplete:
        return MALFORMED, incomplete, None
    try:
        parsed = L2.parse_per_skala(payload)
    except (AttributeError, TypeError, KeyError) as exc:
        return MALFORMED, f"scope rows unparseable: {type(exc).__name__}", None
    if not parsed:
        return MALFORMED, "published scope carries no risk rows", None
    proposed = L2.merge_per_skala(current_rows, parsed)
    if not current_rows:
        return PUBLISHED, f"{len(proposed)} risk row(s) published", proposed
    if _row_multiset(proposed) == _row_multiset(current_rows):
        if gap:
            # Same rows, but the gap code does not carry them AS OSS rows: the
            # news is the provenance, and without a proposal the code would sit
            # in the gap population forever (Codex red-team finding 5).
            return PUBLISHED, "OSS now publishes the canonical rows: provenance moves to OSS", proposed
        return UNCHANGED, "OSS rows equal the canonical rows", None
    return CHANGED, f"{len(proposed)} OSS risk row(s) vs {len(current_rows)} canonical", proposed


def _row_multiset(rows: list) -> list[str]:
    """Order-blind fingerprint of a per_skala. Measured 2026-09-22: OSS returns
    the same `kewenangan` set in a different order from one fetch to the next
    (96900), and an order is not a published change."""
    def canonical(row: Any) -> str:
        if isinstance(row, dict):
            row = {k: sorted(v) if isinstance(v, list) and all(isinstance(x, str) for x in v) else v
                   for k, v in row.items()}
        return json.dumps(row, sort_keys=True, ensure_ascii=False)
    return sorted(canonical(row) for row in rows)


def decide_exit(counts: Counter, controls_ok: bool) -> tuple[int, str]:
    """Pure. The verdict order matters: an auth refusal or a blind endpoint
    outranks anything the remaining answers seem to say, and "nothing new" is
    only said when EVERY asked code got a trustworthy answer — a code left
    deferred or in error may be exactly the one OSS just published."""
    asked = sum(counts.values())
    if asked == 0:
        return EXIT_CANNOT_VERIFY, "empty population: nothing was asked"
    if counts[AUTH_FAILED]:
        return EXIT_CANNOT_VERIFY, f"OSS refused auth on {counts[AUTH_FAILED]} code(s) (set {USER_KEY_ENV})"
    if not controls_ok:
        return EXIT_CANNOT_VERIFY, "positive control failed: the endpoint could not say yes for a sourced code"
    if not sum(counts[k] for k in TRUSTED_CLASSES):
        return EXIT_CANNOT_VERIFY, "fetch empty: no code got a trustworthy answer"
    proposed = sum(counts[k] for k in PROPOSAL_CLASSES)
    if proposed:
        return EXIT_PROPOSED, f"{proposed} new OSS scope(s) proposed"
    untrusted = asked - sum(counts[k] for k in TRUSTED_CLASSES)
    if untrusted:
        return EXIT_CANNOT_VERIFY, f"partial: {untrusted} of {asked} code(s) got no trustworthy answer"
    return EXIT_NOTHING_NEW, "nothing new"


# ------------------------------------------------------------------- population


def gap_population(records: list[dict]) -> tuple[list[dict], list[str]]:
    """(gap records ascending by code, sorted strong codes). Derived from the
    scoreboard's own computation — the loop and the scoreboard can never
    disagree on which codes are gaps."""
    licensing = build_scoreboard(records)["axes"]["licensing"]
    strong = set(licensing["strong_codes"])
    gaps = sorted((r for r in records if str(r.get(CODE_FIELD)) not in strong), key=lambda r: str(r.get(CODE_FIELD)))
    return gaps, sorted(strong)


def pick_controls(strong_codes: list[str], count: int = CONTROL_COUNT) -> list[str]:
    """Deterministic positive controls: the lowest and highest sourced codes."""
    if not strong_codes:
        return []
    picks = [strong_codes[0], strong_codes[-1]][:count]
    return list(dict.fromkeys(picks))


def licensing_state(record: dict) -> str:
    return AXES["licensing"][0](record)


def quarantine_keys(record: dict) -> list[str]:
    return sorted(k for k in record if k.startswith(QUARANTINE_PREFIX))


# ------------------------------------------------------------------------- run


def run_loop(
    targets: list[dict],
    controls: list[dict],
    uuids: dict[str, str],
    session: ScopeFetcher,
    *,
    deadline_s: float = DEFAULT_DEADLINE_S,
    rate_s: float = RATE_S,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = lambda message: None,
) -> tuple[list[dict], list[dict]]:
    """Controls first, then targets in code order. Codes the deadline did not
    reach are `deferred`: asked, not fetched, and counted as such."""
    start = clock()
    first = True

    def probe(record: dict, gap: bool) -> dict:
        nonlocal first
        code = str(record.get(CODE_FIELD))
        entry = {
            "code": code,
            "uuid": uuids.get(code),
            "licensing_state": licensing_state(record),
            "quarantined_by": quarantine_keys(record),
        }
        uuid = uuids.get(code) or ""
        if not UUID_RE.fullmatch(uuid):
            return {**entry, "class": FETCH_ERROR, "reason": "no valid OSS uuid in the ground truth",
                    "http_status": None, "attempts": 0, "body_sha256": None, "rows": 0, "_proposed": None}
        if clock() - start >= deadline_s:
            return {**entry, "class": DEFERRED, "reason": f"deadline {deadline_s:.0f}s reached before fetch",
                    "http_status": None, "attempts": 0, "body_sha256": None, "rows": 0, "_proposed": None}
        if not first:
            sleep(rate_s)
        first = False
        answer = session.get(uuid)
        klass, reason, proposed = classify_answer(answer, list(record.get("per_skala") or []), code, uuid, gap)
        log(f"{code} {klass} {reason}")
        return {
            **entry,
            "class": klass,
            "reason": reason,
            "http_status": answer.status or None,
            "attempts": answer.attempts,
            "body_sha256": hashlib.sha256(answer.body).hexdigest() if answer.body else None,
            "rows": len(proposed) if proposed else 0,
            "_proposed": proposed,
        }

    control_results = [probe(record, gap=False) for record in controls]
    target_results = [probe(record, gap=True) for record in targets]
    return control_results, target_results


# ---------------------------------------------------------------------- outputs


class OutputRefused(RuntimeError):
    pass


def write_contained(out_root: Path, path: Path, text: str) -> None:
    """Write `text` to `path` (built under `out_root`) through no symlink, via
    an exclusive temp file + os.replace — so neither a symlinked directory nor
    a pre-planted temp name can redirect the write onto the canonical (Codex
    red-team finding 1). `out_root` itself may be a symlink: the operator
    chose it. Every directory BELOW `out_root` is refused one level at a time
    BEFORE it is created: `path.parent.mkdir(parents=True)` alone would let
    pathlib's own parent-recursion materialise real directories at a
    symlinked intermediate's (even a dangling one's) destination first, and
    only then would the walk-up below refuse it (D1)."""
    if path.is_symlink():
        raise OutputRefused(f"{path} is a symlink")
    out_root.mkdir(parents=True, exist_ok=True)
    cursor = out_root
    for part in path.parent.relative_to(out_root).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise OutputRefused(f"{cursor} is a symlink")
        cursor.mkdir(exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _write_or_refuse(out_root: Path, written: list[Path], path: Path, text: str) -> Exception | None:
    """`write_contained`, but never let a write escape as an uncaught
    traceback: `OutputRefused` is the loop's own guard, but a plain
    `OSError` (permission denied, ENOSPC, a vanished directory) is exactly
    as fatal to the output and must be caught the same way (Codex M2) — an
    uncaught exception exits the interpreter with 1, the SAME code as
    "new scopes proposed". On success `path` is recorded in `written` so a
    LATER failure in this run can undo it (M3); on failure nothing is
    recorded (`write_contained` never leaves a partial file of its own) and
    the exception is returned, never raised, for the caller to report
    without ever repeating a secret."""
    try:
        write_contained(out_root, path, text)
    except (OutputRefused, OSError) as exc:
        return exc
    written.append(path)
    return None


def _public(entry: dict) -> dict:
    return {k: v for k, v in entry.items() if not k.startswith("_")}


def build_cure_spec(date: str, results: list[dict], records_by_code: dict[str, dict], canonical_sha256: str) -> dict | None:
    """Pure. None when nothing was proposed — an empty spec file would read as
    work to do."""
    codes: dict[str, Any] = {}
    for entry in results:
        if entry["class"] not in PROPOSAL_CLASSES:
            continue
        record = records_by_code[entry["code"]]
        proposed = entry["_proposed"]
        quarantined = entry["quarantined_by"]
        item = {
            "class": entry["class"],
            "uuid": entry["uuid"],
            "licensing_state": entry["licensing_state"],
            "route": "quarantine_owner" if quarantined else "l2_transform",
            "quarantined_by": quarantined,
            "body_sha256": entry["body_sha256"],
            "besar_verdict": L2.besar_block_verdict(proposed),
        }
        if quarantined:
            # Evidence for the quarantine owner, deliberately NOT applyable: no
            # per_skala / set / drop_keys a compiler could write by mistake.
            codes[entry["code"]] = {**item, "record_sha256": H.sha256_of(record), "oss_rows": proposed}
            continue
        codes[entry["code"]] = {
            **item,
            "premises": {
                "per_skala": {"old_sha256": H.sha256_of(record.get("per_skala")), "new_sha256": H.sha256_of(proposed)},
                "_l2_source": {"old_sha256": H.sha256_of(record.get("_l2_source")), "new_sha256": H.sha256_of(L2.L2_SOURCE)},
                "_l2_status": {"old_sha256": H.sha256_of(record.get("_l2_status")), "new_sha256": H.sha256_of(None)},
                "absent_probes": {"old_sha256": H.sha256_of(record.get("absent_probes")), "new_sha256": H.sha256_of(None)},
            },
            "per_skala": proposed,
            "set": {"_l2_source": L2.L2_SOURCE},
            "drop_keys": ["_l2_status", "absent_probes"],
        }
    if not codes:
        return None
    return {
        "_generated_by": "scripts/kbli_filiera/oss_refresh_loop.py",
        "_doc": (
            "PROPOSAL, not an adjudication. OSS published a ruang-lingkup scope for these licensing-gap "
            "codes; `per_skala` is what scripts/build_kbli_l2_oss_risk.py would write for each "
            "(parse_per_skala + merge_per_skala). Apply only through a hardened compiler that judges "
            "`premises` with _hardened_cure_io.judge_patch. route=quarantine_owner: the code's per_skala "
            "is cure-owned (per_skala_disputed_*), so its entry carries only `oss_rows` + `record_sha256` "
            "as evidence for that owner and nothing applyable. l4_bali is not proposed: `besar_verdict` "
            "is informational."
        ),
        "version": f"oss-refresh-{date}",
        "fetched": date,
        "source": {"endpoint": ENDPOINT, "l2_source": L2.L2_SOURCE},
        "canonical_sha256": canonical_sha256,
        "codes": codes,
    }


def build_report(
    *,
    date: str,
    generated_at: str,
    canonical: dict,
    population: list[dict],
    control_results: list[dict],
    target_results: list[dict],
    exit_code: int,
    verdict: str,
    cure_spec_rel: str | None,
    user_key_present: bool,
) -> dict:
    """Pure."""
    counts = Counter(entry["class"] for entry in target_results)
    # `fetched` counts codes that got an HTTP answer — not `fetch_error` (no
    # answer, or one not worth trusting) and not `deferred` (no attempt at
    # all). A run can retry a code 3 times and still never get an answer;
    # counting those attempts as "fetched" let a report say "fetched 219/219"
    # over 218 fetch_errors (D6). `attempted` keeps the old attempts-made
    # count, for whoever still wants it.
    fetched = sum(1 for entry in target_results if entry["class"] not in (DEFERRED, FETCH_ERROR))
    attempted = sum(1 for entry in target_results if entry["class"] != DEFERRED and entry["attempts"])
    return {
        "schema": "kbli-oss-refresh/v1",
        "date": date,
        "generated_at": generated_at,
        "source": {"endpoint": ENDPOINT, "user_key": "present" if user_key_present else "absent"},
        "canonical": canonical,
        "population": {
            "derivation": "kbli_coverage_scoreboard.build_scoreboard: licensing codes not holding a strong state",
            "count": len(population),
            "by_state": dict(sorted(Counter(licensing_state(r) for r in population).items())),
            "quarantined": sum(1 for r in population if quarantine_keys(r)),
        },
        "coverage": {
            "asked": len(target_results),
            "fetched": fetched,
            "attempted": attempted,
            "trusted_answers": sum(counts[k] for k in TRUSTED_CLASSES),
            "errors": counts[FETCH_ERROR] + counts[AUTH_FAILED] + counts[MALFORMED],
            "deferred": counts[DEFERRED],
        },
        "controls": [_public(entry) for entry in control_results],
        "counts": {klass: counts[klass] for klass in CLASSES},
        "exit_code": exit_code,
        "verdict": verdict,
        "cure_spec": cure_spec_rel,
        "codes": [_public(entry) for entry in target_results],
    }


def render_summary(report: dict, *, dry_run: bool = False) -> str:
    cov = report["coverage"]
    pop = report["population"]
    states = " · ".join(f"{state} {n}" for state, n in pop["by_state"].items())
    controls_ok = sum(1 for c in report["controls"] if c["class"] in CONTROL_PASS)
    lines = [
        f"KBLI OSS refresh — {report['date']} (UTC)",
        f"population: {pop['count']} licensing gaps ({states}; {pop['quarantined']} quarantined) — scoreboard-derived",
        f"fetched {cov['fetched']}/{cov['asked']} asked · trusted answers {cov['trusted_answers']} · "
        f"errors {cov['errors']} · deferred {cov['deferred']} · controls {controls_ok}/{len(report['controls'])} ok",
    ]
    lines += [f"  {klass:<12} {n:>4}" for klass, n in report["counts"].items()]
    proposals = [c for c in report["codes"] if c["class"] in PROPOSAL_CLASSES]
    for entry in proposals:
        route = "quarantine owner" if entry["quarantined_by"] else "L2 transform"
        lines.append(f"  PROPOSED {entry['code']} {entry['class']}: {entry['reason']} → {route}")
    lines.append(f"verdict: {report['verdict']} (exit {report['exit_code']})")
    if report["cure_spec"]:
        # A dry-run never writes it — say so, the same honesty as "DRY-RUN —
        # nothing written" below it (D7).
        prefix = "cure spec (dry-run, not written)" if dry_run else "cure spec"
        lines.append(f"{prefix}: {report['cure_spec']}")
    return "\n".join(lines)


# ------------------------------------------------------------------------- main


def _parse_only(raw: str) -> set[str]:
    return {c.strip() for c in raw.split(",") if c.strip()}


def main(argv: list[str] | None = None, *, session: ScopeFetcher | None = None,
         now: Callable[[], datetime] | None = None, sleep: Callable[[float], None] = time.sleep) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--ground-truth", type=Path, default=DEFAULT_GROUND_TRUTH)
    parser.add_argument("--only", default="", help="comma-separated subset of the gap population")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True, help="fetch and print, write nothing (default)")
    mode.add_argument("--apply", action="store_true", help="also write the report (+ cure spec when proposed)")
    parser.add_argument("--out-root", type=Path, default=REPO_ROOT,
                        help="root the repo-relative outputs are written under (default: the repo)")
    parser.add_argument("--deadline-s", type=float, default=DEFAULT_DEADLINE_S)
    args = parser.parse_args(argv)

    moment = (now or (lambda: datetime.now(timezone.utc)))()
    date = moment.strftime("%Y-%m-%d")
    generated_at = moment.strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        records = load_records(args.canonical)
        uuids = dict(ground_truth.load_five_digit_codes(args.ground_truth))
        canonical_bytes = args.canonical.read_bytes()
    except (OSError, ValueError, KeyError, json.JSONDecodeError, ground_truth.InvalidCode) as exc:
        print(f"CANNOT VERIFY: canonical or ground truth unreadable: {exc}")
        return EXIT_CANNOT_VERIFY

    population, strong_codes = gap_population(records)
    by_code = {str(r.get(CODE_FIELD)): r for r in records}
    targets = population
    only = _parse_only(args.only)
    if only:
        outside = sorted(only - {str(r.get(CODE_FIELD)) for r in population})
        if outside:
            print(f"USAGE: --only names code(s) outside the licensing-gap population: {', '.join(outside)}")
            return EXIT_USAGE
        targets = [r for r in population if str(r.get(CODE_FIELD)) in only]
    if not targets:
        print("CANNOT VERIFY: empty population — the scoreboard reports no licensing gap to ask about")
        return EXIT_CANNOT_VERIFY
    controls = [by_code[c] for c in pick_controls(strong_codes)]

    user_key = os.environ.get(USER_KEY_ENV, "")
    if user_key and not USER_KEY_RE.fullmatch(user_key):
        print(f"CANNOT VERIFY: {USER_KEY_ENV} is set but is not a sendable header value (value not printed)")
        return EXIT_CANNOT_VERIFY
    owned_session = session is None
    session = session or OssSession(user_key)
    try:
        control_results, target_results = run_loop(
            targets, controls, uuids, session, deadline_s=args.deadline_s, sleep=sleep,
            log=lambda message: print(f"  {message}", flush=True),
        )
    finally:
        if owned_session:
            session.close()

    counts = Counter(entry["class"] for entry in target_results)
    # `bool(control_results)` matters on its own: `all(...)` over an EMPTY
    # control list is vacuously True, so a catalogue with no sourced code to
    # draw a control from would otherwise "pass" its controls and let 219
    # honest 404s read as nothing new (D3 — superscar #2 again, one layer up).
    controls_ok = bool(control_results) and all(c["class"] in CONTROL_PASS for c in control_results)
    exit_code, verdict = decide_exit(counts, controls_ok)

    # Only a run whose verdict is "proposed" may emit something applyable: a
    # proposal beside a failed control or an auth refusal is not vouched for.
    spec = (build_cure_spec(date, target_results, by_code, hashlib.sha256(canonical_bytes).hexdigest())
            if exit_code == EXIT_PROPOSED else None)
    spec_rel = (SPEC_REL / f"oss_refresh_{date.replace('-', '_')}.json").as_posix() if spec else None
    canonical_meta = {
        "path": "data/source_documents/KBLI_2025_FINAL_CLEAN.json",
        "sha256": hashlib.sha256(canonical_bytes).hexdigest(),
        "version": (json.loads(canonical_bytes).get("metadata") or {}).get("version"),
    }

    out_root = args.out_root.expanduser()
    report_path = out_root / REPORT_REL / f"{date}.json"
    # Every output this run actually wrote, in write order — so a LATER
    # failure can undo the earlier ones instead of leaving a report that
    # disagrees with the exit code the process returns (M3).
    written: list[Path] = []

    # The spec is written BEFORE the report that names it (D2): a report
    # saying `exit_code: 1` and `cure_spec: <path>` while that path was
    # refused would be a lie on disk the moment it lands. If the spec write
    # is refused, this run IS exit 4 — the report built afterwards (if any)
    # carries that exit code, no cure_spec, and says why.
    if args.apply and spec is not None:
        spec_path = out_root / spec_rel
        exc = _write_or_refuse(out_root, written, spec_path, json.dumps(spec, indent=2, ensure_ascii=False) + "\n")
        if exc is not None:
            exit_code = EXIT_CANNOT_VERIFY
            verdict = f"cure spec write refused: {exc}"
            spec_rel = None
        else:
            print(f"OSS_REFRESH_CURE_SPEC={spec_path}")

    report = build_report(
        date=date, generated_at=generated_at, canonical=canonical_meta, population=population,
        control_results=control_results, target_results=target_results, exit_code=exit_code,
        verdict=verdict, cure_spec_rel=spec_rel, user_key_present=bool(user_key),
    )
    summary = render_summary(report, dry_run=not args.apply)
    print(summary)

    if not args.apply:
        print("DRY-RUN — nothing written (pass --apply to write the report)")
        return exit_code

    exc = _write_or_refuse(out_root, written, report_path, json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    if exc is None:
        exc = _write_or_refuse(out_root, written, report_path.with_suffix(".md"), summary + "\n")
    if exc is not None:
        # M3: never leave a partial run's output behind for the wrapper (or
        # a human) to read as something it isn't — a report.json saying
        # `exit_code: 1` while the process itself returns 4 is exactly the
        # "Esiste≠Armato" shape (superscar #2) one layer up. Undo every
        # output this run wrote and say so on ONE parseable line the wrapper
        # greps for, never a raw traceback and never a secret.
        for p in written:
            p.unlink(missing_ok=True)
        print(f"OSS_REFRESH_OUTPUT_REFUSED={exc}")
        return EXIT_CANNOT_VERIFY
    print(f"OSS_REFRESH_REPORT={report_path}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
