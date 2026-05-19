# ifc-sync-server

The WebSocket relay and op-log server for `ifc-live`.

Starts a FastAPI app exposing `ws://HOST:PORT/sync/<file_id>` for clients to
connect to. Maintains an in-memory append-only op log per file, detects
concurrent edits, applies last-write-wins, and broadcasts ops to peers.

For v1, state is in-memory only — server restart wipes everything.

```sh
uv run ifc-sync-server               # binds 127.0.0.1:8765
uv run ifc-sync-server --port 9000
```

See [`../../docs/DESIGN.md`](../../docs/DESIGN.md) section 7 for the design,
and [`../../docs/PROTOCOL.md`](../../docs/PROTOCOL.md) for the wire format.
