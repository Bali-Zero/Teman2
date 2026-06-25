"""Readiness checks for the local-first voice concierge audio stack."""

from __future__ import annotations

import http.client
import importlib.util
import json
import os
import socket
import sys
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from backend.app.services.local_audio import LOCAL_ONLY_PROVIDER_POLICY, ProviderStatus
from backend.app.services.local_audio.chatterbox import (
    ChatterboxTTSProvider,
    _find_local_huggingface_checkpoint,
    _missing_checkpoint_files,
)
from backend.app.services.local_audio.runtime_checks import (
    MIN_CHATTERBOX_JSON_BYTES,
    MIN_CHATTERBOX_WEIGHT_BYTES,
    MIN_WHISPER_MODEL_BYTES,
    VOICE_RUNTIME_HOSTS,
    check_whisper_binary_path,
    check_whisper_model_path,
    check_whisper_model_quality,
    invalid_chatterbox_checkpoint_files,
    normalize_hostname,
)
from backend.app.services.local_audio.silero_vad import SileroVADProvider
from backend.app.services.local_audio.whisper_cpp import WhisperCppSTTProvider

ReadinessMode = Literal["static", "deep"]
CheckStatus = Literal["pass", "warn", "fail"]

OFFLINE_ENV_GUARDS = {
    "DO_NOT_TRACK": "1",
    "HF_DATASETS_OFFLINE": "1",
    "HF_HUB_DISABLE_TELEMETRY": "1",
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
}
TTS_PROFILE_HIGH_QUALITY = "high_quality_offline"
TTS_PROFILE_BROWSER_REALTIME = "browser_realtime"
CHATTERBOX_TTS_PROVIDER_NAME = "chatterbox-v3"
TTS_PROFILE_ALIASES = {
    "high-quality": TTS_PROFILE_HIGH_QUALITY,
    "high-quality-offline": TTS_PROFILE_HIGH_QUALITY,
    "high_quality": TTS_PROFILE_HIGH_QUALITY,
    "high_quality_offline": TTS_PROFILE_HIGH_QUALITY,
    "offline": TTS_PROFILE_HIGH_QUALITY,
    "browser-realtime": TTS_PROFILE_BROWSER_REALTIME,
    "browser_realtime": TTS_PROFILE_BROWSER_REALTIME,
    "realtime": TTS_PROFILE_BROWSER_REALTIME,
}


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    status: CheckStatus
    detail: str
    metadata: dict[str, str | int | float | bool | None] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class ReadinessReport:
    mode: ReadinessMode
    ok: bool
    machine: str
    checks: list[ReadinessCheck]
    constraints: list[str]

    def check(self, name: str) -> ReadinessCheck:
        for item in self.checks:
            if item.name == name:
                return item
        raise KeyError(name)

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "ok": self.ok,
            "machine": self.machine,
            "constraints": self.constraints,
            "checks": [check.to_dict() for check in self.checks],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def format_text(self) -> str:
        lines = [
            f"local audio readiness: {'OK' if self.ok else 'FAILED'}",
            f"mode: {self.mode}",
            f"machine: {self.machine}",
        ]
        for check in self.checks:
            lines.append(f"[{check.status.upper()}] {check.name}: {check.detail}")
        return "\n".join(lines)


@dataclass(frozen=True)
class _LiveKitWorkerHealth:
    ok: bool
    detail: str
    status_code: int | None = None


def build_local_audio_readiness_report(
    *,
    mode: ReadinessMode = "static",
    settings: Any | None = None,
    hostname: str | None = None,
    python_prefix: str | None = None,
    python_base_prefix: str | None = None,
) -> ReadinessReport:
    """Build a local audio readiness report.

    Static mode validates configuration, files, imports, and policy without
    loading models. Deep mode is gated to Pro/Mini and may instantiate runtime
    provider status checks.
    """
    if mode not in ("static", "deep"):
        raise ValueError("mode must be 'static' or 'deep'")

    runtime_settings = settings or _load_settings()
    machine = hostname or socket.gethostname()
    prefix = python_prefix if python_prefix is not None else sys.prefix
    base_prefix = python_base_prefix if python_base_prefix is not None else sys.base_prefix

    if mode == "deep" and normalize_hostname(machine) not in VOICE_RUNTIME_HOSTS:
        checks = [
            _host_check(mode=mode, hostname=machine),
            _venv_check(python_prefix=prefix, python_base_prefix=base_prefix),
            _provider_policy_check(),
            ReadinessCheck(
                name="deep_runtime_gate",
                status="fail",
                detail="deep runtime checks are allowed only on Pro/Mini voice hosts",
            ),
        ]
        return _report(mode=mode, machine=machine, checks=checks)

    checks = _build_static_checks(
        mode=mode,
        settings=runtime_settings,
        hostname=machine,
        python_prefix=prefix,
        python_base_prefix=base_prefix,
    )

    static_failed = _has_static_blocking_failure(checks)
    if mode == "deep":
        if static_failed:
            checks.append(
                ReadinessCheck(
                    name="deep_static_gate",
                    status="fail",
                    detail="static readiness failed; runtime warm checks skipped",
                ),
            )
        else:
            checks.extend(_build_deep_checks(runtime_settings))

    return _report(mode=mode, machine=machine, checks=checks)


