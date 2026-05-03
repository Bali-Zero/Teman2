"""
Portal RBAC — defensive layer.

Organo: backend-rag / portal services
  → consuma: ClientContext passato dal router portal (già validato da
    `backend.app.routers.portal.get_current_client`)
  → produce: PortalAccessDenied quando il `client_id` di un metodo
    non coincide col `client_id` autoritativo del requester

Audit 2026-04-18 HIGH-6.

**Perché esiste questo modulo (difesa in profondità):**

Il gate primario resta il router: `get_current_client` risolve il
`client_id` dal JWT/cookie e lo passa come primo positional ai metodi
del PortalService. Un'eventuale regressione futura del router (p.es.
un nuovo endpoint che accetta `?client_id=` dalla query) potrebbe
permettere a un cliente di leggere i dati di un altro. Questo
decorator riapplica il controllo *dentro* il service, così anche se
il router sbaglia, il service nega.

**Contract:**
- Ogni metodo pubblico del PortalService che legge/scrive dati
  scoped-a-un-cliente prende `client_id: int` come primo positional e
  `current_user: ClientContext` come kwarg.
- Il router portal passa sempre `current_user=client` (dove `client`
  è il dict emesso da `get_current_client`).
- Il decorator confronta `current_user["client_id"]` con `client_id`:
  match o impersonation esplicita → pass; mismatch → PortalAccessDenied.
- `current_user=None` è un **errore di programmazione**: il decorator
  solleva AuthRequired con un messaggio chiaro così il test fallisce
  in sviluppo invece di aprire un buco in produzione.
"""

from __future__ import annotations

import functools
import inspect
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypedDict, TypeVar, cast

from backend.core.exceptions import PortalAccessDenied, UnauthorizedError

logger = logging.getLogger(__name__)

__all__ = [
    "ClientContext",
    "require_client_access",
    "PortalAuthRequired",
]


class ClientContext(TypedDict, total=False):
    """
    Shape of the `current_user` kwarg passed from the portal router to the
    service layer. Mirrors what `get_current_client` returns.

    Required keys:
        client_id: int — the client being viewed (may be an impersonation target)
        email:     str — actor email (used for audit only)

    Optional keys:
        impersonating: bool — True when a superuser views another client's data
        user_id:       str — requester's team_members.id
        name:          str — display name
    """

    client_id: int
    email: str
    impersonating: bool
    user_id: str
    name: str


class PortalAuthRequired(UnauthorizedError):
    """
    Raised when a decorated service method is called without `current_user`.

    Distinct from :class:`PortalAccessDenied`: this signals a programming
    error (a caller forgot to pass the kwarg) rather than a denied access.
    The router layer MUST always pass `current_user=`; failing loudly here
    keeps the RBAC invariant auditable.
    """

    def __init__(self, method: str) -> None:
        super().__init__(
            f"Portal service method '{method}' requires a current_user kwarg; "
            "router layer did not supply it. This is a programming error — "
            "fix the caller instead of suppressing this exception.",
            details={"method": method},
        )
        self.method = method


F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


def _extract_client_id(
    bound_args: inspect.BoundArguments,
    method_name: str,
) -> int:
    """Pull the `client_id` argument out of a bound call."""
    if "client_id" not in bound_args.arguments:
        raise TypeError(
            f"require_client_access: '{method_name}' must declare "
            f"'client_id' as a parameter",
        )
    raw = bound_args.arguments["client_id"]
    if not isinstance(raw, int) or isinstance(raw, bool):
        raise TypeError(
            f"require_client_access: '{method_name}' got non-int client_id "
            f"({type(raw).__name__}={raw!r}); route arg parsing regressed",
        )
    return raw


def require_client_access(func: F) -> F:
    """
    Enforce that the decorated async method is called with a `current_user`
    kwarg whose `client_id` matches the `client_id` positional argument
    (or who is explicitly impersonating).

    Usage::

        class PortalDashboardMixin:
            @require_client_access
            async def get_dashboard(
                self,
                client_id: int,
                *,
                current_user: ClientContext,
            ) -> dict[str, Any]: ...

    The router then calls::

        await portal_service.get_dashboard(
            client["client_id"],
            current_user=client,
        )

    If the router forgets `current_user=` → PortalAuthRequired.
    If `current_user["client_id"] != client_id` and not impersonating →
    PortalAccessDenied.
    """
    signature = inspect.signature(func)

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        method_name = f"{func.__module__}.{func.__qualname__}"
        bound = signature.bind_partial(*args, **kwargs)

        current_user: ClientContext | None = bound.arguments.get("current_user")
        if current_user is None:
            raise PortalAuthRequired(method_name)

        target_client_id = _extract_client_id(bound, method_name)
        actor_client_id = current_user.get("client_id")
        actor_email = current_user.get("email")
        impersonating = bool(current_user.get("impersonating", False))

        if actor_client_id is None:
            raise PortalAuthRequired(method_name)

        if impersonating:
            # Impersonation was already vetted at the router layer (superuser
            # check + audit log written in portal.get_current_client). We only
            # require that the impersonation target == the method's client_id
            # so that a superuser can't pass as_client=A and then query data
            # for an unrelated client_id=B in the same request.
            if actor_client_id != target_client_id:
                logger.warning(
                    "portal_rbac.impersonation_mismatch",
                    extra={
                        "actor_email": actor_email,
                        "actor_client_id": actor_client_id,
                        "target_client_id": target_client_id,
                        "method": method_name,
                    },
                )
                raise PortalAccessDenied(
                    target_client_id,
                    actor_email=actor_email,
                    actor_client_id=actor_client_id,
                    method=method_name,
                )
            return await func(*args, **kwargs)

        if actor_client_id != target_client_id:
            logger.warning(
                "portal_rbac.access_denied",
                extra={
                    "actor_email": actor_email,
                    "actor_client_id": actor_client_id,
                    "target_client_id": target_client_id,
                    "method": method_name,
                },
            )
            raise PortalAccessDenied(
                target_client_id,
                actor_email=actor_email,
                actor_client_id=actor_client_id,
                method=method_name,
            )

        return await func(*args, **kwargs)

    return cast(F, wrapper)
