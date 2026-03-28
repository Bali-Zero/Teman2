"""
CRM Migration Status Tracking

Real-time monitoring and statistics for bulk data migrations.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from backend.app.dependencies import get_current_user, get_database_pool

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/migration/status")
async def get_migration_status(
    pool=Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Get comprehensive migration status and statistics.

    Returns real-time stats about:
    - Total clients in database
    - Clients with/without Google Drive folders
    - Total documents
    - Documents by category
    - Storage breakdown

    Returns:
        {
            "clients": {
                "total": 50,
                "with_drive_folder": 35,
                "without_drive_folder": 15,
                "by_type": {"individual": 30, "company": 20}
            },
            "documents": {
                "total": 1234,
                "by_category": {...},
                "by_storage": {...}
            },
            "storage": {
                "total_size_gb": 280.5
            },
            "timestamp": "2026-01-14T10:00:00Z"
        }
    """
    async with pool.acquire() as conn:
        # Client statistics
        client_stats = await conn.fetchrow(
            """
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE google_drive_folder_id IS NOT NULL) as with_drive_folder,
                COUNT(*) FILTER (WHERE google_drive_folder_id IS NULL) as without_drive_folder,
                COUNT(*) FILTER (WHERE client_type = 'individual') as individuals,
                COUNT(*) FILTER (WHERE client_type = 'company') as companies
            FROM clients
            """,
        )

        # Document statistics
        doc_stats = await conn.fetchrow(
            """
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE document_category = 'immigration') as immigration,
                COUNT(*) FILTER (WHERE document_category = 'pma') as pma,
                COUNT(*) FILTER (WHERE document_category = 'tax') as tax,
                COUNT(*) FILTER (WHERE document_category = 'personal') as personal,
                COUNT(*) FILTER (WHERE document_category = 'other') as other,
                COUNT(*) FILTER (WHERE storage_type = 'google_drive') as google_drive,
                COUNT(*) FILTER (WHERE storage_type = 'dropbox') as dropbox,
                COUNT(*) FILTER (WHERE storage_type = 'local') as local_storage
            FROM documents
            """,
        )

        # Recently created clients (migration activity indicator)
        recent_clients = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM clients
            WHERE created_at >= NOW() - INTERVAL '24 hours'
            """,
        )

        # Recently uploaded documents (migration activity indicator)
        recent_documents = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM documents
            WHERE uploaded_at >= NOW() - INTERVAL '24 hours'
            """,
        )

        # Clients awaiting folder creation
        pending_folder_creation = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM clients
            WHERE google_drive_folder_id IS NULL
            """,
        )

    return {
        "clients": {
            "total": client_stats["total"],
            "with_drive_folder": client_stats["with_drive_folder"],
            "without_drive_folder": client_stats["without_drive_folder"],
            "by_type": {
                "individual": client_stats["individuals"],
                "company": client_stats["companies"],
            },
            "recent_24h": recent_clients,
            "pending_folder_creation": pending_folder_creation,
        },
        "documents": {
            "total": doc_stats["total"],
            "by_category": {
                "immigration": doc_stats["immigration"],
                "pma": doc_stats["pma"],
                "tax": doc_stats["tax"],
                "personal": doc_stats["personal"],
                "other": doc_stats["other"],
            },
            "by_storage": {
                "google_drive": doc_stats["google_drive"],
                "dropbox": doc_stats["dropbox"],
                "local": doc_stats["local_storage"],
            },
            "recent_24h": recent_documents,
        },
        "migration_activity": {
            "clients_created_last_24h": recent_clients,
            "documents_uploaded_last_24h": recent_documents,
            "is_actively_migrating": recent_clients > 0 or recent_documents > 10,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/migration/clients-summary")
async def get_clients_migration_summary(
    pool=Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Get detailed summary of client migration status.

    Returns list of all clients with their migration completion status:
    - Client ID and name
    - Whether Google Drive folder exists
    - Document count
    - Last updated time

    Useful for identifying which clients still need migration.

    Returns:
        {
            "clients": [
                {
                    "id": 123,
                    "full_name": "Marco Rossi",
                    "client_type": "individual",
                    "has_drive_folder": true,
                    "folder_id": "1ABC...",
                    "document_count": 15,
                    "last_updated": "2026-01-14T10:00:00Z"
                },
                ...
            ],
            "summary": {
                "total": 50,
                "migrated": 35,
                "pending": 15
            }
        }
    """
    async with pool.acquire() as conn:
        # Get all clients with document counts
        clients = await conn.fetch(
            """
            SELECT
                c.id,
                c.full_name,
                c.client_type,
                c.google_drive_folder_id,
                c.updated_at,
                COUNT(d.id) as document_count
            FROM clients c
            LEFT JOIN documents d ON d.client_id = c.id
            GROUP BY c.id, c.full_name, c.client_type, c.google_drive_folder_id, c.updated_at
            ORDER BY c.full_name
            """,
        )

    clients_list = []
    migrated_count = 0
    pending_count = 0

    for client in clients:
        has_folder = client["google_drive_folder_id"] is not None

        if has_folder:
            migrated_count += 1
        else:
            pending_count += 1

        clients_list.append(
            {
                "id": client["id"],
                "full_name": client["full_name"],
                "client_type": client["client_type"],
                "has_drive_folder": has_folder,
                "folder_id": client["google_drive_folder_id"],
                "document_count": client["document_count"],
                "last_updated": (
                    client["updated_at"].isoformat() if client["updated_at"] else None
                ),
            },
        )

    return {
        "clients": clients_list,
        "summary": {
            "total": len(clients_list),
            "migrated": migrated_count,
            "pending": pending_count,
            "completion_percentage": (
                round((migrated_count / len(clients_list)) * 100, 1) if clients_list else 0
            ),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/migration/documents-by-client/{client_id}")
async def get_client_documents_summary(
    client_id: int,
    pool=Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Get detailed document summary for a specific client.

    Useful for verifying migration completeness for individual clients.

    Args:
        client_id: Client database ID

    Returns:
        {
            "client_id": 123,
            "client_name": "Marco Rossi",
            "folder_id": "1ABC...",
            "folder_url": "https://drive.google.com/...",
            "documents": {
                "total": 15,
                "by_category": {...},
                "by_type": {...}
            },
            "recent_uploads": [...]
        }
    """
    async with pool.acquire() as conn:
        # Get client info
        client = await conn.fetchrow(
            """
            SELECT id, full_name, google_drive_folder_id
            FROM clients
            WHERE id = $1
            """,
            client_id,
        )

        if not client:
            raise HTTPException(status_code=404, detail=f"Client {client_id} not found")

        # Get document statistics
        doc_stats = await conn.fetch(
            """
            SELECT
                document_category,
                document_type,
                COUNT(*) as count
            FROM documents
            WHERE client_id = $1
            GROUP BY document_category, document_type
            ORDER BY document_category, document_type
            """,
            client_id,
        )

        # Get recent uploads
        recent_docs = await conn.fetch(
            """
            SELECT
                id, file_name, document_type, document_category, uploaded_at
            FROM documents
            WHERE client_id = $1
            ORDER BY uploaded_at DESC
            LIMIT 10
            """,
            client_id,
        )

    # Aggregate by category
    by_category = {}
    by_type = {}

    for stat in doc_stats:
        category = stat["document_category"] or "uncategorized"
        doc_type = stat["document_type"] or "unknown"
        count = stat["count"]

        by_category[category] = by_category.get(category, 0) + count
        by_type[doc_type] = by_type.get(doc_type, 0) + count

    total_docs = sum(by_category.values())

    # Format recent uploads
    recent_uploads = [
        {
            "id": doc["id"],
            "file_name": doc["file_name"],
            "type": doc["document_type"],
            "category": doc["document_category"],
            "uploaded_at": doc["uploaded_at"].isoformat() if doc["uploaded_at"] else None,
        }
        for doc in recent_docs
    ]

    # Build folder URL if folder exists
    folder_url = None
    if client["google_drive_folder_id"]:
        folder_url = f"https://drive.google.com/drive/folders/{client['google_drive_folder_id']}"

    return {
        "client_id": client["id"],
        "client_name": client["full_name"],
        "folder_id": client["google_drive_folder_id"],
        "folder_url": folder_url,
        "documents": {
            "total": total_docs,
            "by_category": by_category,
            "by_type": by_type,
        },
        "recent_uploads": recent_uploads,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
