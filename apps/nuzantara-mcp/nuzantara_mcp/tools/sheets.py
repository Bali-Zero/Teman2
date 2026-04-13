"""Google Sheets Tools - Read/write spreadsheet data."""

from typing import Optional


def register(mcp, _call, _call_safe):
    @mcp.tool()
    async def read_sheet(
        spreadsheet_id: str,
        range: str,
    ) -> dict:
        """
        Read data from a Google Spreadsheet range.

        Uses POST to avoid URL-encoding issues with A1 notation
        (exclamation marks in ranges like 'Company!A1:Z100' cause
        double-escaping problems with GET query parameters).

        Args:
            spreadsheet_id: The spreadsheet ID (from the URL)
            range: A1 notation range, e.g. 'Sheet1!A1:Z100'

        Returns:
            Rows of data as list of lists.
        """
        return await _call(
            "/api/sheets/read",
            method="POST",
            json={"spreadsheet_id": spreadsheet_id, "range": range},
        )

    @mcp.tool()
    async def write_sheet(
        spreadsheet_id: str,
        range: str,
        values: list[list[str]],
    ) -> dict:
        """
        Write values to a Google Spreadsheet range.

        Args:
            spreadsheet_id: The spreadsheet ID
            range: A1 notation range, e.g. 'Company!D5:U5'
            values: 2D array of values to write

        Returns:
            Number of updated cells.
        """
        return await _call(
            "/api/sheets/write",
            method="POST",
            json={
                "spreadsheet_id": spreadsheet_id,
                "range": range,
                "values": values,
            },
        )

    @mcp.tool()
    async def update_sheet_row(
        spreadsheet_id: str,
        sheet_name: str,
        row_number: int,
        column_start: str,
        values: list[str],
    ) -> dict:
        """
        Update a specific row in a Google Spreadsheet starting from a column.

        Args:
            spreadsheet_id: The spreadsheet ID
            sheet_name: Sheet tab name, e.g. 'Company'
            row_number: 1-based row number
            column_start: Starting column letter, e.g. 'D'
            values: List of values to write (fills columns sequentially)

        Returns:
            Updated range and cell count.
        """
        return await _call(
            "/api/sheets/update-row",
            method="POST",
            json={
                "spreadsheet_id": spreadsheet_id,
                "sheet_name": sheet_name,
                "row_number": row_number,
                "column_start": column_start,
                "values": values,
            },
        )

    @mcp.tool()
    async def find_sheet_row(
        spreadsheet_id: str,
        range: str,
        search_value: str,
        search_column: int = 0,
    ) -> dict:
        """
        Find a row in a spreadsheet by matching a column value.

        Args:
            spreadsheet_id: The spreadsheet ID
            range: Range to search, e.g. 'Company!A:C'
            search_value: Value to find (case-insensitive)
            search_column: 0-based column index within the range

        Returns:
            Row number (1-based) if found, null otherwise.
        """
        return await _call(
            "/api/sheets/find",
            method="POST",
            json={
                "spreadsheet_id": spreadsheet_id,
                "range": range,
                "search_value": search_value,
                "search_column": search_column,
            },
        )
