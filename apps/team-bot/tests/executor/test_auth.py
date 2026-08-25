from __future__ import annotations

from team_bot.executor.auth import AuthMaterial, NullTokenProvider


def test_null_token_provider_resolves_nothing_for_anyone() -> None:
    provider = NullTokenProvider()
    assert provider.resolve("USR-001") is None
    assert provider.resolve("anyone-at-all") is None


def test_auth_material_carries_headers_verbatim() -> None:
    material = AuthMaterial(headers={"Authorization": "Bearer x"})
    assert material.headers == {"Authorization": "Bearer x"}