def _report(
    *,
    mode: ReadinessMode,
    machine: str,
    checks: list[ReadinessCheck],
) -> ReadinessReport:
    return ReadinessReport(
        mode=mode,
        ok=not _has_failure(checks),
        machine=machine,
        checks=checks,
        constraints=[
            "local_only_audio",
            "no_cloud_fallback",
            "pii_boundary_local_only",
            "deep_runtime_checks_pro_mini_only",
            "livekit_agent_required_for_production",
        ],
    )


def _load_settings() -> Any:
    from backend.app.core.config import settings

    return settings


def _build_static_checks(
    *,
    mode: ReadinessMode,
    settings: Any,
    hostname: str,
    python_prefix: str,
    python_base_prefix: str,
) -> list[ReadinessCheck]:
    checks = [
        _host_check(mode=mode, hostname=hostname),
        _venv_check(python_prefix=python_prefix, python_base_prefix=python_base_prefix),
        _local_audio_enabled_check(settings),
        _provider_policy_check(),
        _tts_profile_check(settings),
        _capacity_limits_check(settings),
        _whisper_binary_check(settings),
        _whisper_model_check(settings),
        _whisper_model_quality_check(settings),
        _positive_timeout_check(
            "whisper_timeout",
            _get_float(settings, "voice_concierge_whisper_timeout_seconds"),
        ),
        _silero_import_check(settings),
        _silero_config_check(settings),
        _chatterbox_import_check(settings),
        _chatterbox_dependency_check("soundfile"),
        _chatterbox_dependency_check("torch"),
        _chatterbox_checkpoint_check(settings),
        _chatterbox_config_check(settings),
        _offline_env_check(mode),
        _livekit_agent_check(mode, settings),
    ]
    return checks


def _build_deep_checks(settings: Any) -> list[ReadinessCheck]:
    checks: list[ReadinessCheck] = []

    binary_path = _path_or_none(_get_str(settings, "voice_concierge_whisper_binary"))
    model_path = _path_or_none(_get_str(settings, "voice_concierge_whisper_model"))
    if binary_path is not None and model_path is not None:
        checks.append(
            _provider_status_check(
                name="deep_whisper_status",
                status=WhisperCppSTTProvider(
                    binary_path=binary_path,
                    model_path=model_path,
                    timeout_seconds=_get_float(
                        settings,
                        "voice_concierge_whisper_timeout_seconds",
                    ),
                ).warm_status(),
            ),
        )

    checks.append(
        _provider_status_check(
            name="deep_silero_status",
            status=SileroVADProvider(
                module_name=_get_str(settings, "voice_concierge_silero_module") or "silero_vad",
                sampling_rate=_get_int(settings, "voice_concierge_silero_sampling_rate"),
                threshold=_get_float(settings, "voice_concierge_silero_threshold"),
                timeout_seconds=_get_float(settings, "voice_concierge_silero_timeout_seconds"),
            ).warm_status(),
        ),
    )
    checks.append(
        _provider_status_check(
            name="deep_chatterbox_status",
            status=ChatterboxTTSProvider(
                module_name=_get_str(settings, "voice_concierge_chatterbox_module") or "chatterbox",
                model_path=_path_or_none(
                    _get_str(settings, "voice_concierge_chatterbox_model_path"),
                ),
                t3_model=_get_str(settings, "voice_concierge_chatterbox_t3_model") or "v3",
                language_id=_get_str(settings, "voice_concierge_chatterbox_language") or "en",
                timeout_seconds=_get_float(
                    settings,
                    "voice_concierge_chatterbox_timeout_seconds",
                ),
            ).warm_status(),
        ),
    )
    return checks


