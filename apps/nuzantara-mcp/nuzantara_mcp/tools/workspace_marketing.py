"""Fail-closed tools for the Bali Zero ChatGPT Business marketing workspace.

This module is intentionally not registered by the full Nuzantara MCP server.
``server_workspace_marketing`` creates a fresh FastMCP instance and registers
only the tools below.  The boundary is structural: there is no CRM, client,
document, raw-intelligence, admin, filesystem-path, or social-publishing tool
on this surface.

Only public-intended editorial material may cross the workspace boundary.
News Room results are allowlisted and redacted before they leave the Pro. WR2
jobs accept a small, typed brief and return only closed SOL strategy codes for
human development in the governed local pipeline. FlowKit generation uses
fixed project/tier settings and never accepts local paths.
"""

from __future__ import annotations

import asyncio
import fcntl
import hashlib
import json
import os
import re
import sys
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterator
from urllib.parse import quote, urlsplit, urlunsplit

from nuzantara_mcp.workspace_flowkit import run as _run_flowkit_cli

BackendCall = Callable[..., Awaitable[dict[str, Any]]]

MAX_LIST_ITEMS = 25
MAX_PUBLIC_TEXT = 12_000
MAX_PROMPT_TEXT = 3_000
MAX_NOTES_TEXT = 1_000
FLOW_PROJECT_NAME = "bali-zero-marketing-workspace"
FLOW_PAYGATE_TIER = "PAYGATE_TIER_TIER1P5"
ALLOWED_PLATFORMS = frozenset({"instagram", "x", "facebook"})
ALLOWED_LANGUAGES = frozenset({"id", "en"})
ALLOWED_ORIENTATIONS = frozenset({"PORTRAIT", "LANDSCAPE"})
JOB_ID_RE = re.compile(r"^[0-9a-f]{32}$")
ITEM_ID_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,158}[A-Za-z0-9])?$")
MEDIA_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,256}$")
REQUEST_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{7,63}$")
CONFIRMATION_WORDS = frozenset({"CONFIRM", "CONFERMO", "SETUJU"})

_EMAIL_RE = re.compile(
    r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])",
    re.IGNORECASE,
)
_PHONE_RE = re.compile(
    r"(?<!\w)(?:\+\d{1,3}[\s()-]*(?:\d[\s()-]*){7,13}|0(?:\d[\s()-]*){8,13})(?!\w)"
)
_CURRENCY_RE = re.compile(
    r"(?<!\w)(?:Rp|IDR)\s*\d(?:[\d.,]*\d)?(?!\w)",
    re.IGNORECASE,
)
_IDENTIFIER_RE = re.compile(
    r"\b(NIK|KTP|NPWP|passport(?:\s+number)?|nomor\s+paspor|tax\s+id|id\s+number)"
    r"\b\s*[:#-]?\s*[A-Z0-9.-]{6,}",
    re.IGNORECASE,
)
_LONG_DIGIT_RE = re.compile(r"(?<!\d)\d{12,}(?!\d)")
_PASSPORT_LIKE_RE = re.compile(r"(?<![A-Z0-9])[A-Z]{1,3}\d{6,9}(?![A-Z0-9])")
_LOCAL_PATH_RE = re.compile(r"(?:/Users/[^\s\"']+|~/[^\s\"']+)")
_SECRET_VALUE_RE = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|Bearer\s+[A-Za-z0-9._-]{16,})\b",
    re.IGNORECASE,
)


