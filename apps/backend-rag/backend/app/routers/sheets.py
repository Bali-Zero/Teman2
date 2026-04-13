"""
Google Sheets API — Read/write spreadsheet data.

Endpoints:
  GET  /api/sheets/read    — Read a range
  POST /api/sheets/write   — Write to a range
  POST /api/sheets/append  — Append rows
  POST /api/sheets/find    — Find row by value
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core.cache import invalidate_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sheets", tags=["sheets"])


# ---- Request / Response models ----


class ReadRequest(BaseModel):
    spreadsheet_id: str
    range: str


class WriteRequest(BaseModel):
    spreadsheet_id: str
    range: str
    values: list[list[str]]


class FindRequest(BaseModel):
    spreadsheet_id: str
    range: str
    search_column: int = 0
    search_value: str


class UpdateRowRequest(BaseModel):
    """Write specific columns to a known row in a spreadsheet."""

    spreadsheet_id: str
    sheet_name: str
    row_number: int
    column_start: str  # e.g. "D"
    values: list[str]


# ---- Helpers ----


def _get_sheets_service() -> Any:
    from backend.services.integrations.sheets_service import SheetsService

    return SheetsService()


# ---- Endpoints ----


@router.get("/read")
async def read_range(spreadsheet_id: str, range: str) -> dict[str, Any]:
    """Read a range from a Google Spreadsheet."""
    try:
        svc = _get_sheets_service()
        # Unescape backslash-escaped exclamation marks from URL encoding
        clean_range = range.replace("\\!", "!")
        rows = await svc.read_range(spreadsheet_id, clean_range)
        return {"status": "success", "rows": rows, "count": len(rows)}
    except Exception as e:
        logger.error(f"[SHEETS] Read failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/read")
async def read_range_post(req: ReadRequest) -> dict[str, Any]:
    """Read a range (POST version to avoid URL encoding issues with '!')."""
    try:
        svc = _get_sheets_service()
        rows = await svc.read_range(req.spreadsheet_id, req.range)
        return {"status": "success", "rows": rows, "count": len(rows)}
    except Exception as e:
        logger.error(f"[SHEETS] Read failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/write")
async def write_range(req: WriteRequest) -> dict[str, Any]:
    """Write values to a specific range."""
    try:
        svc = _get_sheets_service()
        result = await svc.write_range(req.spreadsheet_id, req.range, req.values)
        await invalidate_cache("zantara:sheets:*")
        return {"status": "success", "updated_cells": result.get("updatedCells", 0)}
    except Exception as e:
        logger.error(f"[SHEETS] Write failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/append")
async def append_rows(req: WriteRequest) -> dict[str, Any]:
    """Append rows after the last data row."""
    try:
        svc = _get_sheets_service()
        result = await svc.append_row(req.spreadsheet_id, req.range, req.values)
        await invalidate_cache("zantara:sheets:*")
        return {
            "status": "success",
            "updated_range": result.get("updates", {}).get("updatedRange", ""),
        }
    except Exception as e:
        logger.error(f"[SHEETS] Append failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/find")
async def find_row(req: FindRequest) -> dict[str, Any]:
    """Find a row by matching a column value."""
    try:
        svc = _get_sheets_service()
        row_num = await svc.find_row_by_value(
            req.spreadsheet_id, req.range, req.search_column, req.search_value,
        )
        if row_num is None:
            return {"status": "not_found", "row": None}
        return {"status": "found", "row": row_num}
    except Exception as e:
        logger.error(f"[SHEETS] Find failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/update-row")
async def update_row(req: UpdateRowRequest) -> dict[str, Any]:
    """
    Write values to a specific row starting at a given column.
    Example: sheet_name='Company', row_number=5, column_start='D', values=['addr','nib',...]
    writes to Company!D5:U5
    """
    try:
        svc = _get_sheets_service()
        # Calculate end column
        start_col_idx = ord(req.column_start.upper()) - ord("A")
        end_col_idx = start_col_idx + len(req.values) - 1
        end_col = chr(ord("A") + end_col_idx)
        range_ = f"{req.sheet_name}!{req.column_start}{req.row_number}:{end_col}{req.row_number}"

        result = await svc.write_range(req.spreadsheet_id, range_, [req.values])
        await invalidate_cache("zantara:sheets:*")
        return {
            "status": "success",
            "range": range_,
            "updated_cells": result.get("updatedCells", 0),
        }
    except Exception as e:
        logger.error(f"[SHEETS] Update row failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
