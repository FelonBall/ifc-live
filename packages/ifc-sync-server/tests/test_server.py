"""Integration tests for the ifc-live sync server.

Uses ``starlette.testclient.TestClient``, which runs the ASGI app in a
background thread and provides synchronous WebSocket and HTTP interfaces.
Multiple WebSocket connections can be open concurrently within a single test.

Each test creates its own ``create_app()`` instance so state never leaks
between tests.
"""

from __future__ import annotations

from uuid import uuid4

from starlette.testclient import TestClient, WebSocketTestSession

from ifc_sync_server.app import create_app

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_envelope(file_id: str, op_id: str | None = None) -> dict[str, object]:
    """Return a minimal valid ``IfcOpEnvelope`` as a plain dict.

    Uses ``modify_attribute`` because it has no IfcOpenShell dependency and
    exercises the full discriminated-union deserialization path.
    """
    return {
        "schema_version": "1",
        "op_id": op_id if op_id is not None else str(uuid4()),
        "parent_op_id": None,
        "file_id": file_id,
        "author": "test-client",
        "timestamp": 1_716_042_000.0,
        "payload": {
            "kind": "modify_attribute",
            "guid": "GUID00000001",
            "attribute": "Name",
            "previous_value": {"kind": "null"},
            "new_value": {"kind": "string", "value": "Test Wall"},
        },
    }


def _do_handshake(
    ws: WebSocketTestSession,
    client_id: str = "test-client",
    last_known_op_id: str | None = None,
) -> dict[str, object]:
    """Send hello and consume the subsequent sync + ready messages.

    Returns the ``sync`` message dict so callers can inspect ``ops``.
    """
    ws.send_json(
        {
            "type": "hello",
            "client_id": client_id,
            "last_known_op_id": last_known_op_id,
        }
    )
    sync_msg: dict[str, object] = ws.receive_json()
    assert sync_msg["type"] == "sync", f"expected sync, got {sync_msg}"
    ready_msg: dict[str, object] = ws.receive_json()
    assert ready_msg["type"] == "ready", f"expected ready, got {ready_msg}"
    return sync_msg


# ---------------------------------------------------------------------------
# Test 1: single client receives sync (empty) and ready
# ---------------------------------------------------------------------------


def test_hello_receives_sync_and_ready() -> None:
    """A fresh connection receives an empty sync followed by ready."""
    with TestClient(create_app()) as client, client.websocket_connect("/sync/demo") as ws:
        sync = _do_handshake(ws, "c1")
        assert sync["ops"] == []
        assert sync["head_op_id"] is None


# ---------------------------------------------------------------------------
# Test 2: single client sends an op and receives op_ack
# ---------------------------------------------------------------------------


def test_op_receives_ack() -> None:
    """After handshake, sending an op produces an op_ack with server_position=0."""
    with TestClient(create_app()) as client, client.websocket_connect("/sync/demo") as ws:
        _do_handshake(ws, "c1")
        env = _make_envelope("demo")
        ws.send_json({"type": "op", "envelope": env})

        ack: dict[str, object] = ws.receive_json()
        assert ack["type"] == "op_ack"
        assert ack["op_id"] == env["op_id"]
        assert ack["server_position"] == 0


# ---------------------------------------------------------------------------
# Test 3: two clients on same file_id — one sends op, other receives broadcast
# ---------------------------------------------------------------------------


def test_op_broadcast_to_second_client() -> None:
    """An op sent by client A is broadcast to client B on the same file_id."""
    with (
        TestClient(create_app()) as client,
        client.websocket_connect("/sync/shared") as ws1,
        client.websocket_connect("/sync/shared") as ws2,
    ):
        _do_handshake(ws1, "c1")
        _do_handshake(ws2, "c2")

        env = _make_envelope("shared")
        ws1.send_json({"type": "op", "envelope": env})

        # ws1 gets ack
        ack: dict[str, object] = ws1.receive_json()
        assert ack["type"] == "op_ack"
        assert ack["server_position"] == 0

        # ws2 gets broadcast
        broadcast: dict[str, object] = ws2.receive_json()
        assert broadcast["type"] == "op"
        assert broadcast["server_position"] == 0
        assert broadcast["resolved"] is False
        assert broadcast["envelope"] == env  # type: ignore[comparison-overlap]


# ---------------------------------------------------------------------------
# Test 4: two clients on different file_ids — ops do NOT cross
# ---------------------------------------------------------------------------


