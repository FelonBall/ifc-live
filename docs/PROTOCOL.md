# Wire Protocol

> **Status:** Specification in progress. The shape below is the v1 plan from
> `DESIGN.md` section 4 — exact field names and types are subject to refinement
> as `ifc-ops` lands (Milestone 1 step 1) and the server is built (step 3).

## Transport

JSON over WebSocket. One WebSocket connection per `file_id`. Clients connect to:

```
ws://HOST:PORT/sync/<file_id>
```

For v1, `HOST` is always `localhost`/`127.0.0.1` and `PORT` defaults to `8765`.

## Message envelope

Every message is a JSON object with a `type` field that discriminates the
payload shape. All other fields depend on the type.

```json
{ "type": "hello", ... }
```

## Message types

### Client → Server

#### `hello`

Sent immediately after the WebSocket connects. Identifies the client and the
last op it knows about (for catch-up sync).

```json
{
  "type": "hello",
  "client_id": "01HM5...",
  "last_known_op_id": "01HM5..." | null
}
```

#### `op`

Sent whenever the client wants to mutate the model.

```json
{
  "type": "op",
  "envelope": {
    "schema_version": "1",
    "op_id": "01HM5...",
    "parent_op_id": "01HM4...",
    "file_id": "demo",
    "author": "01HM5...",
    "timestamp": 1716042000.123,
    "payload": { "kind": "add_entity", ... }
  }
}
```

See `DESIGN.md` section 3 for the full schema of `payload`.

### Server → Client

#### `sync`

Sent after `hello` to bootstrap the client's view of the op log.

```json
{
  "type": "sync",
  "ops": [ <IfcOpEnvelope>, ... ],
  "head_op_id": "01HM5..."
}
```

#### `ready`

Sent after `sync` to indicate steady state.

```json
{ "type": "ready" }
```

#### `op`

A broadcast of someone else's op (or a conflict-resolved version of the
client's own op).

```json
{
  "type": "op",
  "envelope": { ... },
  "server_position": 42,
  "resolved": false
}
```

If `resolved` is `true`, the op was modified by LWW conflict resolution and the
client should expect the values inside to differ from what was originally sent.

#### `op_ack`

Acknowledges receipt and assignment of a client-submitted op.

```json
{
  "type": "op_ack",
  "op_id": "01HM5...",
  "server_position": 42
}
```

#### `conflict_resolved`

Informational broadcast when LWW resolves a conflict. Clients use this to
surface a notification to the user.

```json
{
  "type": "conflict_resolved",
  "winning_op_id": "01HM5...",
  "losing_op_id": "01HM5...",
  "guid": "3Hx9...",
  "attribute": "Name"
}
```

## HTTP endpoints

These are debug aids, not part of the realtime protocol.

| Method | Path | Returns |
|---|---|---|
| `GET` | `/healthz` | `{"status": "ok"}` |
| `GET` | `/files` | List of known `file_id`s |
| `GET` | `/files/{file_id}/log` | Full op log as JSON |
| `GET` | `/files/{file_id}/audit` | Full audit log as JSON |

## Versioning

The wire format is versioned by the `schema_version` field on every envelope.
v1 declares `"1"`. Breaking changes increment this. Servers and clients refuse
to communicate across schema versions for v1; later versions may add
negotiation.
