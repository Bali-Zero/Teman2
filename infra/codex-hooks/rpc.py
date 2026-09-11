"""Small stdio client for the installed Codex app-server (no model calls on init)."""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any


def binary_path() -> str:
    override = os.environ.get("CODEX_CONTEXT_BINARY")
    if override:
        return override
    for candidate in (
        "/Applications/Codex.app/Contents/Resources/codex",
        "/Applications/ChatGPT.app/Contents/Resources/codex",
    ):
        if Path(candidate).is_file():
            return candidate
    return shutil.which("codex") or "codex"


class RPC:
    def __init__(self, binary: str | None = None) -> None:
        self.proc = subprocess.Popen(
            [binary or binary_path(), "app-server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            env=os.environ.copy(),
        )
        self.messages: queue.Queue[dict[str, Any]] = queue.Queue()
        self.serial = 0
        threading.Thread(target=self._read, daemon=True).start()
        self.call(
            "initialize",
            {
                "clientInfo": {"name": "nuzantara_context_bridge", "version": "1.0.0"},
                "capabilities": {"experimentalApi": True},
            },
        )
        self.send({"method": "initialized"})

    def _read(self) -> None:
        assert self.proc.stdout
        for line in self.proc.stdout:
            try:
                self.messages.put(json.loads(line))
            except ValueError:
                continue
        self.messages.put({"method": "bridge/eof"})

    def send(self, message: dict[str, Any]) -> None:
        assert self.proc.stdin
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()

    def next(self, timeout: float = 30) -> dict[str, Any]:
        message = self.messages.get(timeout=timeout)
        if message.get("method") == "bridge/eof":
            raise RuntimeError("app-server exited")
        # A background continuation cannot obtain new consent. Never grant it.
        if "id" in message and "method" in message:
            self.send(
                {
                    "id": message["id"],
                    "error": {
                        "code": -32000,
                        "message": "Continuation requires interactive approval",
                    },
                }
            )
            raise RuntimeError("interactive approval required")
        return message

    def call(self, method: str, params: dict[str, Any], timeout: float = 30) -> Any:
        self.serial += 1
        wanted = self.serial
        self.send({"id": wanted, "method": method, "params": params})
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            message = self.next(max(0.01, until - time.monotonic()))
            if message.get("id") == wanted:
                if "error" in message:
                    raise RuntimeError(str(message["error"]))
                return message.get("result")
        raise TimeoutError(method)

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