def _state_dir() -> Path:
    configured = os.getenv("WORKSPACE_MARKETING_STATE_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".nuzantara" / "workspace-marketing"


def _writes_enabled() -> bool:
    return os.getenv("WORKSPACE_MARKETING_WRITES_ENABLED", "").strip().lower() == "true"


def _require_write_confirmation(confirmation: str) -> None:
    if not _writes_enabled():
        raise RuntimeError("Workspace marketing write actions are not armed")
    normalized = str(confirmation or "").strip().upper()
    if normalized not in CONFIRMATION_WORDS:
        raise ValueError(
            "A team member must explicitly confirm with CONFIRM, CONFERMO, or SETUJU"
        )


def _queue_path() -> Path:
    configured = os.getenv("WR2_QUEUE_PATH", "").strip()
    if configured:
        return Path(configured).expanduser()
    return (
        Path.home()
        / "nuzantara/apps/war-room/output/queue/human-review-queue.json"
    )


def _clean_text(value: Any, *, limit: int = MAX_PUBLIC_TEXT) -> str:
    """Return bounded public text with common direct identifiers removed."""

    text = str(value or "").replace("\x00", " ").strip()

    def redact_non_currency(segment: str) -> str:
        segment = _IDENTIFIER_RE.sub(
            lambda match: f"{match.group(1)} [identifier removed]",
            segment,
        )
        segment = _EMAIL_RE.sub("[email removed]", segment)
        segment = _PHONE_RE.sub("[phone removed]", segment)
        segment = _LONG_DIGIT_RE.sub("[number removed]", segment)
        segment = _PASSPORT_LIKE_RE.sub("[identifier removed]", segment)
        segment = _LOCAL_PATH_RE.sub("[local path removed]", segment)
        return _SECRET_VALUE_RE.sub("[secret removed]", segment)

    public_parts: list[str] = []
    cursor = 0
    for currency_match in _CURRENCY_RE.finditer(text):
        public_parts.append(redact_non_currency(text[cursor : currency_match.start()]))
        public_parts.append(currency_match.group(0))
        cursor = currency_match.end()
    public_parts.append(redact_non_currency(text[cursor:]))
    return "".join(public_parts)[:limit]


def _public_team_input(value: Any, *, field: str, limit: int) -> str:
    """Reject private-looking team input instead of silently forwarding redactions."""

    raw = str(value or "").replace("\x00", " ").strip()
    if len(raw) > limit:
        raise ValueError(f"{field} exceeds the allowed length")
    if raw.startswith("-"):
        raise ValueError(f"{field} cannot start with a command-line option")
    cleaned = _clean_text(raw, limit=limit)
    if "[" in cleaned and any(
        marker in cleaned
        for marker in (
            "[email removed]",
            "[phone removed]",
            "[identifier removed]",
            "[number removed]",
            "[local path removed]",
            "[secret removed]",
        )
    ):
        raise ValueError(f"{field} contains private or local-only data")
    return cleaned


def _clean_public_value(value: Any, *, depth: int = 0) -> Any:
    """Recursively sanitize a small public-intended editorial value."""

    if depth > 3:
        return None
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _clean_text(value)
    if isinstance(value, list):
        return [_clean_public_value(item, depth=depth + 1) for item in value[:30]]
    if isinstance(value, dict):
        return {
            _clean_text(key, limit=80): _clean_public_value(item, depth=depth + 1)
            for key, item in list(value.items())[:40]
        }
    return _clean_text(value)


def _public_source_url(value: Any) -> str:
    """Return an HTTP(S) citation URL without query parameters or fragments."""

    candidate = _clean_text(value, limit=2_000)
    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return ""
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        return ""
    return urlunsplit((parsed.scheme.lower(), parsed.netloc, parsed.path, "", ""))


def _bounded_limit(limit: int) -> int:
    if not isinstance(limit, int):
        raise ValueError("limit must be an integer")
    return max(1, min(limit, MAX_LIST_ITEMS))


def _validated_item_id(item_id: str) -> str:
    candidate = str(item_id or "").strip()
    if not ITEM_ID_RE.fullmatch(candidate):
        raise ValueError("Invalid News Room item id")
    return candidate


def _validated_job_id(job_id: str) -> str:
    candidate = str(job_id or "").strip().lower()
    if not JOB_ID_RE.fullmatch(candidate):
        raise ValueError("Invalid WR2 job id")
    return candidate


def _validated_media_id(media_id: str, *, required: bool = True) -> str:
    candidate = str(media_id or "").strip()
    if not candidate and not required:
        return ""
    if candidate.startswith("-") or not MEDIA_ID_RE.fullmatch(candidate):
        raise ValueError("Invalid Flow media id")
    return candidate


def _validated_request_key(request_key: str) -> str:
    candidate = str(request_key or "").strip()
    if not REQUEST_KEY_RE.fullmatch(candidate):
        raise ValueError(
            "request_key must be 8-64 letters, numbers, dots, underscores, or dashes"
        )
    return candidate


def _first_text(*values: Any) -> str:
    return next((value for value in values if isinstance(value, str)), "")


def _public_news_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "item_id": _clean_text(item.get("id") or item.get("item_id"), limit=160),
        "title": _clean_text(item.get("title"), limit=500),
        "category": _clean_text(item.get("category"), limit=120),
        "status": _clean_text(item.get("status"), limit=80),
        "detected_at": _clean_text(item.get("detected_at"), limit=80),
        "published_at": _clean_text(item.get("published_at"), limit=80),
        "source_name": _clean_text(
            _first_text(item.get("source_name"), item.get("source")), limit=240
        ),
        "liveness_tier": _clean_text(item.get("liveness_tier"), limit=80),
        "preview": _clean_text(item.get("content"), limit=1_200),
    }