def _host_check(*, mode: ReadinessMode, hostname: str) -> ReadinessCheck:
    normalized_hostname = normalize_hostname(hostname)
    if normalized_hostname in VOICE_RUNTIME_HOSTS:
        return ReadinessCheck(
            name="host_role",
            status="pass",
            detail=f"{normalized_hostname} is an approved local audio runtime host",
            metadata={"hostname": hostname, "normalized_hostname": normalized_hostname},
        )
    if mode == "deep":
        return ReadinessCheck(
            name="host_role",
            status="fail",
            detail=f"{hostname} is not approved for deep local audio runtime checks",
            metadata={"hostname": hostname, "normalized_hostname": normalized_hostname},
        )
    return ReadinessCheck(
        name="host_role",
        status="warn",
        detail=f"{hostname} can run static checks only; real runtime belongs on Pro/Mini",
        metadata={"hostname": hostname, "normalized_hostname": normalized_hostname},
    )


def _venv_check(*, python_prefix: str, python_base_prefix: str) -> ReadinessCheck:
    active = python_prefix != python_base_prefix
    return ReadinessCheck(
        name="virtualenv",
        status="pass" if active else "warn",
        detail="virtualenv active" if active else "virtualenv not detected",
    )


def _local_audio_enabled_check(settings: Any) -> ReadinessCheck:
    enabled = bool(
        getattr(settings, "voice_concierge_local_audio_enabled", False)
        or getattr(settings, "voice_concierge_local_audio", False)
    )
    return ReadinessCheck(
        name="local_audio_enabled",
        status="pass" if enabled else "fail",
        detail="local audio flag enabled" if enabled else "local audio flag disabled",
        metadata={"enabled": enabled},
    )


def _provider_policy_check() -> ReadinessCheck:
    policy = LOCAL_ONLY_PROVIDER_POLICY
    ok = (
        policy.requires_network is False
        and policy.allows_cloud_fallback is False
        and policy.pii_boundary == "local_only"
    )
    return ReadinessCheck(
        name="provider_policy",
        status="pass" if ok else "fail",
        detail="providers are local-only" if ok else "provider policy allows remote escape hatch",
        metadata={
            "requires_network": policy.requires_network,
            "allows_cloud_fallback": policy.allows_cloud_fallback,
            "pii_boundary": policy.pii_boundary,
        },
    )


def _tts_profile_check(settings: Any) -> ReadinessCheck:
    raw_value = _get_str(settings, "voice_concierge_tts_profile") or TTS_PROFILE_HIGH_QUALITY
    normalized = _normalize_tts_profile(raw_value)
    if normalized is None:
        return ReadinessCheck(
            name="tts_profile",
            status="fail",
            detail="VOICE_CONCIERGE_TTS_PROFILE must be high_quality_offline or browser_realtime",
            metadata={"configured": raw_value},
        )
    provider = (
        CHATTERBOX_TTS_PROVIDER_NAME
        if normalized == TTS_PROFILE_HIGH_QUALITY
        else (
            _get_str(settings, "voice_concierge_realtime_tts_provider")
            or "browser-web-speech-local"
        )
    )
    return ReadinessCheck(
        name="tts_profile",
        status="pass",
        detail=f"active TTS profile {normalized} uses {provider}",
        metadata={
            "active_profile": normalized,
            "active_provider": provider,
            "fallback_policy": "fail_closed",
            "pii_boundary": "local_only",
        },
    )


def _capacity_limits_check(settings: Any) -> ReadinessCheck:
    values = {
        "audio_max_bytes": _get_int(settings, "voice_concierge_audio_max_bytes"),
        "tts_max_chars": _get_int(settings, "voice_concierge_tts_max_chars"),
        "tts_audio_max_bytes": _get_int(settings, "voice_concierge_tts_audio_max_bytes"),
    }
    invalid = [name for name, value in values.items() if value <= 0]
    return ReadinessCheck(
        name="capacity_limits",
        status="fail" if invalid else "pass",
        detail=f"invalid positive limits: {', '.join(invalid)}"
        if invalid
        else "capacity caps are positive",
        metadata=values,
    )


def _normalize_tts_profile(raw_value: str) -> str | None:
    value = raw_value.strip().lower().replace(" ", "_")
    return TTS_PROFILE_ALIASES.get(value)


