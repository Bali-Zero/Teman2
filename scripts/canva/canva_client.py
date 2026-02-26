#!/usr/bin/env python3
"""
Canva API client con auto-refresh del token.
"""

import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

CLIENT_ID = os.getenv("CANVA_CLIENT_ID", "OC-AZyQGrxp8EfH")
CLIENT_SECRET = os.getenv("CANVA_CLIENT_SECRET", "")
TOKENS_FILE = Path.home() / ".canva_tokens.json"
BASE_URL = "https://api.canva.com/rest/v1"


class CanvaClient:
    def __init__(self):
        self._tokens: dict = {}
        self._load_tokens()

    def _load_tokens(self):
        if not TOKENS_FILE.exists():
            raise FileNotFoundError(
                f"Token non trovati. Esegui prima: python3 canva_auth.py"
            )
        self._tokens = json.loads(TOKENS_FILE.read_text())

    def _save_tokens(self):
        TOKENS_FILE.write_text(json.dumps(self._tokens, indent=2))
        TOKENS_FILE.chmod(0o600)

    def _is_expired(self) -> bool:
        expires_at = self._tokens.get("expires_at", 0)
        return time.time() >= (expires_at - 60)  # refresh 60s early

    def _refresh(self):
        refresh_token = self._tokens.get("refresh_token")
        if not refresh_token:
            raise RuntimeError("Nessun refresh_token — riesegui canva_auth.py")

        data = urllib.parse.urlencode({
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        }).encode()

        req = urllib.request.Request(
            f"{BASE_URL}/oauth/token",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            new_tokens = json.loads(resp.read())

        new_tokens["expires_at"] = time.time() + new_tokens.get("expires_in", 3600)
        new_tokens.setdefault("refresh_token", refresh_token)
        self._tokens = new_tokens
        self._save_tokens()

    def _access_token(self) -> str:
        if "expires_at" not in self._tokens:
            self._tokens["expires_at"] = time.time() + self._tokens.get("expires_in", 3600)
            self._save_tokens()
        if self._is_expired():
            self._refresh()
        return self._tokens["access_token"]

    def _request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        params: dict | None = None,
    ) -> Any:
        url = f"{BASE_URL}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)

        data = json.dumps(body).encode() if body else None
        headers = {
            "Authorization": f"Bearer {self._access_token()}",
            "Content-Type": "application/json",
        }

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode()
            raise RuntimeError(f"Canva API {method} {path} → {e.code}: {error_body}") from e

    # ------------------------------------------------------------------ #
    # Design API                                                           #
    # ------------------------------------------------------------------ #

    def get_design(self, design_id: str) -> dict:
        return self._request("GET", f"/designs/{design_id}")

    def list_designs(self, query: str = "", limit: int = 20) -> dict:
        params: dict = {"limit": limit}
        if query:
            params["query"] = query
        return self._request("GET", "/designs", params=params)

    def create_design_from_template(self, design_id: str, title: str) -> dict:
        """Duplicate a design (use it as template)."""
        return self._request("POST", "/designs", body={
            "design_type": {"type": "preset", "name": "Presentation"},
            "asset_id": design_id,
            "title": title,
        })

    def get_design_pages(self, design_id: str) -> dict:
        return self._request("GET", f"/designs/{design_id}/pages")

    def update_design_pages(self, design_id: str, updates: list[dict]) -> dict:
        """Replace text elements on pages."""
        return self._request("PUT", f"/designs/{design_id}/pages", body={"pages": updates})

    def export_design(self, design_id: str, format: str = "png") -> dict:
        """Start an export job. Returns job_id."""
        return self._request("POST", "/exports", body={
            "design_id": design_id,
            "format": {"type": format},
        })

    def get_export_job(self, export_id: str) -> dict:
        return self._request("GET", f"/exports/{export_id}")

    def wait_for_export(self, export_id: str, timeout: int = 120) -> list[str]:
        """Poll until export is complete, return list of download URLs."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            job = self.get_export_job(export_id)
            status = job.get("job", {}).get("status")
            if status == "success":
                raw = job.get("job", {}).get("urls", [])
                # API returns either list of strings or list of {url: str} objects
                urls = [
                    u if isinstance(u, str) else u["url"]
                    for u in raw
                ]
                return urls
            if status == "failed":
                raise RuntimeError(f"Export failed: {job}")
            time.sleep(2)
        raise TimeoutError(f"Export {export_id} timed out after {timeout}s")

    def download_file(self, url: str, dest: Path) -> Path:
        urllib.request.urlretrieve(url, dest)
        return dest