def _public_news_article(item: dict[str, Any]) -> dict[str, Any]:
    enrichment = item.get("enrichment")
    allowed_enrichment: dict[str, Any] = {}
    if isinstance(enrichment, dict):
        for field in (
            "headline",
            "thirty_second_brief",
            "the_facts",
            "in_practice",
            "next_steps",
            "bali_zero_take",
            "faq",
        ):
            if field in enrichment:
                allowed_enrichment[field] = _clean_public_value(enrichment[field])

    return {
        "item_id": _clean_text(item.get("item_id") or item.get("id"), limit=160),
        "title": _clean_text(item.get("title"), limit=500),
        "category": _clean_text(item.get("category"), limit=120),
        "status": _clean_text(item.get("status"), limit=80),
        "content": _clean_text(item.get("content")),
        "source_name": _clean_text(
            _first_text(item.get("source_name"), item.get("source")), limit=240
        ),
        "source_url": _public_source_url(item.get("source_url")),
        "published_at": _clean_text(item.get("published_at"), limit=80),
        "detected_at": _clean_text(item.get("detected_at"), limit=80),
        "liveness_tier": _clean_text(item.get("liveness_tier"), limit=80),
        "editorial": allowed_enrichment,
        "boundary": "Public-intended News Room copy; raw enrichment is withheld.",
    }