def _whisper_binary_check(settings: Any) -> ReadinessCheck:
    value = _get_str(settings, "voice_concierge_whisper_binary")
    path = _path_or_none(value)
    if path is None:
        return ReadinessCheck(
            name="whisper_binary",
            status="fail",
            detail="VOICE_CONCIERGE_WHISPER_BINARY is not configured",
        )
    check = check_whisper_binary_path(path)
    if not check.ok:
        return ReadinessCheck(
            name="whisper_binary",
            status="fail",
            detail=f"whisper.cpp {check.detail}",
            metadata=check.metadata,
        )
    return ReadinessCheck(
        name="whisper_binary",
        status="pass",
        detail=check.detail,
        metadata=check.metadata,
    )


def _whisper_model_check(settings: Any) -> ReadinessCheck:
    path = _path_or_none(_get_str(settings, "voice_concierge_whisper_model"))
    if path is None:
        return ReadinessCheck(
            name="whisper_model",
            status="fail",
            detail="VOICE_CONCIERGE_WHISPER_MODEL is not configured",
        )
    check = check_whisper_model_path(path)
    if not check.ok:
        return ReadinessCheck(
            name="whisper_model",
            status="fail",
            detail=f"whisper.cpp {check.detail}",
            metadata=check.metadata,
        )
    return ReadinessCheck(
        name="whisper_model",
        status="pass",
        detail=check.detail,
        metadata=check.metadata,
    )


def _whisper_model_quality_check(settings: Any) -> ReadinessCheck:
    path = _path_or_none(_get_str(settings, "voice_concierge_whisper_model"))
    if path is None:
        return ReadinessCheck(
            name="whisper_model_quality",
            status="fail",
            detail="whisper model path unavailable; expected large-v3-turbo",
        )
    check = check_whisper_model_quality(path)
    if not check.ok:
        return ReadinessCheck(
            name="whisper_model_quality",
            status="fail",
            detail=f"whisper {check.detail}",
            metadata=check.metadata,
        )
    return ReadinessCheck(
        name="whisper_model_quality",
        status="pass",
        detail=check.detail,
        metadata=check.metadata,
    )


def _silero_import_check(settings: Any) -> ReadinessCheck:
    module_name = _get_str(settings, "voice_concierge_silero_module") or "silero_vad"
    return _module_spec_check("silero_import", module_name)


def _silero_config_check(settings: Any) -> ReadinessCheck:
    sampling_rate = _get_int(settings, "voice_concierge_silero_sampling_rate")
    threshold = _get_float(settings, "voice_concierge_silero_threshold")
    timeout = _get_float(settings, "voice_concierge_silero_timeout_seconds")
    invalid: list[str] = []
    if sampling_rate not in (8000, 16000):
        invalid.append("sampling_rate")
    if threshold <= 0 or threshold >= 1:
        invalid.append("threshold")
    if timeout <= 0:
        invalid.append("timeout_seconds")
    return ReadinessCheck(
        name="silero_config",
        status="fail" if invalid else "pass",
        detail=f"invalid Silero config: {', '.join(invalid)}" if invalid else "Silero config valid",
        metadata={
            "sampling_rate": sampling_rate,
            "threshold": threshold,
            "timeout_seconds": timeout,
        },
    )


def _chatterbox_import_check(settings: Any) -> ReadinessCheck:
    module_name = _get_str(settings, "voice_concierge_chatterbox_module") or "chatterbox"
    base_check = _module_spec_check("chatterbox_import", module_name)
    if base_check.status != "pass":
        return base_check
    return _module_spec_check("chatterbox_import", f"{module_name}.mtl_tts")


def _chatterbox_dependency_check(module_name: str) -> ReadinessCheck:
    return _module_spec_check(f"chatterbox_dependency_{module_name}", module_name)


def _chatterbox_checkpoint_check(settings: Any) -> ReadinessCheck:
    t3_model = _get_str(settings, "voice_concierge_chatterbox_t3_model") or "v3"
    configured_path = _path_or_none(_get_str(settings, "voice_concierge_chatterbox_model_path"))
    model_path = configured_path or _find_local_huggingface_checkpoint(t3_model)
    if model_path is None:
        return ReadinessCheck(
            name="chatterbox_checkpoint",
            status="fail",
            detail="Chatterbox checkpoint not configured and local HuggingFace snapshot not found",
        )
    missing = _missing_checkpoint_files(model_path, t3_model)
    if missing:
        return ReadinessCheck(
            name="chatterbox_checkpoint",
            status="fail",
            detail=f"Chatterbox checkpoint incomplete: {missing[0]}",
            metadata={"model_path": str(model_path)},
        )
    invalid_files = invalid_chatterbox_checkpoint_files(model_path, t3_model)
    if invalid_files:
        return ReadinessCheck(
            name="chatterbox_checkpoint",
            status="fail",
            detail=f"Chatterbox checkpoint file is not plausible: {invalid_files[0]}",
            metadata={"model_path": str(model_path)},
        )
    return ReadinessCheck(
        name="chatterbox_checkpoint",
        status="pass",
        detail=f"Chatterbox checkpoint ready: {model_path}",
        metadata={"model_path": str(model_path)},
    )


