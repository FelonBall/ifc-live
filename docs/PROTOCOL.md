# Wire Protocol

> **Status:** Envelope and payload schemas are final as of Milestone 1 step 1
> (`ifc-ops` package implemented and tested). Server message types (`sync`,
> `ready`, `op_ack`, `conflict_resolved`) remain provisional until step 3.

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

See [Op payload types](#op-payload-types) below for the full `payload` schema.

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

## Op payload types

The `payload` field of every `IfcOpEnvelope` is one of four mutation types,
discriminated by `kind`.

### `IfcValue` types

Every attribute value and property value is an `IfcValue` — a tagged object
discriminated by `kind`:

| `kind`    | Extra fields          | Notes |
|-----------|-----------------------|-------|
| `string`  | `value: str`          | |
| `int`     | `value: int`          | |
| `float`   | `value: float`        | |
| `bool`    | `value: bool`         | |
| `enum`    | `value: str`          | String token, e.g. `"SOLIDWALL"` |
| `ref`     | `guid: str`           | IFC GlobalId of the referenced entity |
| `list`    | `values: [IfcValue…]` | Recursive; used for coordinates, sets, etc. |
| `null`    | _(none)_              | Unset / `$` in STEP |

### `add_entity`

Creates a new IFC entity. All geometry is expressed as `IfcRef` values — the
referenced placement and representation entities must arrive (as their own
`add_entity` ops) before this op is applied.

```json
{
  "kind": "add_entity",
  "guid": "3fSEzHa$D1Hv_MlW1vNfSa",
  "ifc_type": "IfcWall",
  "attributes": {
    "Name":             { "kind": "string", "value": "Wall-N" },
    "PredefinedType":   { "kind": "enum",   "value": "SOLIDWALL" },
    "ObjectType":       { "kind": "null" },
    "ObjectPlacement":  { "kind": "ref",    "guid": "PlacGuid000001" },
    "Representation":   { "kind": "ref",    "guid": "RepGuid0000001" }
  }
}
```

### `delete_entity`

Removes an entity. `previous_snapshot` is a raw JSON object with the entity's
attribute values at deletion time, stored verbatim for audit/undo.

```json
{
  "kind": "delete_entity",
  "guid": "3fSEzHa$D1Hv_MlW1vNfSa",
  "previous_snapshot": {
    "GlobalId": "3fSEzHa$D1Hv_MlW1vNfSa",
    "Name": "Wall-N",
    "PredefinedType": "SOLIDWALL"
  }
}
```

### `modify_attribute`

Changes a single direct attribute on an existing entity.

```json
{
  "kind": "modify_attribute",
  "guid": "3fSEzHa$D1Hv_MlW1vNfSa",
  "attribute": "Name",
  "previous_value": { "kind": "string", "value": "Wall-N" },
  "new_value":      { "kind": "string", "value": "Wall-North" }
}
```

### `set_property_value`

Sets a property inside a named property set. `previous_value` is `null` (JSON
`null`, not the `IfcNull` kind) when the property did not exist before.

```json
{
  "kind": "set_property_value",
  "entity_guid": "3fSEzHa$D1Hv_MlW1vNfSa",
  "pset_name": "Pset_WallCommon",
  "property_name": "FireRating",
  "previous_value": null,
  "new_value": { "kind": "string", "value": "REI 60" }
}
```

---

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
