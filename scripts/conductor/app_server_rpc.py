"""Bounded stdlib NDJSON transport for a caller-owned Codex App Server process.

The caller supplies the entire child environment and owns mission admission. This
transport never starts a thread/turn itself and never grants a server approval.
Only selected notifications survive; stderr and provider error text are discarded.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import signal
from types import TracebackType
from typing import Any, Mapping, Sequence


class AppServerError(RuntimeError):
    """Stable diagnostic codes, without provider messages, argv or child output."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"app_server:{code}")


def _notification(method: str, params: object) -> dict[str, Any] | None:
    """Project selected native events without reasoning, tools, paths or errors."""
    allowed = {
        "thread/started",
        "turn/started",
        "turn/completed",
        "item/completed",
        "thread/tokenUsage/updated",
    }
    if method not in allowed:
        return None
    if not isinstance(params, dict):
        raise AppServerError("protocol_error")
    selected: dict[str, Any] = {}
    if method == "thread/started":
        thread = params.get("thread")
        if not isinstance(thread, dict) or not isinstance(thread.get("id"), str):
            raise AppServerError("protocol_error")
        selected["thread"] = {"id": thread["id"]}
    else:
        if not isinstance(params.get("threadId"), str):
            raise AppServerError("protocol_error")
        selected["threadId"] = params["threadId"]
        if method in {"turn/started", "turn/completed"}:
            turn = params.get("turn")
            if not isinstance(turn, dict) or not isinstance(turn.get("id"), str):
                raise AppServerError("protocol_error")
            if turn.get("status") not in {
                "inProgress",
                "completed",
                "interrupted",
                "failed",
            }:
                raise AppServerError("protocol_error")
            selected["turn"] = {"id": turn["id"], "status": turn["status"]}
        else:
            if not isinstance(params.get("turnId"), str):
                raise AppServerError("protocol_error")
            selected["turnId"] = params["turnId"]
            if method == "item/completed":
                item = params.get("item")
                if not isinstance(item, dict):
                    raise AppServerError("protocol_error")
                if item.get("type") != "agentMessage":
                    return None
                if not all(isinstance(item.get(key), str) for key in ("id", "text")):
                    raise AppServerError("protocol_error")
                selected["item"] = {key: item[key] for key in ("id", "type", "text")}
                if item.get("phase") in {"commentary", "final_answer"}:
                    selected["item"]["phase"] = item["phase"]
            else:
                usage = params.get("tokenUsage")
                if not isinstance(usage, dict):
                    raise AppServerError("protocol_error")
                selected["tokenUsage"] = {}
                for group in ("last", "total"):
                    counters = usage.get(group)
                    if not isinstance(counters, dict):
                        raise AppServerError("protocol_error")
                    selected["tokenUsage"][group] = {
                        key: counters[key]
                        for key in (
                            "inputTokens",
                            "cachedInputTokens",
                            "cacheWriteInputTokens",
                            "outputTokens",
                            "reasoningOutputTokens",
                            "totalTokens",
                        )
                        if type(counters.get(key)) is int and counters[key] >= 0
                    }
                if (
                    type(usage.get("modelContextWindow")) is int
                    and usage["modelContextWindow"] >= 0
                ):
                    selected["tokenUsage"]["modelContextWindow"] = usage[
                        "modelContextWindow"
                    ]
    return {"method": method, "params": selected}