def _chatterbox_config_check(settings: Any) -> ReadinessCheck:
    t3_model = _get_str(settings, "voice_concierge_chatterbox_t3_model")
    language = _get_str(settings, "voice_concierge_chatterbox_language")
    timeout = _get_float(settings, "voice_concierge_chatterbox_timeout_seconds")
    invalid: list[str] = []
    if not t3_model:
        invalid.append("t3_model")
    if not language:
        invalid.append("language")
    if timeout <= 0:
        invalid.append("timeout_seconds")
    return ReadinessCheck(
        name="chatterbox_config",
        status="fail" if invalid else "pass",
        detail=f"invalid Chatterbox config: {', '.join(invalid)}"
        if invalid
        else "Chatterbox config valid",
        metadata={
            "t3_model": t3_model,
            "language": language,
            "timeout_seconds": timeout,
        },
    )


def _offline_env_check(mode: ReadinessMode) -> ReadinessCheck:
    missing_or_wrong = [
        key for key, expected in OFFLINE_ENV_GUARDS.items() if os.environ.get(key) != expected
    ]
    if missing_or_wrong:
        return ReadinessCheck(
            name="offline_env",
            status="fail" if mode == "deep" else "warn",
            detail=f"offline guard env missing or mismatched: {', '.join(missing_or_wrong)}",
            metadata={key: os.environ.get(key) for key in OFFLINE_ENV_GUARDS},
        )
    return ReadinessCheck(
        name="offline_env",
        status="pass",
        detail="offline guard env is set",
        metadata=OFFLINE_ENV_GUARDS.copy(),
    )


def _livekit_agent_check(mode: ReadinessMode, settings: Any) -> ReadinessCheck:
    health_url = _get_str(settings, "voice_concierge_livekit_worker_health_url")
    timeout_seconds = _get_float_default(
        settings,
        "voice_concierge_livekit_worker_timeout_seconds",
        3.0,
    )
    if timeout_seconds <= 0:
        return ReadinessCheck(
            name="livekit_agent",
            status="fail",
            detail="LiveKit worker health timeout must be positive",
            metadata={"timeout_seconds": timeout_seconds},
        )
    if health_url is None or not health_url.strip():
        return ReadinessCheck(
            name="livekit_agent",
            status="fail" if mode == "deep" else "warn",
            detail="VOICE_CONCIERGE_LIVEKIT_WORKER_HEALTH_URL is not configured",
            metadata={"configured": False, "timeout_seconds": timeout_seconds},
        )

    sanitized_url = _sanitize_livekit_health_url(health_url)
    if sanitized_url is None:
        return ReadinessCheck(
            name="livekit_agent",
            status="fail",
            detail="LiveKit worker health URL must be an http(s) URL with a host",
            metadata={"configured": True, "timeout_seconds": timeout_seconds},
        )

    metadata: dict[str, str | int | float | bool | None] = {
        "configured": True,
        "health_url": sanitized_url,
        "timeout_seconds": timeout_seconds,
    }
    if mode == "static":
        return ReadinessCheck(
            name="livekit_agent",
            status="pass",
            detail="LiveKit worker health URL configured",
            metadata=metadata,
        )

    health = _fetch_livekit_worker_health(health_url.strip(), timeout_seconds)
    if health.status_code is not None:
        metadata["status_code"] = health.status_code
    return ReadinessCheck(
        name="livekit_agent",
        status="pass" if health.ok else "fail",
        detail=health.detail,
        metadata=metadata,
    )


def _sanitize_livekit_health_url(health_url: str) -> str | None:
    parsed = urllib.parse.urlsplit(health_url.strip())
    try:
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
    ):
        return None
    path = parsed.path or "/"
    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    netloc = f"{host}:{port}" if port is not None else host
    return urllib.parse.urlunsplit((parsed.scheme, netloc, path, "", ""))


