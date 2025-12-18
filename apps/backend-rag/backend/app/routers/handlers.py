"""
Handlers Registry Endpoint
Auto-discovers and exposes all available handlers/tools for ZANTARA
"""

from typing import Any

from fastapi import APIRouter, HTTPException

# Initialize Router
router = APIRouter(prefix="/api/handlers", tags=["handlers"])


def extract_handlers_from_router(module) -> list[dict[str, Any]]:
    """Extract all route handlers from a router module"""
    handlers = []

    if hasattr(module, "router"):
        for route in module.router.routes:
            if hasattr(route, "endpoint"):
                handlers.append(
                    {
                        "name": route.name,
                        "path": route.path,
                        "methods": list(route.methods) if hasattr(route, "methods") else [],
                        "description": (
                            route.endpoint.__doc__.strip() if route.endpoint.__doc__ else ""
                        ),
                        "module": module.__name__,
                    }
                )

    return handlers


@router.get("/list")
async def list_all_handlers():
    """
    Returns complete registry of all available handlers
    This is the master catalog that ZANTARA uses to see all available tools
    """
    # Lazy import to avoid circular dependencies
    from app.routers import (
        agents,
        conversations,
        crm_clients,
        crm_interactions,
        crm_practices,
        health,
        ingest,
        intel,
        memory_vector,
        oracle_universal,
    )

    modules = [
        agents,
        conversations,
        crm_clients,
        crm_interactions,
        crm_practices,
        health,
        ingest,
        intel,
        memory_vector,
        oracle_universal,
    ]

    all_handlers = []
    categories = {}

    for module in modules:
        module_handlers = extract_handlers_from_router(module)
        category = module.__name__.split(".")[-1]

        categories[category] = {"count": len(module_handlers), "handlers": module_handlers}

        all_handlers.extend(module_handlers)

    return {
        "total_handlers": len(all_handlers),
        "categories": categories,
        "handlers": all_handlers,
        "last_updated": "2025-11-03T02:00:00Z",
    }


@router.get("/search")
async def search_handlers(query: str):
    """Search handlers by name, path, or description"""

    all_data = await list_all_handlers()
    handlers = all_data["handlers"]

    query_lower = query.lower()

    matching = [
        h
        for h in handlers
        if query_lower in h["name"].lower()
        or query_lower in h["path"].lower()
        or query_lower in h["description"].lower()
    ]

    return {"query": query, "matches": len(matching), "handlers": matching}


@router.get("/category/{category}")
async def get_handlers_by_category(category: str):
    """Get all handlers in a specific category"""

    all_data = await list_all_handlers()

    if category not in all_data["categories"]:
        raise HTTPException(status_code=404, detail=f"Category '{category}' not found")

    return all_data["categories"][category]