def _load_review_queue(path: Path | None = None) -> list[dict[str, Any]]:
    queue_file = path or _queue_path()
    payload = json.loads(queue_file.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = payload.get("items") or payload.get("queue") or []
    else:
        raise RuntimeError("WR2 review queue has an unsupported shape")
    if not isinstance(items, list):
        raise RuntimeError("WR2 review queue items are not a list")
    return [item for item in items if isinstance(item, dict)]


def _queue_item_id(item: dict[str, Any]) -> str:
    return str(item.get("item_id") or item.get("id") or item.get("topic_slug") or "")


def _ref_code(item_id: str) -> str:
    digest = hashlib.sha1(item_id.encode("utf-8")).hexdigest()
    return f"WR2-{digest[:6].upper()}"


def _public_review_item(item: dict[str, Any], *, detail: bool = False) -> dict[str, Any]:
    item_id = _queue_item_id(item)
    public: dict[str, Any] = {
        "item_id": _clean_text(item_id, limit=200),
        "ref_code": _ref_code(item_id) if item_id else "",
        "topic": _clean_text(item.get("topic") or item.get("topic_slug"), limit=500),
        "state": _clean_text(
            item.get("state") or item.get("critic_overall_verdict"), limit=100
        ),
        "critic_verdict": _clean_text(
            item.get("critic_overall_verdict"), limit=100
        ),
        "slide_count": _bounded_public_int(
            item.get("slide_count") or item.get("intended_slide_count"),
            minimum=0,
            maximum=20,
        ),
        "domain": _clean_text(item.get("domain"), limit=120),
        "created_at": _clean_text(
            item.get("created_at") or item.get("drafted_at"), limit=80
        ),
    }
    if detail:
        public.update(
            {
                "critic_summary": _clean_text(item.get("critic_summary"), limit=3_000),
                "caption": _clean_text(item.get("caption"), limit=5_000),
                "fact_check_status": _clean_text(
                    item.get("fact_check_status"), limit=120
                ),
                "archetype": _clean_text(item.get("archetype"), limit=120),
                "layout_family": _clean_text(
                    item.get("layout_family_primary"), limit=120
                ),
                "tone_register": _clean_text(
                    item.get("tone_register_primary"), limit=120
                ),
            }
        )
    return public


def _bounded_public_int(value: Any, *, minimum: int, maximum: int) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return max(minimum, min(value, maximum))


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            os.chmod(temporary_path, 0o600)
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink(missing_ok=True)


def _operation_path(kind: str, request_key: str) -> Path:
    safe_kind = re.sub(r"[^a-z0-9_-]", "-", kind.lower())
    digest = hashlib.sha256(request_key.encode("utf-8")).hexdigest()
    return _state_dir() / "operations" / safe_kind / f"{digest}.json"


def _operation_fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _claim_operation(
    kind: str,
    request_key: str,
    fingerprint_payload: dict[str, Any],
    initial: dict[str, Any],
) -> tuple[Path, dict[str, Any], bool]:
    """Create one idempotency record, or return its existing result."""

    safe_key = _validated_request_key(request_key)
    path = _operation_path(kind, safe_key)
    fingerprint = _operation_fingerprint(fingerprint_payload)
    if path.is_file():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing.get("fingerprint") != fingerprint:
            raise ValueError("request_key was already used for different inputs")
        return path, existing, False

    record = {
        "schema_version": 1,
        "kind": kind,
        "request_key_hash": hashlib.sha256(safe_key.encode("utf-8")).hexdigest(),
        "fingerprint": fingerprint,
        "status": "accepted",
        "created_at": datetime.now(timezone.utc).isoformat(),
        **initial,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing.get("fingerprint") != fingerprint:
            raise ValueError("request_key was already used for different inputs")
        return path, existing, False
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    return path, record, True


def _flow_daily_limit_available() -> bool:
    raw_limit = os.getenv("WORKSPACE_MARKETING_FLOW_DAILY_LIMIT", "6").strip()
    try:
        daily_limit = max(0, min(int(raw_limit), 50))
    except ValueError as exc:
        raise RuntimeError("WORKSPACE_MARKETING_FLOW_DAILY_LIMIT is invalid") from exc
    today = datetime.now(timezone.utc).date().isoformat()
    operation_root = _state_dir() / "operations"
    used = 0
    for kind in ("flow-image", "flow-video"):
        for path in (operation_root / kind).glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            if str(payload.get("created_at", "")).startswith(today):
                used += 1
    return used < daily_limit


def _bounded_env_int(name: str, default: int, maximum: int) -> int:
    raw_value = os.getenv(name, str(default)).strip()
    try:
        return max(0, min(int(raw_value), maximum))
    except ValueError as exc:
        raise RuntimeError(f"{name} is invalid") from exc


def _sol_capacity_available() -> bool:
    daily_limit = _bounded_env_int("WORKSPACE_MARKETING_SOL_DAILY_LIMIT", 4, 20)
    max_active = _bounded_env_int("WORKSPACE_MARKETING_SOL_MAX_ACTIVE", 1, 2)
    today = datetime.now(timezone.utc).date().isoformat()
    operation_root = _state_dir() / "operations" / "wr2-sol"
    used = 0
    for path in operation_root.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if str(payload.get("created_at", "")).startswith(today):
            used += 1

    active = 0
    for path in (_state_dir() / "jobs").glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if payload.get("status") in {"queued", "running"}:
            active += 1
    return used < daily_limit and active < max_active


@contextmanager
def _flow_claim_lock() -> Iterator[None]:
    """Serialize Flow quota checks and idempotency claims across MCP requests."""

    operation_root = _state_dir() / "operations"
    operation_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(operation_root, 0o700)
    lock_path = operation_root / ".flow-claim.lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        os.chmod(lock_path, 0o600)
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _claim_flow_operation(
    kind: str,
    request_key: str,
    fingerprint_payload: dict[str, Any],
) -> tuple[Path, dict[str, Any], bool]:
    """Atomically reserve one bounded Flow operation or return its prior claim."""

    with _flow_claim_lock():
        existing_path = _operation_path(kind, request_key)
        if not existing_path.is_file() and not _flow_daily_limit_available():
            raise RuntimeError("Daily Flow generation limit reached")
        return _claim_operation(kind, request_key, fingerprint_payload, {})


def _existing_flow_operation(
    kind: str,
    request_key: str,
    fingerprint_payload: dict[str, Any],
) -> dict[str, Any] | None:
    """Return a prior idempotent claim without creating or consuming quota."""

    with _flow_claim_lock():
        path = _operation_path(kind, request_key)
        if not path.is_file():
            return None
        try:
            operation = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("Flow operation record is invalid") from exc
        if operation.get("fingerprint") != _operation_fingerprint(fingerprint_payload):
            raise ValueError("request_key was already used for different inputs")
        return operation


async def _flow_preflight() -> dict[str, Any] | None:
    """Return a sanitized outage result before reserving quota, or None if ready."""

    try:
        payload = await _run_flowkit_cli(["health"], timeout_s=60)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        raise RuntimeError("FlowKit preflight failed on Pro") from exc
    result = _safe_flow_result(payload)
    return None if result.get("ok") is True else result


def _claim_sol_operation(
    request_key: str,
    fingerprint_payload: dict[str, Any],
    job_payload: dict[str, Any],
) -> tuple[Path, dict[str, Any], bool]:
    """Atomically cap and reserve both operation and visible queued job."""

    operation_root = _state_dir() / "operations"
    operation_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(operation_root, 0o700)
    lock_path = operation_root / ".sol-claim.lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        os.chmod(lock_path, 0o600)
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            existing_path = _operation_path("wr2-sol", request_key)
            if not existing_path.is_file() and not _sol_capacity_available():
                raise RuntimeError("SOL daily or active-job limit reached")
            operation_path, operation, created = _claim_operation(
                "wr2-sol",
                request_key,
                fingerprint_payload,
                {"job_id": job_payload["job_id"]},
            )
            if created:
                job_path = _state_dir() / "jobs" / f"{job_payload['job_id']}.json"
                try:
                    _write_json_atomic(job_path, job_payload)
                except Exception:
                    operation["status"] = "failed"
                    _write_json_atomic(operation_path, operation)
                    raise
            return operation_path, operation, created
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _worker_env() -> dict[str, str]:
    allowed = {"HOME", "LANG", "LC_ALL", "PATH", "TMPDIR", "CODEX_HOME"}
    env = {key: value for key, value in os.environ.items() if key in allowed}
    standard_path = (
        "/opt/homebrew/bin:/Users/nuzantara/.local/bin:"
        "/usr/local/bin:/usr/bin:/bin"
    )
    current_path = env.get("PATH", "")
    env["PATH"] = f"{standard_path}:{current_path}" if current_path else standard_path
    env["WORKSPACE_MARKETING_STATE_DIR"] = str(_state_dir())
    return env


async def _spawn_wr2_worker(job_id: str) -> int:
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "nuzantara_mcp.workspace_marketing_worker",
        job_id,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
        env=_worker_env(),
        start_new_session=True,
    )
    return int(process.pid or 0)


def _safe_flow_result(payload: dict[str, Any]) -> dict[str, Any]:
    allowed = (
        "ok",
        "status",
        "ready",
        "media_id",
        "video_media_id",
        "start_image_media_id",
        "scene_id",
        "project_id",
        "task_id",
        "error_kind",
    )
    result = {
        key: _clean_public_value(payload[key])
        for key in allowed
        if key in payload
    }
    result["executed_on"] = "Pro"
    if not bool(result.get("ok", False)):
        result["message"] = "FlowKit is unavailable or not connected on Pro."
    return result


def register(mcp: Any, backend_call: BackendCall) -> None:
    """Register the exact ChatGPT Business marketing allowlist."""

    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }
    )
    async def workspace_health() -> dict[str, Any]:
        """Return the bridge policy and local queue readiness; never returns secrets."""

        queue = _queue_path()
        return {
            "ok": queue.is_file(),
            "workspace": "Bali Zero Marketing",
            "news_room": "available",
            "wr2_queue": "available" if queue.is_file() else "unavailable",
            "sol_model": "gpt-5.6-sol",
            "publication": "manual_only",
            "write_actions_armed": _writes_enabled(),
            "forbidden_domains": [
                "client_pii",
                "crm",
                "documents",
                "raw_osint",
                "admin",
                "social_publish",
            ],
        }

    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        }
    )
    async def newsroom_list_pending(limit: int = 10) -> dict[str, Any]:
        """List redacted, public-intended News Room articles awaiting review."""

        bounded = _bounded_limit(limit)
        payload = await backend_call(
            "/api/workspace-marketing/news/pending",
            params={"limit": bounded},
        )
        raw_items = payload.get("items") if isinstance(payload, dict) else []
        items = raw_items if isinstance(raw_items, list) else []
        public = [
            _public_news_summary(item)
            for item in items[:bounded]
            if isinstance(item, dict)
        ]
        return {"count": len(public), "items": public, "type": "news"}

    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        }
    )
    async def newsroom_get_article(item_id: str) -> dict[str, Any]:
        """Read one sanitized News Room article; raw enrichment stays on Pro."""

        safe_id = _validated_item_id(item_id)
        payload = await backend_call(
            f"/api/workspace-marketing/news/{quote(safe_id, safe='')}"
        )
        if not isinstance(payload, dict):
            raise RuntimeError("News Room returned an unsupported article shape")
        return _public_news_article(payload)

    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }
    )
    async def wr2_list_review_queue(limit: int = 10) -> dict[str, Any]:
        """List sanitized WR2 carousel entries from the human review queue."""

        bounded = _bounded_limit(limit)
        items = _load_review_queue()
        selected = items[-bounded:]
        selected.reverse()
        return {
            "count": len(selected),
            "total": len(items),
            "items": [_public_review_item(item) for item in selected],
            "publication": "manual_only",
        }

    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }
    )
    async def wr2_get_review_item(item_id: str) -> dict[str, Any]:
        """Read one sanitized WR2 review item without internal filesystem paths."""

        safe_id = _clean_text(item_id, limit=200)
        if not safe_id:
            raise ValueError("WR2 item id is required")
        matches = [item for item in _load_review_queue() if _queue_item_id(item) == safe_id]
        if len(matches) != 1:
            raise ValueError("WR2 item id was not found or is ambiguous")
        return _public_review_item(matches[0], detail=True)

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        }
    )
    async def wr2_prepare_with_sol(
        topic: str,
        audience: str,
        request_key: str,
        confirmation: str,
        platforms: list[str] | None = None,
        language: str = "id",
        creative_notes: str = "",
    ) -> dict[str, Any]:
        """Prepare a SOL 5.6 creative direction for governed local WR2 Control.

        SOL runs read-only. The job cannot execute the privileged WR2 writer and
        cannot publish to any client-facing channel. A team member carries the
        returned handoff into the existing governed WR2 Control app.
        """

        _require_write_confirmation(confirmation)
        safe_topic = _public_team_input(topic, field="topic", limit=500)
        safe_audience = _public_team_input(audience, field="audience", limit=300)
        safe_notes = _public_team_input(
            creative_notes,
            field="creative_notes",
            limit=MAX_NOTES_TEXT,
        )
        if len(safe_topic) < 3:
            raise ValueError("topic must contain at least 3 characters")
        if len(safe_audience) < 3:
            raise ValueError("audience must contain at least 3 characters")
        raw_platforms = platforms or []
        if len(raw_platforms) > len(ALLOWED_PLATFORMS) or any(
            not isinstance(value, str) or len(value) > 20 for value in raw_platforms
        ):
            raise ValueError("Unsupported platform selection")
        selected_platforms = [value.strip().lower() for value in raw_platforms]
        if not selected_platforms:
            selected_platforms = ["instagram", "x", "facebook"]
        invalid_platforms = set(selected_platforms) - ALLOWED_PLATFORMS
        if invalid_platforms:
            raise ValueError("Unsupported platform selection")
        normalized_language = str(language or "").strip().lower()
        if normalized_language not in ALLOWED_LANGUAGES:
            raise ValueError("language must be 'id' or 'en'")

        safe_request_key = _validated_request_key(request_key)
        job_id = uuid.uuid4().hex
        payload: dict[str, Any] = {
            "schema_version": 1,
            "job_id": job_id,
            "kind": "wr2_sol_brief",
            "status": "queued",
            "phase": "waiting_for_sol",
            "topic": safe_topic,
            "audience": safe_audience,
            "platforms": sorted(set(selected_platforms)),
            "language": normalized_language,
            "creative_notes": safe_notes,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "publication": "manual_only",
        }
        operation_path, operation, created = _claim_sol_operation(
            safe_request_key,
            {
                "topic": safe_topic,
                "audience": safe_audience,
                "platforms": sorted(set(selected_platforms)),
                "language": normalized_language,
                "creative_notes": safe_notes,
            },
            payload,
        )
        if not created:
            if operation.get("status") == "failed":
                return {
                    "ok": False,
                    "job_id": operation.get("job_id"),
                    "status": "failed",
                    "next": "Use a new request_key after an operator checks Pro.",
                    "publication": "not_performed",
                }
            return {
                "ok": True,
                "job_id": operation.get("job_id"),
                "status": "already_accepted",
                "next": "Use wr2_job_status with this job_id.",
                "publication": "not_performed",
            }
        jobs_dir = _state_dir() / "jobs"
        job_path = jobs_dir / f"{job_id}.json"
        try:
            worker_pid = await _spawn_wr2_worker(job_id)
            if worker_pid <= 0:
                raise RuntimeError("SOL strategy worker did not return a process id")
        except Exception as exc:
            payload.update(
                {
                    "status": "failed",
                    "phase": "stopped",
                    "error_kind": "sol_worker_start_failed",
                    "message": "SOL strategy worker could not start on Pro.",
                }
            )
            _write_json_atomic(job_path, payload)
            operation["status"] = "failed"
            _write_json_atomic(operation_path, operation)
            raise RuntimeError("SOL strategy worker could not start on Pro") from exc
        operation["status"] = "queued"
        _write_json_atomic(operation_path, operation)
        return {
            "ok": True,
            "job_id": job_id,
            "status": "queued",
            "next": "Use wr2_job_status with this job_id.",
            "publication": "not_performed",
        }

    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }
    )
    async def wr2_job_status(job_id: str) -> dict[str, Any]:
        """Read the safe status of one SOL-to-WR2 production job."""

        safe_id = _validated_job_id(job_id)
        path = _state_dir() / "jobs" / f"{safe_id}.json"
        if not path.is_file():
            raise ValueError("WR2 job was not found")
        payload = json.loads(path.read_text(encoding="utf-8"))
        allowed = (
            "job_id",
            "status",
            "phase",
            "topic",
            "platforms",
            "language",
            "started_at",
            "updated_at",
            "completed_at",
            "result_item_ids",
            "creative_codes",
            "direction_ref",
            "error_kind",
            "message",
            "publication",
        )
        return {
            key: _clean_public_value(payload[key])
            for key in allowed
            if key in payload
        }

    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        }
    )
    async def flow_workspace_health() -> dict[str, Any]:
        """Check FlowKit readiness on Pro without returning local paths or secrets."""

        return _safe_flow_result(await _run_flowkit_cli(["health"], timeout_s=60))

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        }
    )
    async def flow_generate_image(
        prompt: str,
        request_key: str,
        confirmation: str,
        orientation: str = "PORTRAIT",
    ) -> dict[str, Any]:
        """Generate one Flow image using fixed Bali Zero workspace settings."""

        _require_write_confirmation(confirmation)
        safe_prompt = _public_team_input(
            prompt,
            field="prompt",
            limit=MAX_PROMPT_TEXT,
        )
        if len(safe_prompt) < 10:
            raise ValueError("prompt must contain at least 10 characters")
        safe_orientation = str(orientation or "").strip().upper()
        if safe_orientation not in ALLOWED_ORIENTATIONS:
            raise ValueError("Unsupported image orientation")
        safe_request_key = _validated_request_key(request_key)
        fingerprint_payload = {
            "prompt": safe_prompt,
            "orientation": safe_orientation,
        }
        existing = _existing_flow_operation(
            "flow-image",
            safe_request_key,
            fingerprint_payload,
        )
        if existing is not None:
            result = existing.get("result")
            return result if isinstance(result, dict) else {"ok": False, "status": "pending"}
        preflight_failure = await _flow_preflight()
        if preflight_failure is not None:
            return preflight_failure
        operation_path, operation, created = _claim_flow_operation(
            "flow-image",
            safe_request_key,
            fingerprint_payload,
        )
        if not created:
            result = operation.get("result")
            return result if isinstance(result, dict) else {"ok": False, "status": "pending"}
        try:
            payload = await _run_flowkit_cli(
                [
                    "generate-image",
                    "--prompt",
                    safe_prompt,
                    "--orientation",
                    safe_orientation,
                    "--project",
                    FLOW_PROJECT_NAME,
                    "--paygate-tier",
                    FLOW_PAYGATE_TIER,
                ],
                timeout_s=300,
            )
        except asyncio.CancelledError:
            operation.update(
                {
                    "status": "cancelled",
                    "result": {"ok": False, "status": "cancelled"},
                }
            )
            _write_json_atomic(operation_path, operation)
            raise
        except Exception as exc:
            operation.update(
                {
                    "status": "failed",
                    "result": {"ok": False, "status": "failed"},
                }
            )
            _write_json_atomic(operation_path, operation)
            raise RuntimeError("Flow image generation failed on Pro") from exc
        result = _safe_flow_result(payload)
        operation.update(
            {
                "status": "completed" if result.get("ok") is True else "failed",
                "result": result,
            }
        )
        _write_json_atomic(operation_path, operation)
        return result

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        }
    )
    async def flow_generate_video(
        prompt: str,
        start_image_media_id: str,
        request_key: str,
        confirmation: str,
        orientation: str = "PORTRAIT",
        scene_id: str = "",
    ) -> dict[str, Any]:
        """Generate one Veo clip from a Flow media id; local file paths are forbidden."""

        _require_write_confirmation(confirmation)
        safe_prompt = _public_team_input(
            prompt,
            field="prompt",
            limit=MAX_PROMPT_TEXT,
        )
        if len(safe_prompt) < 10:
            raise ValueError("prompt must contain at least 10 characters")
        safe_media_id = _validated_media_id(start_image_media_id)
        safe_scene_id = _validated_media_id(scene_id, required=False)
        safe_orientation = str(orientation or "").strip().upper()
        if safe_orientation not in ALLOWED_ORIENTATIONS:
            raise ValueError("Unsupported video orientation")
        safe_request_key = _validated_request_key(request_key)
        fingerprint_payload = {
            "prompt": safe_prompt,
            "orientation": safe_orientation,
            "start_image_media_id": safe_media_id,
            "scene_id": safe_scene_id,
        }
        existing = _existing_flow_operation(
            "flow-video",
            safe_request_key,
            fingerprint_payload,
        )
        if existing is not None:
            result = existing.get("result")
            return result if isinstance(result, dict) else {"ok": False, "status": "pending"}
        preflight_failure = await _flow_preflight()
        if preflight_failure is not None:
            return preflight_failure
        operation_path, operation, created = _claim_flow_operation(
            "flow-video",
            safe_request_key,
            fingerprint_payload,
        )
        if not created:
            result = operation.get("result")
            return result if isinstance(result, dict) else {"ok": False, "status": "pending"}
        args = [
            "generate-video",
            "--prompt",
            safe_prompt,
            "--orientation",
            safe_orientation,
            "--project",
            FLOW_PROJECT_NAME,
            "--paygate-tier",
            FLOW_PAYGATE_TIER,
            "--start-image-media-id",
            safe_media_id,
        ]
        if safe_scene_id:
            args.extend(["--scene-id", safe_scene_id])
        try:
            payload = await _run_flowkit_cli(args, timeout_s=780)
        except asyncio.CancelledError:
            operation.update(
                {
                    "status": "cancelled",
                    "result": {"ok": False, "status": "cancelled"},
                }
            )
            _write_json_atomic(operation_path, operation)
            raise
        except Exception as exc:
            operation.update(
                {
                    "status": "failed",
                    "result": {"ok": False, "status": "failed"},
                }
            )
            _write_json_atomic(operation_path, operation)
            raise RuntimeError("Flow video generation failed on Pro") from exc
        result = _safe_flow_result(payload)
        operation.update(
            {
                "status": "completed" if result.get("ok") is True else "failed",
                "result": result,
            }
        )
        _write_json_atomic(operation_path, operation)
        return result