def test_no_cross_file_broadcast() -> None:
    """An op sent on file-1 is NOT delivered to a client on file-2.

    After ws1 sends an op, ws2 sends its own op on file-2 and immediately
    receives its op_ack. If the file-1 broadcast had leaked to ws2, the
    first message on ws2 would be the broadcast (type="op"), not the ack
    (type="op_ack"), and the assertion would fail.
    """
    with (
        TestClient(create_app()) as client,
        client.websocket_connect("/sync/file-1") as ws1,
        client.websocket_connect("/sync/file-2") as ws2,
    ):
        _do_handshake(ws1, "c1")
        _do_handshake(ws2, "c2")

        # ws1 sends op on file-1, gets ack
        ws1.send_json({"type": "op", "envelope": _make_envelope("file-1")})
        ack1: dict[str, object] = ws1.receive_json()
        assert ack1["type"] == "op_ack"

        # ws2 sends its own op on file-2; the NEXT message it gets
        # must be its own ack, not the file-1 broadcast
        env2 = _make_envelope("file-2")
        ws2.send_json({"type": "op", "envelope": env2})
        ack2: dict[str, object] = ws2.receive_json()
        assert ack2["type"] == "op_ack", (
            f"expected op_ack but got {ack2!r} — cross-file broadcast may have leaked"
        )
        assert ack2["op_id"] == env2["op_id"]


# ---------------------------------------------------------------------------
# Test 5: catch-up sync — client receives only ops after last_known_op_id
# ---------------------------------------------------------------------------


def test_catch_up_sync() -> None:
    """A client that reconnects with last_known_op_id receives only newer ops."""
    with TestClient(create_app()) as client:
        # Bootstrap: ws1 sends two ops
        with client.websocket_connect("/sync/demo") as ws1:
            _do_handshake(ws1, "c1")
            env1 = _make_envelope("demo", op_id=str(uuid4()))
            env2 = _make_envelope("demo", op_id=str(uuid4()))

            ws1.send_json({"type": "op", "envelope": env1})
            ws1.receive_json()  # ack for op1

            ws1.send_json({"type": "op", "envelope": env2})
            ws1.receive_json()  # ack for op2

        # ws2 connects knowing about op1 but not op2
        with client.websocket_connect("/sync/demo") as ws2:
            ws2.send_json(
                {
                    "type": "hello",
                    "client_id": "c2",
                    "last_known_op_id": env1["op_id"],
                }
            )
            sync: dict[str, object] = ws2.receive_json()
            assert sync["type"] == "sync"
            ops: list[dict[str, object]] = sync["ops"]  # type: ignore[assignment]
            assert len(ops) == 1, f"expected 1 catch-up op, got {len(ops)}"
            assert ops[0]["op_id"] == env2["op_id"]

            ready: dict[str, object] = ws2.receive_json()
            assert ready["type"] == "ready"


# ---------------------------------------------------------------------------
# Test 6: GET /healthz returns {"status": "ok"}
# ---------------------------------------------------------------------------


def test_healthz() -> None:
    """The liveness endpoint returns 200 with the expected JSON body."""
    with TestClient(create_app()) as client:
        resp = client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Test 7: GET /files/{file_id}/log returns appended ops
# ---------------------------------------------------------------------------


def test_log_endpoint() -> None:
    """After sending two ops, the log endpoint returns a list of length 2."""
    with TestClient(create_app()) as client:
        with client.websocket_connect("/sync/logtest") as ws:
            _do_handshake(ws, "c1")

            for _ in range(2):
                ws.send_json({"type": "op", "envelope": _make_envelope("logtest")})
                ws.receive_json()  # consume ack

        resp = client.get("/files/logtest/log")
        assert resp.status_code == 200
        log = resp.json()
        assert isinstance(log, list)
        assert len(log) == 2
        assert log[0]["server_position"] == 0
        assert log[1]["server_position"] == 1
        assert log[0]["resolved"] is False


# ---------------------------------------------------------------------------
# Test 8: clean disconnect — server does not crash, next client unaffected
# ---------------------------------------------------------------------------


def test_clean_disconnect() -> None:
    """A client that disconnects mid-session is cleanly removed.

    The server must not raise or leave the disconnected WebSocket in its
    client set. A subsequent connection should receive a clean, empty sync.
    """
    with TestClient(create_app()) as client:
        # ws1 connects, completes handshake, then disconnects without sending ops
        with client.websocket_connect("/sync/demo") as ws1:
            _do_handshake(ws1, "c1")
        # ws1 context exits → close frame sent → server removes ws1 from clients

        # ws2 connects afterwards and receives a clean, empty sync
        with client.websocket_connect("/sync/demo") as ws2:
            sync = _do_handshake(ws2, "c2")
            assert sync["ops"] == []
