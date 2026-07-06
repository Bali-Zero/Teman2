from __future__ import annotations

from typing import Any

import pytest

from backend.services.integrations import team_drive_service as team_module
from backend.services.integrations.team_drive_service import TeamDriveService


class FakeHttpClient:
    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


class FakeAuth:
    service_account_available = True

    async def get_access_token(self, user_id: str = "system") -> str:
        return f"token:{user_id}"

    async def get_user_allowed_folders(self, user_email: str) -> tuple[list[str], bool]:
        return [f"folder:{user_email}"], True


class FakeOperations:
    async def list_files(self, **kwargs: Any) -> dict[str, Any]:
        return {"method": "list_files", "kwargs": kwargs}

    async def get_file_metadata(self, **kwargs: Any) -> dict[str, Any]:
        return {"method": "get_file_metadata", "kwargs": kwargs}

    async def download_file(self, **kwargs: Any) -> bytes:
        return b"file-bytes"

    async def search_files(self, **kwargs: Any) -> list[dict[str, Any]]:
        return [{"method": "search_files", "kwargs": kwargs}]

    async def upload_file(self, **kwargs: Any) -> dict[str, Any]:
        return {"method": "upload_file", "kwargs": kwargs}

    async def create_folder(self, **kwargs: Any) -> dict[str, Any]:
        return {"method": "create_folder", "kwargs": kwargs}


class FakePermissions:
    async def list_permissions(self, **kwargs: Any) -> list[dict[str, Any]]:
        return [{"method": "list_permissions", "kwargs": kwargs}]

    async def add_permission(self, **kwargs: Any) -> dict[str, Any]:
        return {"method": "add_permission", "kwargs": kwargs}

    async def remove_permission(self, **kwargs: Any) -> dict[str, Any]:
        return {"method": "remove_permission", "kwargs": kwargs}


def make_service() -> TeamDriveService:
    service = TeamDriveService.__new__(TeamDriveService)
    service.db_pool = object()
    service.http_client = FakeHttpClient()
    service.auth = FakeAuth()
    service.operations = FakeOperations()
    service.permissions = FakePermissions()
    return service


def test_get_team_drive_service_constructs_facade(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[object] = []

    class FakeTeamDriveService:
        def __init__(self, db_pool: object) -> None:
            created.append(db_pool)

    monkeypatch.setattr(team_module, "TeamDriveService", FakeTeamDriveService)
    pool = object()

    service = team_module.get_team_drive_service(pool)

    assert isinstance(service, FakeTeamDriveService)
    assert created == [pool]


def test_configuration_flags_reflect_auth_manager_state() -> None:
    service = make_service()

    assert service.is_configured() is True
    assert service.service_account_available is True

    service.auth = None
    assert service.is_configured() is False
    assert service.service_account_available is False


@pytest.mark.asyncio
async def test_auth_methods_delegate_to_auth_manager() -> None:
    service = make_service()

    assert await service.get_access_token("user-1") == "token:user-1"
    assert await service.get_user_allowed_folders("zero@example.com") == (
        ["folder:zero@example.com"],
        True,
    )


@pytest.mark.asyncio
async def test_operation_methods_delegate_to_operations_manager() -> None:
    service = make_service()

    assert await service.list_files("user@example.com", folder_id="root") == {
        "method": "list_files",
        "kwargs": {
            "user_email": "user@example.com",
            "folder_id": "root",
            "q": None,
            "page_size": 50,
            "page_token": None,
        },
    }
    assert await service.get_file_metadata("user@example.com", "file-1") == {
        "method": "get_file_metadata",
        "kwargs": {"user_email": "user@example.com", "file_id": "file-1"},
    }
    assert await service.download_file("user@example.com", "file-1") == b"file-bytes"
    assert await service.search_files("user@example.com", "passport") == [
        {
            "method": "search_files",
            "kwargs": {
                "user_email": "user@example.com",
                "query": "passport",
                "file_type": None,
                "page_size": 20,
            },
        },
    ]


@pytest.mark.asyncio
async def test_mutating_operation_methods_delegate_to_operations_manager() -> None:
    service = make_service()

    assert (await service.upload_file("user@example.com", file="file", parent_id="root"))[
        "method"
    ] == "upload_file"
    assert (await service.create_folder("user@example.com", request={"name": "Docs"}))[
        "method"
    ] == "create_folder"


@pytest.mark.asyncio
async def test_permission_methods_delegate_to_permissions_manager() -> None:
    service = make_service()

    assert await service.list_permissions("user@example.com", "file-1") == [
        {
            "method": "list_permissions",
            "kwargs": {"user_email": "user@example.com", "file_id": "file-1"},
        },
    ]
    assert (await service.add_permission("user@example.com", "file-1", {"role": "reader"}))[
        "method"
    ] == "add_permission"
    assert (await service.remove_permission("user@example.com", "file-1", "perm-1"))[
        "method"
    ] == "remove_permission"


@pytest.mark.asyncio
async def test_close_closes_shared_http_client() -> None:
    service = make_service()

    await service.close()

    assert service.http_client.closed is True
