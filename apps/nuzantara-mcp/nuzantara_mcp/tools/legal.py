"""Legal Tools — ingest Indonesian regulation documents into Qdrant+KG+Drive+NLM+Sheets."""

from typing import Optional

from nuzantara_mcp.auth import require_role


def register(mcp, _call, _call_safe):
    @mcp.tool()
    @require_role("admin")
    async def ingest_regulation(
        url: str,
        tipo: str,
        nomor: str,
        anno: str,
        titolo: Optional[str] = None,
        nb_target: Optional[str] = None,
    ) -> dict:
        """
        Ingest an Indonesian government regulation into all systems.

        Pipeline (async, 4 steps):
          1. Download PDF + embed in Qdrant + build KG
          2. Upload to Google Drive (PERATURAN/<tipo>/<anno>/)
          3. Add to NotebookLM notebook (NB-3 for PP/Perpres/Permen, NB-4 for PMK/SE)
          4. Append row to Legal Catalog Google Sheet

        Returns HTTP 202 immediately with a job_id. Poll get_ingest_status(job_id) for progress.
        Idempotent: same tipo+nomor+anno returns the existing job (no duplicate ingestion).

        Args:
            url: Direct URL to the PDF (e.g. jdih.kemenkeu.go.id link)
            tipo: Regulation type — PP, Perpres, PMK, Permen, SE, SKB
            nomor: Regulation number (e.g. "28")
            anno: Year (e.g. "2025")
            titolo: Optional title — auto-extracted from PDF if not provided
            nb_target: Override NotebookLM target (NB-3 to NB-6); auto-mapped if omitted

        Returns:
            job_id, status, message, nb_target assigned
        """
        payload: dict = {
            "url": url,
            "tipo": tipo,
            "nomor": nomor,
            "anno": anno,
        }
        if titolo:
            payload["titolo"] = titolo
        if nb_target:
            payload["nb_target"] = nb_target

        return await _call("/api/legal/ingest-full", method="POST", json=payload)

    @mcp.tool()
    @require_role("admin")
    async def get_ingest_status(job_id: str) -> dict:
        """
        Poll the status of a legal regulation ingestion job.

        Statuses:
          - pending: queued, not yet started
          - qdrant_done: embedded in Qdrant + KG built
          - drive_done: uploaded to Google Drive
          - nlm_done: added to NotebookLM notebook
          - complete: all 4 steps done, row appended to Sheets
          - failed: error occurred (see error field)

        Args:
            job_id: UUID returned by ingest_regulation

        Returns:
            Full job state: status, tipo, nomor, anno, titolo, qdrant_chunks,
            drive_url, nlm_source_id, sheets_row, error (if failed)
        """
        return await _call(f"/api/legal/ingest-full/{job_id}")
