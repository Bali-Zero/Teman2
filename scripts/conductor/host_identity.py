"""Immutable, OS-derived identity for the local Conductor executor.

Dispatch payloads and environment variables are claims, not host evidence. The
only production observation exposed here comes from the kernel's effective UID
and the hostname returned by the local socket API.
"""

from __future__ import annotations

import os
import pwd
import socket
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


class HostIdentityError(RuntimeError):
    """The current process cannot be bound to one known fleet host."""


@dataclass(frozen=True, slots=True)
class HostIdentity:
    """A locally observed fleet identity which cannot be mutated by callers."""

    machine: str
    hostname: str
    username: str
    effective_uid: int = -1

    @property
    def fleet_label(self) -> str:
        """Return the control-plane display label without changing runtime IDs."""

        try:
            return {
                "pro": "Pro",
                "mini-pro2": "Mini-Pro2",
                "air-m5": "Air-M5",
            }[self.machine]
        except KeyError as error:
            raise HostIdentityError("local machine id is not canonical") from error


_FLEET_HOSTS: Mapping[str, tuple[str, str]] = MappingProxyType(
    {
        "nuzantara": ("pro", "nuzantara"),
        "mini-pro2": ("mini-pro2", "nuzantara"),
        "air-m5": ("air-m5", "balizero"),
    }
)


def canonical_hostname(raw: str) -> str:
    """Canonicalize the directly observed hostname without accepting aliases."""

    if not isinstance(raw, str) or "\x00" in raw:
        raise HostIdentityError("local hostname is invalid")
    hostname = raw.strip().lower()
    if hostname.endswith(".local"):
        hostname = hostname[: -len(".local")]
    if not hostname:
        raise HostIdentityError("local hostname is invalid")
    return hostname


def observe_local_host() -> HostIdentity:
    """Return one fresh kernel/account-database observation of the local host.

    ``USER``, ``LOGNAME``, ``HOME`` and any dispatch-supplied machine name are
    deliberately ignored. A renamed host or mismatched effective account is an
    abstention condition, never an invitation to infer the machine remotely.
    """

    hostname = canonical_hostname(socket.gethostname())
    expected = _FLEET_HOSTS.get(hostname)
    if expected is None:
        raise HostIdentityError("local host is outside the attested fleet")
    effective_uid = os.geteuid()
    try:
        username = pwd.getpwuid(effective_uid).pw_name
    except (KeyError, OSError) as error:
        raise HostIdentityError("effective user cannot be resolved") from error
    machine, expected_username = expected
    if username != expected_username:
        raise HostIdentityError("local hostname and effective user disagree")
    return HostIdentity(
        machine=machine,
        hostname=hostname,
        username=username,
        effective_uid=effective_uid,
    )


__all__ = [
    "HostIdentity",
    "HostIdentityError",
    "canonical_hostname",
    "observe_local_host",
]
