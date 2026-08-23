"""Manual/ceremony probe wrapper for ``POST /api/visa-oracle/evaluate``.

Every request must now carry an explicit ``traffic_source`` query parameter;
the router rejects an omission with a sanitized 422 instead of silently
classifying it as ``real``. That fail-closed boundary matters because an
operator probe is not organic traffic: `shadow_evidence.py`'s G-a-vol gate
reserves ``real`` for genuine adoption evidence, and earlier arming/prove-live
ceremonies that relied on the former implicit default contaminated that ledger
(3 rows 2026-07-26, 4 rows 2026-08-10, 2 rows + 1 rejected 422 on 2026-08-11 --
``.agents/skills/visaoracle/{SKILL,CURRENT_STATE}.md``).

This CLI closes that gap for the manual path: it defaults to
``traffic_source=synthetic_driver`` plus the ``X-Visa-Driver-Token`` header
(read from the W4 gold-corpus replay driver credential file, never printed,
logged, or committed), so a probe run through this wrapper cannot silently
land as ``real``. Missing/loose token file is a hard, fail-closed error --
never a silent fallback to ``real``.

Usage (from ``apps/backend-rag``)::

    PYTHONPATH=. .venv/bin/python -m backend.scripts.visa_engine.probe_evaluate \\
      --url https://nuzantara-rag.fly.dev/api/visa-oracle/evaluate \\
      --payload /path/to/facts.json

Payload can also be piped on stdin (omit ``--payload``). The driver token is
read by default from ``~/.config/nuzantara/visa-signing/driver-token`` (the
same custody location as the signing keys -- see
``docs/runbooks/visa-engine-key-ceremony.md`` and
``reference_visa_oracle_signing_key_lives_on_m5_2026_08_10.md``); override
with ``--driver-token-file`` or ``$VISA_ENGINE_DRIVER_TOKEN_FILE``.

For the rare legitimate case a probe must exercise the exact real-caller
code path, pass ``--as-real-i-know-what-i-am-doing`` explicitly -- it is loud
(prints a warning banner) and never the default.

By default this CLI prints a deliberately small summary (mode/state/rule
pack identity) -- enough to prove the endpoint answered, not enough to
verify what it actually decided. Pass ``--full-body`` (or set
``$VISA_ORACLE_PROBE_FULL_BODY=1``) to print the complete, pretty-printed
JSON response instead -- candidates, reason codes, review reasons and all.
The evaluate endpoint's response envelope never echoes applicant facts back
(see ``visa_oracle_evaluate.py``'s module docstring and the ``Decision`` /
``VisaOracleDisplayDTO`` schemas: candidates carry product/rule-pack/pricing
data only, ``missing_facts`` is fact *paths* not values, and
``facts_fingerprint`` is an HMAC digest) -- so the full body is safe for a
synthetic-payload probe run in a terminal. The one thing the response can
carry that must never reach a scrollback is the driver-token header
reflected by a misbehaving proxy; the redaction below covers both output
shapes.

This module never imports the FastAPI app; it is a pure HTTP client CLI,
offline-ops posture like its ``visa_engine`` script siblings
(``sign_pack.py``, ``activate_pack.py``).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import stat
import sys
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger("visa_engine.probe_evaluate")

#: Direct backend URL (bypasses the balizero.com proxy) -- override with
#: --url or $VISA_ORACLE_PROBE_URL for a different environment/proxy.
DEFAULT_URL = "https://nuzantara-rag.fly.dev/api/visa-oracle/evaluate"
URL_ENV = "VISA_ORACLE_PROBE_URL"

#: Opt-in to the full pretty-printed response body instead of the small
#: mode/state/rule_pack summary -- see module docstring.
FULL_BODY_ENV = "VISA_ORACLE_PROBE_FULL_BODY"

DEFAULT_DRIVER_TOKEN_FILE = Path.home() / ".config" / "nuzantara" / "visa-signing" / "driver-token"
DRIVER_TOKEN_FILE_ENV = "VISA_ENGINE_DRIVER_TOKEN_FILE"
DRIVER_TOKEN_HEADER = "X-Visa-Driver-Token"

#: Migration 256's CHECK classes, verbatim (mirrors
#: ``shadow_evidence.SYNTHETIC_TRAFFIC_SOURCES`` -- not imported directly so
#: this offline CLI never imports the FastAPI app's dependency graph).
SYNTHETIC_TRAFFIC_SOURCES = frozenset({"synthetic_gold", "synthetic_driver"})
REAL_TRAFFIC_SOURCE = "real"
ALL_TRAFFIC_SOURCES = frozenset({REAL_TRAFFIC_SOURCE, *SYNTHETIC_TRAFFIC_SOURCES})
DEFAULT_SYNTHETIC_TRAFFIC_SOURCE = "synthetic_driver"

DEFAULT_TIMEOUT_SECONDS = 30.0

#: Group/other permission bits -- a token file must be chmod 0600 or
#: stricter (same posture as sign_pack.py's key-file check, cicatrix
#: family #4 "secret in the clear").
_GROUP_OTHER_BITS = stat.S_IRWXG | stat.S_IRWXO


class ProbeEvaluateError(RuntimeError):
    """A fail-closed condition this CLI refuses to proceed past."""


def _env_flag(name: str) -> bool:
    """Truthy-string env parse for a boolean CLI default (``--full-body``)."""

    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _check_token_file_permissions(path: Path, mode: int) -> None:
    if mode & _GROUP_OTHER_BITS:
        raise ProbeEvaluateError(
            f"driver token file {path} has mode {oct(mode)} -- refusing to read a "
            "group/other-accessible secret. `chmod 0600` it first."
        )


def _load_driver_token(path: Path) -> str:
    """Load the W4 driver credential from disk.

    Fail-closed on every irregular shape (missing, loose permissions, not a
    regular file, empty) -- NEVER falls back to omitting the header, which
    would resurface as a 400 from the server rather than a clear local
    error, and never logs or returns the token in an exception message.
    """

    try:
        file_stat = path.stat()
    except FileNotFoundError as exc:
        raise ProbeEvaluateError(
            f"driver token file not found: {path} -- refusing to fall back to "
            "traffic_source=real. Provision the file (see "
            "docs/runbooks/visa-engine-key-ceremony.md) or pass "
            "--as-real-i-know-what-i-am-doing explicitly if this probe truly must "
            "run as real traffic."
        ) from exc
    except OSError as exc:
        raise ProbeEvaluateError(f"cannot stat driver token file {path}: {exc}") from exc

    if not stat.S_ISREG(file_stat.st_mode):
        raise ProbeEvaluateError(f"driver token file {path} is not a regular file")
    _check_token_file_permissions(path, file_stat.st_mode)

    try:
        token = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ProbeEvaluateError(f"cannot read driver token file {path}: {exc}") from exc

    if not token:
        raise ProbeEvaluateError(f"driver token file {path} is empty")
    return token


def _load_payload(payload_arg: str | None) -> dict[str, Any]:
    """Load the request body JSON from ``--payload`` file, or stdin if omitted."""

    if payload_arg is None:
        raw = sys.stdin.read()
        source = "<stdin>"
    else:
        try:
            raw = Path(payload_arg).read_text(encoding="utf-8")
        except OSError as exc:
            raise ProbeEvaluateError(f"cannot read payload file {payload_arg}: {exc}") from exc
        source = payload_arg

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProbeEvaluateError(f"payload from {source} is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ProbeEvaluateError(f"payload from {source} must be a JSON object")
    return parsed


def resolve_traffic_source(args: argparse.Namespace) -> str:
    """Decide the ``traffic_source`` query value. Pure function, no I/O.

    Without ``--as-real-i-know-what-i-am-doing``: only the two synthetic classes
    are reachable, defaulting to ``synthetic_driver``. Requesting ``real``
    (or anything outside the synthetic set) without the override flag is
    REJECTED here -- it is never silently promoted to a synthetic value,
    the caller must pass the loud flag to explicitly opt into landing as
    real traffic.

    With ``--as-real-i-know-what-i-am-doing``: any accepted class is reachable
    (default ``real``) -- the flag only WIDENS the allowed set, it never
    narrows what ``--traffic-source`` can request, and a synthetic class
    requested alongside it still requires the driver token (matching the
    server's own contract: the flag is about caller intent, not about
    bypassing the server's synthetic-class gate).
    """

    requested = args.traffic_source
    if args.as_real_i_know_what_i_am_doing:
        return requested or REAL_TRAFFIC_SOURCE
    if requested is None:
        return DEFAULT_SYNTHETIC_TRAFFIC_SOURCE
    if requested not in SYNTHETIC_TRAFFIC_SOURCES:
        raise ProbeEvaluateError(
            f"--traffic-source {requested!r} requires --as-real-i-know-what-i-am-doing "
            f"(only {sorted(SYNTHETIC_TRAFFIC_SOURCES)} are accepted without it)"
        )
    return requested


def build_query_params(args: argparse.Namespace, traffic_source: str) -> dict[str, str]:
    params = {"traffic_source": traffic_source}
    if args.request_category:
        params["request_category"] = args.request_category
    return params


def build_headers(args: argparse.Namespace, traffic_source: str) -> dict[str, str]:
    """Resolve request headers. Reads the driver-token file when the
    resolved ``traffic_source`` is synthetic -- the only I/O this function
    performs, and it is exactly the fail-closed path under test.
    """

    headers = {"Content-Type": "application/json"}
    if traffic_source in SYNTHETIC_TRAFFIC_SOURCES:
        token_path = Path(args.driver_token_file).expanduser()
        headers[DRIVER_TOKEN_HEADER] = _load_driver_token(token_path)
    if args.idempotency_key:
        headers["Idempotency-Key"] = args.idempotency_key
    return headers


async def _post_evaluate(
    *,
    url: str,
    params: dict[str, str],
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float,
) -> httpx.Response:
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.post(url, params=params, headers=headers, json=payload)


def _summarize_response(response: httpx.Response) -> str:
    lines = [f"HTTP {response.status_code}"]
    try:
        body = response.json()
    except ValueError:
        lines.append(f"non-JSON body ({len(response.content)} bytes)")
        return "\n".join(lines)

    if not isinstance(body, dict):
        lines.append(f"unexpected body shape: {type(body).__name__}")
        return "\n".join(lines)

    mode = body.get("mode")
    decision = body.get("decision")
    decision = decision if isinstance(decision, dict) else {}
    state = decision.get("state")
    lines.append(f"mode={mode!r} state={state!r}")

    rule_pack = decision.get("rule_pack")
    if isinstance(rule_pack, dict):
        lines.append(
            "rule_pack: sequence={!r} version={!r} rule_pack_id={!r}".format(
                rule_pack.get("sequence"),
                rule_pack.get("version"),
                rule_pack.get("rule_pack_id"),
            )
        )
    else:
        lines.append("rule_pack: none (e.g. TEMPORARILY_UNAVAILABLE / no active pack)")

    return "\n".join(lines)


def _full_body_text(response: httpx.Response) -> str:
    """``--full-body``: the complete, pretty-printed JSON response.

    Unlike ``_summarize_response`` this is NOT deliberately small -- it is
    the whole decision (candidates, reason codes, review/no-path reasons,
    sources, display) that a real prove-live needs to actually verify. Its
    caller (``run``) applies the exact same driver-token redaction to this
    text as it does to the small summary -- see the comment at that call
    site for why.
    """

    lines = [f"HTTP {response.status_code}"]
    try:
        body = response.json()
    except ValueError:
        lines.append(f"non-JSON body ({len(response.content)} bytes)")
        return "\n".join(lines)

    lines.append(json.dumps(body, indent=2, sort_keys=True))
    return "\n".join(lines)


def run(args: argparse.Namespace) -> int:
    try:
        traffic_source = resolve_traffic_source(args)
        payload = _load_payload(args.payload)
        params = build_query_params(args, traffic_source)
        headers = build_headers(args, traffic_source)
    except ProbeEvaluateError as exc:
        logger.error("%s", exc)
        return 2

    if args.as_real_i_know_what_i_am_doing:
        logger.warning(
            "!!! sending traffic_source=%s -- this call WILL land in the shadow "
            "ledger as if it were organic end-user traffic !!!",
            traffic_source,
        )

    try:
        response = asyncio.run(
            _post_evaluate(
                url=args.url,
                params=params,
                headers=headers,
                payload=payload,
                timeout=args.timeout,
            )
        )
    except httpx.HTTPError:
        # Do not log the exception text: a transport/proxy exception can
        # reflect request data, including the driver-token header.
        logger.error("request to Visa Oracle evaluate endpoint failed")
        return 3

    # The endpoint never returns the driver token, but a misbehaving proxy
    # must not turn that contract into a CLI secret leak.  Redact the exact
    # credential from the human-facing output -- summary or full body, same
    # rule either way -- as a final defense in depth.
    summary = _full_body_text(response) if args.full_body else _summarize_response(response)
    driver_token = headers.get(DRIVER_TOKEN_HEADER)
    if driver_token:
        summary = summary.replace(driver_token, "[REDACTED]")
    print(summary)
    return 0 if response.status_code == 200 else 1


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Probe wrapper for POST /api/visa-oracle/evaluate. Defaults to "
            "traffic_source=synthetic_driver + X-Visa-Driver-Token so manual "
            "smoke/ceremony calls never land as traffic_source=real in the "
            "shadow ledger."
        )
    )
    parser.add_argument(
        "--url",
        default=os.environ.get(URL_ENV, DEFAULT_URL),
        help=f"Evaluate endpoint URL (default: {DEFAULT_URL}, env {URL_ENV})",
    )
    parser.add_argument(
        "--payload",
        default=None,
        help="Path to a JSON ApplicantFacts body; reads stdin if omitted",
    )
    parser.add_argument(
        "--traffic-source",
        default=None,
        choices=sorted(ALL_TRAFFIC_SOURCES),
        help=(
            "Query traffic_source. Default (without --as-real-i-know-what-i-am-doing): "
            f"{DEFAULT_SYNTHETIC_TRAFFIC_SOURCE}."
        ),
    )
    parser.add_argument(
        "--driver-token-file",
        default=os.environ.get(DRIVER_TOKEN_FILE_ENV, str(DEFAULT_DRIVER_TOKEN_FILE)),
        help=f"Path to the driver token file (default: {DEFAULT_DRIVER_TOKEN_FILE})",
    )
    parser.add_argument("--request-category", default=None)
    parser.add_argument("--idempotency-key", default=None)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument(
        "--full-body",
        action="store_true",
        default=_env_flag(FULL_BODY_ENV),
        help=(
            "Print the complete, pretty-printed JSON response body instead of "
            "the small mode/state/rule_pack summary -- candidates, reason "
            "codes and review reasons included. Same driver-token redaction "
            f"applies either way. Default: off (env {FULL_BODY_ENV}=1 to "
            "opt in)."
        ),
    )
    parser.add_argument(
        "--as-real-i-know-what-i-am-doing",
        action="store_true",
        help=(
            "DANGEROUS: allow traffic_source=real (or any class) for this probe. "
            "The probe WILL be counted as organic end-user traffic by the shadow "
            "evidence ledger. Only for the rare case a probe must exercise the "
            "exact real-caller code path. Prints a loud warning before sending."
        ),
    )
    return parser


def _parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse CLI arguments using the same offline-ops convention as siblings."""

    return _build_arg_parser().parse_args(argv)


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = _parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
