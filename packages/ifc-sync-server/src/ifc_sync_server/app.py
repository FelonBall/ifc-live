"""FastAPI application factory and WebSocket endpoint for ifc-live.

Public surface:
  WS  /sync/{file_id}          — real-time op stream per named IFC file
  GET /healthz                 — liveness probe
  GET /files                   — list known file_ids (debug)
  GET /files/{file_id}/log     — full op log as JSON (debug)
  GET /files/{file_id}/audit   — audit log stub (debug; populated in step 5)

The module-level ``app`` instance is used by uvicorn when the server is
launched via the CLI. Tests should call ``create_app()`` directly to get a
fresh, isolated instance with an empty registry.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import AsyncGenerator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from ifc_sync_server.models import (
    AuditEntry,
    ClientOpMessage,
    FileInfoResponse,
    HelloMessage,
    OpAckMessage,
    ReadyMessage,
    ServerOpMessage,
    StoredOpResponse,
    SyncMessage,
    parse_client_message,
)
from ifc_sync_server.state import FileState, StoredOp

logger = logging.getLogger(__name__)


def create_app(
    registry: dict[str, FileState] | None = None,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> FastAPI:
    """Create and return the FastAPI application.

    Args:
        registry: Pre-built per-file state store. Pass your own dict to get a
            fresh, isolated instance (useful in tests). When ``None``, a new
            empty dict is created.
        host: Bind address — used only for the startup log message printed via
            the lifespan hook. Does not affect actual socket binding (that is
            controlled by the uvicorn call in the CLI).
        port: Bind port — same caveat as ``host``.

    Returns:
        A configured ``FastAPI`` instance with all routes registered.
    """
    _registry: dict[str, FileState] = registry if registry is not None else {}

    @contextlib.asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
        print(f"Listening on ws://{host}:{port}")
        yield

    app = FastAPI(title="ifc-sync-server", lifespan=lifespan)

    # ------------------------------------------------------------------
    # Internal helpers (closures over _registry)
    # ------------------------------------------------------------------

    def _get_or_create(file_id: str) -> FileState:
        if file_id not in _registry:
            _registry[file_id] = FileState(file_id=file_id)
        return _registry[file_id]

    async def _broadcast_to_others(
        file_state: FileState,
        sender: WebSocket,
        message: str,
    ) -> None:
        """Send ``message`` to every client in ``file_state`` except ``sender``.

        Clients that fail during send (disconnected mid-broadcast) are
        collected and removed from the client set after the loop finishes —
        never mutate a set while iterating it.
        """
        failed: set[WebSocket] = set()
        for client in file_state.clients:
            if client is sender:
                continue
            try:
                await client.send_text(message)
            except Exception:  # pylint: disable=broad-except
                # Client disconnected between op receipt and broadcast.
                # Silently remove it; there is nothing useful to report.
                failed.add(client)
        file_state.clients -= failed

    # ------------------------------------------------------------------
    # HTTP debug endpoints
    # ------------------------------------------------------------------

    async def healthz() -> dict[str, str]:
        """Liveness probe — always returns ``{"status": "ok"}``."""
        return {"status": "ok"}

    async def list_files() -> list[FileInfoResponse]:
        """List all known file_ids with their connected client counts."""
        return [
            FileInfoResponse(file_id=fs.file_id, client_count=len(fs.clients))
            for fs in _registry.values()
        ]

    async def get_log(file_id: str) -> list[StoredOpResponse]:
        """Return the full op log for a file as a JSON list."""
        fs = _registry.get(file_id)
        if fs is None:
            return []
        return [
            StoredOpResponse(
                server_position=s.server_position,
                envelope=s.envelope,
                resolved=s.resolved,
            )
            for s in fs.op_log
        ]

    async def get_audit(file_id: str) -> list[AuditEntry]:
        """Return the audit log (empty until step 5 adds conflict resolution)."""
        return []

    app.add_api_route("/healthz", healthz, methods=["GET"])
    app.add_api_route("/files", list_files, methods=["GET"])
    app.add_api_route("/files/{file_id}/log", get_log, methods=["GET"])
    app.add_api_route("/files/{file_id}/audit", get_audit, methods=["GET"])

    # ------------------------------------------------------------------
    # WebSocket endpoint
    # ------------------------------------------------------------------

    async def websocket_sync(ws: WebSocket, file_id: str) -> None:
        """Real-time op sync endpoint.

        Connection lifecycle:

        1. Accept the connection and register the client.
        2. Receive ``hello``; close with code 1007 if the first message is
           not a valid ``HelloMessage``.
        3. Send ``sync`` (all ops since ``last_known_op_id``) then ``ready``.
        4. Steady state: receive ``op`` messages, append each to the log,
           send ``op_ack`` to the sender, broadcast to all other clients.
        5. On disconnect: remove the client from the connected set.

        Args:
            ws: The incoming WebSocket connection.
            file_id: The IFC file namespace, taken from the URL path.
        """
        await ws.accept()
        file_state = _get_or_create(file_id)
        file_state.clients.add(ws)
        try:
            # --- hello phase ---
            try:
                raw = await ws.receive_text()
                hello_msg = parse_client_message(raw)
            except ValidationError as exc:
                logger.warning("malformed hello from client: %s", exc)
                await _close_safely(ws, 1007)
                return
            except WebSocketDisconnect:
                return

            if not isinstance(hello_msg, HelloMessage):
                logger.warning(
                    "expected hello as first message, got %s",
                    type(hello_msg).__name__,
                )
                await _close_safely(ws, 1007)
                return

            # --- sync phase ---
            catchup = file_state.ops_since(hello_msg.last_known_op_id)
            await ws.send_text(
                SyncMessage(
                    ops=[s.envelope for s in catchup],
                    head_op_id=file_state.head_op_id,
                ).model_dump_json()
            )
            await ws.send_text(ReadyMessage().model_dump_json())

            # --- steady state ---
            while True:
                try:
                    raw = await ws.receive_text()
                    incoming = parse_client_message(raw)
                except WebSocketDisconnect:
                    break
                except ValidationError as exc:
                    logger.warning("malformed op message from client: %s", exc)
                    await _close_safely(ws, 1007)
                    break

                if not isinstance(incoming, ClientOpMessage):
                    logger.warning(
                        "expected op in steady state, got %s",
                        type(incoming).__name__,
                    )
                    await _close_safely(ws, 1007)
                    break

                position = len(file_state.op_log)
                file_state.op_log.append(
                    StoredOp(server_position=position, envelope=incoming.envelope)
                )

                await ws.send_text(
                    OpAckMessage(
                        op_id=str(incoming.envelope.op_id),
                        server_position=position,
                    ).model_dump_json()
                )
                await _broadcast_to_others(
                    file_state,
                    ws,
                    ServerOpMessage(
                        envelope=incoming.envelope,
                        server_position=position,
                        resolved=False,
                    ).model_dump_json(),
                )

        except WebSocketDisconnect:
            pass
        finally:
            file_state.clients.discard(ws)

    app.add_api_websocket_route("/sync/{file_id}", websocket_sync)

    return app


async def _close_safely(ws: WebSocket, code: int) -> None:
    """Close ``ws`` with the given code, ignoring errors if already closed."""
    with contextlib.suppress(Exception):
        await ws.close(code)
