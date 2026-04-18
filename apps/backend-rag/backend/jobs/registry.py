"""Job registry: register_job() declarations at import time."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable, Mapping

from croniter import croniter

from backend.jobs.context import JobContext, JobResult
from backend.jobs.retry import DEFAULT_RETRY, RetryPolicy


class RegistryError(Exception):
    """Registry misconfiguration (duplicate, invalid cron, frozen, ...)."""


@dataclass(frozen=True)
class JobDeclaration:
    name: str
    cron: str
    handler: Callable[[JobContext], Awaitable[JobResult | None]]
    timezone: str = "Asia/Makassar"
    timeout_seconds: int = 300
    retry_policy: RetryPolicy = DEFAULT_RETRY
    skip_middleware: tuple[str, ...] = ()
    skip_reasons: Mapping[str, str] = field(default_factory=dict)
    idempotency_key: Callable[[JobContext], str] | None = None
    enabled_when: Callable[[], bool] | None = None


class Registry:
    def __init__(self) -> None:
        self._by_name: dict[str, JobDeclaration] = {}
        self._frozen = False

    def register(
        self,
        *,
        name: str,
        cron: str,
        handler: Callable[[JobContext], Awaitable[JobResult | None]],
        timezone: str = "Asia/Makassar",
        timeout_seconds: int = 300,
        retry_policy: RetryPolicy = DEFAULT_RETRY,
        skip_middleware: tuple[str, ...] = (),
        skip_reasons: Mapping[str, str] | None = None,
        idempotency_key: Callable[[JobContext], str] | None = None,
        enabled_when: Callable[[], bool] | None = None,
    ) -> None:
        if self._frozen:
            raise RegistryError("registry is frozen; cannot register more jobs")
        if name in self._by_name:
            raise RegistryError(f"job {name!r} already registered")
        if not croniter.is_valid(cron):
            raise RegistryError(f"invalid cron expression: {cron!r}")

        skip_reasons = dict(skip_reasons or {})
        for mw in skip_middleware:
            reason = skip_reasons.get(mw, "").strip()
            if not reason:
                raise RegistryError(
                    f"skip_middleware={mw!r} requires a non-empty "
                    f"skip_reasons[{mw!r}] (audit trail)"
                )

        self._by_name[name] = JobDeclaration(
            name=name,
            cron=cron,
            handler=handler,
            timezone=timezone,
            timeout_seconds=timeout_seconds,
            retry_policy=retry_policy,
            skip_middleware=tuple(skip_middleware),
            skip_reasons=skip_reasons,
            idempotency_key=idempotency_key,
            enabled_when=enabled_when,
        )

    def freeze(self) -> None:
        self._frozen = True

    def get(self, name: str) -> JobDeclaration:
        return self._by_name[name]

    def all(self) -> list[JobDeclaration]:
        return list(self._by_name.values())


_default = Registry()


def register_job(**kwargs) -> None:
    _default.register(**kwargs)


def get_registry() -> Registry:
    return _default