class AppServerRPC:
    """One native session, explicit process ownership and no remote-cancel claim."""

    def __init__(
        self,
        argv: Sequence[str],
        cwd: Path,
        env: Mapping[str, str],
        *,
        rpc_timeout: float = 10,
        frame_limit: int = 1 << 20,
        queue_limit: int = 64,
        shutdown_timeout: float = 1,
        experimental_api: bool = False,
        reject_tool_activity: bool = False,
    ) -> None:
        if not argv or not 0 < rpc_timeout <= 60 or not 0 < shutdown_timeout <= 10:
            raise ValueError("invalid transport bounds")
        if not 1 <= frame_limit <= 16 << 20 or not 1 <= queue_limit <= 1024:
            raise ValueError("invalid transport bounds")
        self._argv, self._cwd, self._env = tuple(argv), cwd, dict(env)
        self._timeout, self._frame_limit = rpc_timeout, frame_limit
        self._shutdown_timeout, self._pending_limit = shutdown_timeout, queue_limit
        self._experimental_api = experimental_api
        self._reject_tool_activity = reject_tool_activity
        self._process: asyncio.subprocess.Process | None = None
        self._reader: asyncio.Task[None] | None = None
        self._shutdown_task: asyncio.Task[None] | None = None
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._notifications: asyncio.Queue[dict[str, Any]] = asyncio.Queue(queue_limit)
        self._failed = asyncio.Event()
        self._failure: AppServerError | None = None
        self._write_lock, self._close_lock = asyncio.Lock(), asyncio.Lock()
        self._request_id = 0
        self.initialization: dict[str, str] = {}
        self.local_stopped = False

    @property
    def pid(self) -> int | None:
        return self._process.pid if self._process else None

    async def __aenter__(self) -> AppServerRPC:
        if self._process is not None or self._failure is not None:
            raise AppServerError("already_started")
        try:
            self._process = await asyncio.create_subprocess_exec(
                *self._argv,
                cwd=self._cwd,
                env=self._env,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                start_new_session=True,
                limit=self._frame_limit + 1,
            )
            self._reader = asyncio.create_task(self._read_loop())
            result = await self.call(
                "initialize",
                {
                    "clientInfo": {"name": "nuzantara_dual_consul", "version": "1"},
                    "capabilities": {"experimentalApi": self._experimental_api},
                },
            )
            self.initialization = {
                key: result[key]
                for key in (
                    "userAgent",
                    "platformFamily",
                    "platformOs",
                )
                if isinstance(result.get(key), str)
            }
            await self.notify("initialized", {})
            return self
        except BaseException as error:
            await self.close()
            if isinstance(error, (OSError, ValueError)):
                raise AppServerError("start_failed") from None
            raise

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    def _fail(self, code: str) -> None:
        if self._failure is None:
            self._failure = AppServerError(code)
            self._failed.set()
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(AppServerError(code))

    def _ensure_open(self) -> None:
        if self._failure is not None:
            raise AppServerError(self._failure.code)
        if self._process is None:
            raise AppServerError("not_started")

    def _schedule_close(self) -> None:
        if self._shutdown_task is None:
            self._shutdown_task = asyncio.create_task(self.close())

    async def _send(self, message: dict[str, Any]) -> None:
        self._ensure_open()
        try:
            encoded = json.dumps(message, allow_nan=False).encode() + b"\n"
        except (TypeError, ValueError):
            raise AppServerError("invalid_request") from None
        if len(encoded) > self._frame_limit:
            raise AppServerError("frame_limit")
        written = False
        try:
            async with self._write_lock:
                self._ensure_open()
                assert self._process is not None and self._process.stdin is not None
                self._process.stdin.write(encoded)
                written = True
                await self._process.stdin.drain()
        except asyncio.CancelledError:
            if written:
                self._fail("send_interrupted")
                self._schedule_close()
            raise
        except (BrokenPipeError, ConnectionError, OSError):
            self._fail("transport_closed")
            self._schedule_close()
            raise AppServerError("transport_closed") from None

    def _deadline(self, timeout: float | None) -> float:
        value = self._timeout if timeout is None else timeout
        if not 0 < value <= 60:
            raise AppServerError("invalid_timeout")
        return value

    async def call(
        self,
        method: str,
        params: Mapping[str, Any],
        *,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        self._ensure_open()
        deadline = self._deadline(timeout)
        if len(self._pending) >= self._pending_limit:
            raise AppServerError("pending_limit")
        self._request_id += 1
        identifier = self._request_id
        future: asyncio.Future[dict[str, Any]] = (
            asyncio.get_running_loop().create_future()
        )
        self._pending[identifier] = future
        try:
            async with asyncio.timeout(deadline):
                await self._send(
                    {"id": identifier, "method": method, "params": dict(params)}
                )
                return await future
        except TimeoutError:
            raise AppServerError("rpc_timeout") from None
        finally:
            self._pending.pop(identifier, None)
            if not future.done():
                future.cancel()
            elif not future.cancelled():
                future.exception()

    async def notify(self, method: str, params: Mapping[str, Any]) -> None:
        try:
            async with asyncio.timeout(self._timeout):
                await self._send({"method": method, "params": dict(params)})
        except TimeoutError:
            raise AppServerError("rpc_timeout") from None

    async def next_notification(
        self, *, timeout: float | None = None
    ) -> dict[str, Any]:
        self._ensure_open()
        deadline = self._deadline(timeout)
        event = asyncio.create_task(self._notifications.get())
        failed = asyncio.create_task(self._failed.wait())
        try:
            done, _ = await asyncio.wait(
                (event, failed), timeout=deadline, return_when=asyncio.FIRST_COMPLETED
            )
            self._ensure_open()
            if event not in done:
                raise AppServerError("notification_timeout")
            return event.result()
        finally:
            for task in (event, failed):
                task.cancel()
            await asyncio.gather(event, failed, return_exceptions=True)

    async def _server_request(self, message: dict[str, Any]) -> None:
        method = message["method"]
        if method in {
            "item/commandExecution/requestApproval",
            "item/fileChange/requestApproval",
        }:
            reply = {"result": {"decision": "decline"}}
        elif method == "item/permissions/requestApproval":
            reply = {"result": {"permissions": {}, "scope": "turn"}}
        elif method in {"execCommandApproval", "applyPatchApproval"}:
            reply = {"result": {"decision": "abort"}}
        else:
            reply = {"error": {"code": -32601, "message": "unsupported server request"}}
        async with asyncio.timeout(self._timeout):
            await self._send({"id": message["id"], **reply})

    async def _read_loop(self) -> None:
        assert self._process is not None and self._process.stdout is not None
        try:
            while True:
                try:
                    line = await self._process.stdout.readline()
                except ValueError:
                    raise AppServerError("frame_limit") from None
                if not line:
                    raise AppServerError("eof")
                if len(line) > self._frame_limit or not line.endswith(b"\n"):
                    raise AppServerError("frame_limit")
                message = json.loads(line)
                if not isinstance(message, dict):
                    raise AppServerError("protocol_error")
                if "id" in message and type(message["id"]) not in (str, int):
                    raise AppServerError("protocol_error")
                if "method" in message:
                    if not isinstance(message["method"], str):
                        raise AppServerError("protocol_error")
                    if "id" in message:
                        await self._server_request(message)
                    else:
                        if self._reject_tool_activity and message["method"] in {
                            "item/started",
                            "item/completed",
                        }:
                            params = message.get("params")
                            item = (
                                params.get("item") if isinstance(params, dict) else None
                            )
                            if not isinstance(item, dict):
                                raise AppServerError("protocol_error")
                            if item.get("type") not in {
                                "userMessage",
                                "agentMessage",
                                "reasoning",
                                "contextCompaction",
                            }:
                                raise AppServerError("tool_activity_unqualified")
                        selected = _notification(
                            message["method"], message.get("params")
                        )
                        if selected is not None:
                            self._notifications.put_nowait(selected)
                elif "id" in message:
                    future = self._pending.get(message["id"])
                    if future is None or future.done():
                        continue  # Timed-out/cancelled IDs never bind to a later RPC.
                    if "error" in message:
                        future.set_exception(AppServerError("rpc_error"))
                    elif isinstance(message.get("result"), dict):
                        future.set_result(message["result"])
                    else:
                        raise AppServerError("protocol_error")
                else:
                    raise AppServerError("protocol_error")
        except asyncio.CancelledError:
            raise
        except AppServerError as error:
            self._fail(error.code)
        except asyncio.QueueFull:
            self._fail("notification_overflow")
        except (
            ValueError,
            UnicodeError,
            RecursionError,
            TypeError,
            OSError,
            TimeoutError,
        ):
            self._fail("protocol_error")
        self._schedule_close()

    def _group_alive(self) -> bool:
        if self.pid is None:
            return False
        try:
            os.killpg(self.pid, 0)
            return True
        except ProcessLookupError:
            return False

    async def close(self) -> None:
        """Stop this local process group; remote operation status remains unknown."""
        async with self._close_lock:
            if self.local_stopped:
                return
            self._fail("closed")
            if self._reader is not None and self._reader is not asyncio.current_task():
                self._reader.cancel()
                await asyncio.gather(self._reader, return_exceptions=True)
            if self._process is None:
                return
            if self._process.stdin is not None:
                self._process.stdin.close()
            for sig in (signal.SIGTERM, signal.SIGKILL):
                try:
                    os.killpg(self._process.pid, sig)
                except ProcessLookupError:
                    break
                deadline = asyncio.get_running_loop().time() + self._shutdown_timeout
                while (
                    self._group_alive() and asyncio.get_running_loop().time() < deadline
                ):
                    await asyncio.sleep(0.02)
                if not self._group_alive():
                    break
            try:
                await asyncio.wait_for(self._process.wait(), self._shutdown_timeout)
            except TimeoutError:
                return
            self.local_stopped = (
                self._process.returncode is not None and not self._group_alive()
            )