def _fetch_livekit_worker_health(
    health_url: str,
    timeout_seconds: float,
) -> _LiveKitWorkerHealth:
    parsed = urllib.parse.urlsplit(health_url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
        return _LiveKitWorkerHealth(
            ok=False,
            detail="LiveKit worker health URL is invalid",
        )
    try:
        port = parsed.port
    except ValueError:
        return _LiveKitWorkerHealth(
            ok=False,
            detail="LiveKit worker health URL is invalid",
        )
    connection_class = (
        http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    )
    request_target = urllib.parse.urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
    connection = connection_class(
        parsed.hostname,
        port=port,
        timeout=timeout_seconds,
    )
    try:
        connection.request(
            "GET",
            request_target,
            headers={
                "Accept": "application/json,text/plain,*/*",
                "User-Agent": "nuzantara-local-audio-doctor/1.0",
            },
        )
        response = connection.getresponse()
        status_code = int(response.status)
    except TimeoutError:
        return _LiveKitWorkerHealth(
            ok=False,
            detail="LiveKit worker health request timed out",
        )
    except (http.client.HTTPException, OSError, ValueError) as exc:
        return _LiveKitWorkerHealth(
            ok=False,
            detail=f"LiveKit worker health request failed: {type(exc).__name__}",
        )
    finally:
        connection.close()

    if 200 <= status_code < 300:
        return _LiveKitWorkerHealth(
            ok=True,
            detail=f"LiveKit worker health returned HTTP {status_code}",
            status_code=status_code,
        )
    return _LiveKitWorkerHealth(
        ok=False,
        detail=f"LiveKit worker health returned HTTP {status_code}",
        status_code=status_code,
    )


def _positive_timeout_check(name: str, timeout_seconds: float) -> ReadinessCheck:
    return ReadinessCheck(
        name=name,
        status="pass" if timeout_seconds > 0 else "fail",
        detail="timeout is positive" if timeout_seconds > 0 else "timeout must be positive",
        metadata={"timeout_seconds": timeout_seconds},
    )


def _provider_status_check(*, name: str, status: ProviderStatus) -> ReadinessCheck:
    return ReadinessCheck(
        name=name,
        status="pass" if status.available else "fail",
        detail=status.detail,
        metadata={
            "provider": status.name,
            "requires_network": status.policy.requires_network,
            "allows_cloud_fallback": status.policy.allows_cloud_fallback,
            "pii_boundary": status.policy.pii_boundary,
        },
    )


def _module_spec_check(name: str, module_name: str) -> ReadinessCheck:
    try:
        spec = importlib.util.find_spec(module_name)
    except BaseException as exc:
        return ReadinessCheck(
            name=name,
            status="fail",
            detail=f"module spec lookup failed for {module_name}: {type(exc).__name__}",
            metadata={"module": module_name},
        )
    if spec is None:
        return ReadinessCheck(
            name=name,
            status="fail",
            detail=f"module not found: {module_name}",
            metadata={"module": module_name},
        )
    return ReadinessCheck(
        name=name,
        status="pass",
        detail=f"module import spec found: {module_name}",
        metadata={"module": module_name},
    )


def _path_or_none(value: str | None) -> Path | None:
    if value is None or not value.strip():
        return None
    return Path(value).expanduser()


def _get_str(settings: Any, name: str) -> str | None:
    value = getattr(settings, name, None)
    if value is None:
        return None
    return str(value)


def _get_int(settings: Any, name: str) -> int:
    value = getattr(settings, name)
    return int(value)


def _get_float(settings: Any, name: str) -> float:
    value = getattr(settings, name)
    return float(value)


def _get_float_default(settings: Any, name: str, default: float) -> float:
    value = getattr(settings, name, default)
    return float(value)


def _has_failure(checks: list[ReadinessCheck]) -> bool:
    return any(check.status == "fail" for check in checks)


def _has_static_blocking_failure(checks: list[ReadinessCheck]) -> bool:
    return any(check.status == "fail" for check in checks if check.name != "livekit_agent")


__all__ = [
    "MIN_CHATTERBOX_JSON_BYTES",
    "MIN_CHATTERBOX_WEIGHT_BYTES",
    "MIN_WHISPER_MODEL_BYTES",
    "OFFLINE_ENV_GUARDS",
    "VOICE_RUNTIME_HOSTS",
    "ReadinessCheck",
    "ReadinessReport",
    "build_local_audio_readiness_report",
]
