# ifc-live — Design Document

**Status:** Draft v0.1
**Last updated:** 2026-05-17
**License of this project:** Apache 2.0

---

## 1. Problem Statement

The open-source BIM ecosystem (IfcOpenShell, Bonsai BIM, FreeCAD) is mature for single-user editing but has no real-time multi-user collaboration story. Teams currently work around this with file-based workflows: a model is checked out, edited, checked back in, and merged manually. This is error-prone, slow, and incompatible with how modern teams work.

Existing tools that attempt collaboration in BIM either:

- Treat IFC files as opaque blobs and diff them as text (Git, file sync tools), producing meaningless conflicts because IFC is an entity graph, not a sequence of lines
- Require everyone to use a single proprietary editor (Revit Worksharing, BIM 360)
- Provide federation and review but no live co-editing (Speckle, BIMcollab)

### What we are building

**`ifc-live` is a real-time synchronization service for IFC models.** Multiple users editing the same IFC model in their preferred editor (Bonsai BIM in v1) see each other's changes propagated live, with no manual push/pull step.

The design follows the Google Docs model: the document is never sent between users — only the operations that mutate it. Every mutation is captured as a structured `IfcOp`, streamed over WebSocket to a sync server, and broadcast to all other connected editors.

### Non-goals for v1

- A new IFC editor (we integrate with existing editors, we don't replace them)
- Multi-editor support beyond Bonsai (FreeCAD, Vectorworks, etc. come later)
- Authentication, user management, or permissions
- Multi-machine deployment (v1 is localhost only)
- Persistent op storage across server restarts
- Full ISO 19650 CDE workflow (WIP/Shared/Published state machine)
- AI assistant layer
- Conflict-resolution UI beyond simple last-write-wins + audit log
- Federated discipline models
- Browser-based editing or visualization

These are explicitly punted to future versions. The goal of v1 is to prove the core sync model works end-to-end with one editor on one machine.

---

## 2. Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│  Blender + Bonsai BIM (instance A)                           │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  ifc-live Bonsai addon                                  │ │
│  │                                                         │ │
│  │  ┌──────────────────────┐  ┌─────────────────────────┐ │ │
│  │  │  SyncedIfcModel       │  │  WebSocket client      │ │ │
│  │  │  (wraps the live IFC  │──│  (emits ops, applies   │ │ │
│  │  │   model, intercepts   │  │   incoming ops)        │ │ │
│  │  │   every mutation)     │  └─────────────────────────┘ │ │
│  │  └──────────────────────┘                              │ │
│  └────────────────────────────────────────────────────────┘ │
└───────────────────────────────┬──────────────────────────────┘
                                │ WebSocket (JSON ops)
                                │
┌───────────────────────────────▼──────────────────────────────┐
│  ifc-live sync server (FastAPI + websockets)                 │
│                                                              │
│  ┌──────────────────────┐  ┌─────────────────────────────┐  │
│  │  Op log (in-memory)   │  │  Audit log (in-memory)     │  │
│  │  Append-only          │  │  Records LWW overwrites    │  │
│  └──────────────────────┘  └─────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Conflict detector + LWW resolver                       │  │
│  └────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Broadcast hub                                          │  │
│  └────────────────────────────────────────────────────────┘  │
└───────────────────────────────┬──────────────────────────────┘
                                │ WebSocket
┌───────────────────────────────▼──────────────────────────────┐
│  Blender + Bonsai BIM (instance B)                           │
│  (same addon as A)                                           │
└──────────────────────────────────────────────────────────────┘
```

### Data flow

1. User edits the model in Bonsai. Bonsai calls IfcOpenShell APIs to mutate the in-memory IFC model.
2. `SyncedIfcModel` (the addon's wrapper) intercepts each mutation and emits a structured `IfcOp`.
3. The WebSocket client sends the op to the sync server.
4. The server appends the op to the in-memory op log, checks for conflicts against concurrent ops, applies the LWW policy if needed, and broadcasts the resulting op(s) to all other connected clients.
5. Other clients receive the op and apply it to their local IFC model via the inverse of the `SyncedIfcModel` interception path — applying it directly to IfcOpenShell without re-emitting.
6. Bonsai's viewport refreshes on the next redraw.

### Source of truth

For v1, **the server's op log is the source of truth.** Local files on disk are scratch — they may be exported on demand but are not authoritative. Server restart wipes state (this is accepted for v1).

---

## 3. The IfcOp Data Model

The op model is the most load-bearing part of the design. Everything else flows from it.

### Design principles

- **Closed set.** Every possible mutation is one of a finite, enumerated set of op types. No free-form payloads.
- **GUID-addressed.** Every op references entities by IFC `GlobalId`, never by IfcOpenShell entity ID or list index. GUIDs are stable; entity IDs are not.
- **Self-describing.** Every op contains enough information to be applied without consulting external state, with the exception of GUID lookups.
- **Versioned.** Every op carries a `schema_version` field. Op format changes are explicit.
- **Reversible.** Every op records the previous value of what it changed, so the audit log can reconstruct prior states.

### Op envelope

```python
SCHEMA_VERSION: Literal["1"] = "1"   # module-level constant; also set on every envelope

class IfcOpEnvelope(BaseModel):
    schema_version: Literal["1"] = "1"
    op_id: UUID                       # UUIDv7, time-ordered
    parent_op_id: UUID | None = None  # None for the first op in a session
    file_id: str                      # which IFC file this op targets
    author: str                       # client session id (no real users in v1)
    timestamp: float                  # client clock, unix seconds
    payload: IfcMutation
```

`parent_op_id` defaults to `None` so callers don't have to pass it explicitly when
opening a fresh session.

### Mutation types

```python
class AddEntity(BaseModel):
    kind: Literal["add_entity"] = "add_entity"
    guid: str                         # IFC GlobalId
    ifc_type: str                     # e.g. "IfcWall", "IfcDoor"
    attributes: dict[str, IfcValue]   # IFC attribute values, GUID-referenced

class DeleteEntity(BaseModel):
    kind: Literal["delete_entity"] = "delete_entity"
    guid: str
    previous_snapshot: dict[str, Any] # full entity state for audit/undo (raw Python
                                      # primitives, not IfcValue-typed — audit-only,
                                      # not intended for entity reconstruction)

class ModifyAttribute(BaseModel):
    kind: Literal["modify_attribute"] = "modify_attribute"
    guid: str
    attribute: str                    # e.g. "Name", "ObjectType"
    previous_value: IfcValue
    new_value: IfcValue

class SetPropertyValue(BaseModel):
    kind: Literal["set_property_value"] = "set_property_value"
    entity_guid: str
    pset_name: str                    # e.g. "Pset_WallCommon"
    property_name: str                # e.g. "FireRating"
    previous_value: IfcValue | None   # None when the property is new
    new_value: IfcValue

# Discriminated on the `kind` field — deserializer dispatches without
# inspecting every variant.
IfcMutation = Annotated[
    AddEntity | DeleteEntity | ModifyAttribute | SetPropertyValue,
    Field(discriminator="kind"),
]
```

### IfcValue

`IfcValue` is a tagged union representing the value types IFC supports. Initial scope:

```python
class IfcString(BaseModel):  kind: Literal["string"] = "string";  value: str
class IfcInt(BaseModel):     kind: Literal["int"]    = "int";     value: int
class IfcFloat(BaseModel):   kind: Literal["float"]  = "float";   value: float
class IfcBool(BaseModel):    kind: Literal["bool"]   = "bool";    value: bool
class IfcEnum(BaseModel):    kind: Literal["enum"]   = "enum";    value: str
class IfcRef(BaseModel):     kind: Literal["ref"]    = "ref";     guid: str
class IfcList(BaseModel):    kind: Literal["list"]   = "list";    values: list[IfcValue]
class IfcNull(BaseModel):    kind: Literal["null"]   = "null"

# Same discriminated-union pattern as IfcMutation. IfcList is recursive
# (IfcValue → IfcList → IfcValue …); model_rebuild() is called after the
# union is defined to resolve the forward reference.
IfcValue = Annotated[
    IfcString | IfcInt | IfcFloat | IfcBool | IfcEnum | IfcRef | IfcList | IfcNull,
    Field(discriminator="kind"),
]
```

Complex geometry values (placements, profiles, swept solids) are serialized as nested entity references — i.e. when a wall is added, the placement and representation it references are added as separate entities first via their own `AddEntity` ops.

### Op scope for v1

For v1, the only IFC entities we explicitly support are:

- `IfcWall`, `IfcSlab`, `IfcDoor`, `IfcWindow`
- The placement and representation entities they reference (`IfcLocalPlacement`, `IfcAxis2Placement3D`, `IfcDirection`, `IfcExtrudedAreaSolid`, etc.)
- Spatial structure entities (`IfcProject`, `IfcSite`, `IfcBuilding`, `IfcBuildingStorey`)
- Relationships (`IfcRelContainedInSpatialStructure`, `IfcRelVoidsElement`, `IfcRelFillsVoid`, `IfcRelDefinesByProperties`)
- Property sets (`IfcPropertySet`, `IfcPropertySingleValue`)

Other IFC entities will pass through as generic `AddEntity` / `ModifyAttribute` ops with their attributes serialized verbatim — but won't get specialized handling. The four supported building elements are what the v1 demo will exercise.

### Non-root entity identity

Only `IfcRoot` subclasses carry a stable `GlobalId`. Many IFC entities that
building elements depend on — `IfcLocalPlacement`, `IfcAxis2Placement3D`,
`IfcDirection`, profile definitions, etc. — do not inherit `IfcRoot` and have
no built-in stable identity. Because every op references entities by GUID,
these entities need one too.

**Synthetic GUIDs** are assigned when an `AddEntity` op is applied to a
non-root type. The op's `guid` field carries the synthetic GUID, and the
applier registers it in a per-model non-root registry instead of writing it to
`entity.GlobalId`.

The registry is a `WeakKeyDictionary` keyed by `ifcopenshell.file`, so each
model has its own isolated mapping and the entries are garbage-collected when
the model is released:

```python
# maps entity STEP ID (int) → synthetic GUID (str), per model
_entity_to_guid: WeakKeyDictionary[ifcopenshell.file, dict[int, str]]

# reverse map: synthetic GUID → STEP ID, per model
_guid_to_entity_id: WeakKeyDictionary[ifcopenshell.file, dict[str, int]]
```

**Lifecycle:** The registry is per-session only. STEP entity IDs are assigned
by IfcOpenShell at creation time and are not stable across IFC save/reload
(files can be renumbered on write). The registry is never persisted; after a
reload the synthetic GUIDs would need to be re-established by replaying the op
log.

### IfcValue → NominalValue type mapping

`SetPropertyValue` stores its `new_value` as an `IfcValue`, but
`IfcPropertySingleValue.NominalValue` must be a typed IFC measure wrapper.
The mapping used by the applier:

| `IfcValue` variant | IFC `NominalValue` wrapper |
|---|---|
| `IfcString` | `IfcLabel` |
| `IfcFloat` | `IfcReal` |
| `IfcInt` | `IfcInteger` |
| `IfcBool` | `IfcBoolean` |
| `IfcRef` | ❌ not supported — raises `ValueError` |
| `IfcList` | ❌ not supported — raises `ValueError` |

`IfcRef` and `IfcList` are rejected because `NominalValue` must be a scalar.
Callers that need to store a non-scalar value should model it as a nested
entity via a separate `AddEntity` op.

### Enum/string handling

`serialize_value` cannot distinguish IFC enum-typed attributes from plain
string attributes at runtime without schema introspection. All Python `str`
values therefore emit as `IfcString` on the wire — `IfcEnum` is never produced
automatically.

On deserialization, `IfcOpenShell` accepts plain Python strings for
enum-typed attributes, so the round-trip is lossless: an enum attribute
serialized as `IfcString` and then deserialized back via `setattr` will be
accepted by IfcOpenShell without error.

`IfcEnum` exists in the wire format for callers that _explicitly_ know an
attribute is enum-typed (for example, the `SyncedIfcModel` interception layer
in Step 4 could inspect the schema and emit `IfcEnum` where appropriate). The
`deserialize_value` function treats `IfcEnum` identically to `IfcString` —
both produce a plain Python string.

---

## 4. Synchronization Protocol

### Transport

JSON over WebSocket. Connection lifecycle:

```
Client → Server:  WS connect to ws://localhost:PORT/sync/<file_id>
Client → Server:  { type: "hello", client_id, last_known_op_id | null }
Server → Client:  { type: "sync", ops: [...] }   # all ops since last_known_op_id
Server → Client:  { type: "ready" }
< steady state >
Client → Server:  { type: "op", envelope: IfcOpEnvelope }
Server → Client:  { type: "op_ack", op_id, server_op_id }
Server → Client:  { type: "op", envelope: IfcOpEnvelope }   # ops from others
```

All messages are JSON objects with a `type` discriminator. Schemas are defined in `packages/ifc-ops/`.

### Op ordering

The server maintains a single linear op log per `file_id`. Ops are assigned a server-side monotonic position in the order they're received (not the order they were created by clients — clock skew is irrelevant).

Every op carries `parent_op_id` — the op_id of the HEAD the client believed was current when it created this op. Two ops with the same `parent_op_id` from different clients are concurrent and trigger conflict detection.

### Conflict detection

When the server receives op `B` with `parent_op_id = P`, it looks at all ops in the log with position > position(P) — call this set `C` (the "concurrent ops"). For each op `A` in `C`:

- If `A` and `B` touch different entity GUIDs → no conflict, `B` applies as-is
- If `A` and `B` touch the same entity but different attributes → no conflict, `B` applies as-is
- If `A` and `B` touch the same entity and same attribute → **conflict**, apply LWW policy
- If one is a `DeleteEntity` and the other modifies the same GUID → **conflict** (delete wins under LWW with overwrite logged)

### Last-write-wins policy

The server's receive order is authoritative. The later-received op wins. When LWW overwrites a value:

1. The losing op is still applied to the op log (so it appears in history)
2. The overwrite is recorded in the audit log with:
   - The losing op's full envelope
   - The winning op's full envelope
   - The attribute(s) overwritten
   - The losing value (preserved for potential restore)
3. A `conflict_resolved` event is broadcast to all clients (informational; clients display a notification but don't change behavior)

### Broadcast

After applying an op to the log and resolving conflicts:

- The op is broadcast to all connected clients **except** the originator (the originator already applied it locally)
- The originator receives `op_ack` with the server-assigned position
- If the op was modified by conflict resolution (LWW overwrite), the broadcast includes the resolved value

---

## 5. Conflict Resolution Rules

The conflict matrix, explicitly:

| Op A | Op B (same parent as A) | Touch same entity? | Touch same attribute? | Resolution |
|---|---|---|---|---|
| `add_entity` X | `add_entity` Y | No | — | ✅ Both apply |
| `add_entity` X | `add_entity` X | Yes (GUID collision) | — | ⚠️ LWW: later op wins, log to audit |
| `modify_attribute` X.a | `modify_attribute` Y.a | No | No | ✅ Both apply |
| `modify_attribute` X.a | `modify_attribute` X.b | Yes | No | ✅ Both apply |
| `modify_attribute` X.a | `modify_attribute` X.a | Yes | Yes | ⚠️ LWW: later wins, log to audit |
| `set_property_value` X.p1.v | `set_property_value` X.p1.v | Yes | Yes | ⚠️ LWW: later wins, log to audit |
| `set_property_value` X.p1.v | `set_property_value` X.p2.v | Yes | No | ✅ Both apply |
| `delete_entity` X | `modify_attribute` X.a | Yes | — | ⚠️ Delete wins; modify is logged but discarded |
| `delete_entity` X | `delete_entity` X | Yes | — | ✅ Idempotent (second is no-op) |

GUID collisions for `add_entity` should be vanishingly rare with UUIDv4-derived IFC GlobalIds, but we handle them defensively.

---

## 6. The `SyncedIfcModel` Interception Strategy

### Goal

Wrap `ifcopenshell.file` such that every mutation of the model emits an `IfcOp` without changing the API surface Bonsai uses. Bonsai code should not need to be modified.

### Approach

Bonsai accesses the live IFC model via `bonsai.tool.Ifc.get()`. We monkey-patch this function at addon load time to return a `SyncedIfcModel` instance instead of the raw `ifcopenshell.file`.

```python
# Simplified sketch
import ifcopenshell
import bonsai.tool as tool

class SyncedIfcModel:
    def __init__(self, underlying: ifcopenshell.file, op_emitter):
        self._inner = underlying
        self._emit = op_emitter

    def create_entity(self, ifc_type, **kwargs):
        entity = self._inner.create_entity(ifc_type, **kwargs)
        self._emit(AddEntity(
            guid=getattr(entity, "GlobalId", None),
            ifc_type=ifc_type,
            attributes=serialize_attributes(entity)
        ))
        return wrap_entity(entity, self)

    def remove(self, entity):
        snapshot = serialize_entity(entity)
        self._emit(DeleteEntity(guid=entity.GlobalId, previous_snapshot=snapshot))
        self._inner.remove(entity)

    def __getattr__(self, name):
        # Pass through everything else
        return getattr(self._inner, name)
```

Entities returned by `create_entity` and `by_guid` are wrapped in a proxy that intercepts attribute sets:

```python
class SyncedEntity:
    def __init__(self, inner_entity, model):
        object.__setattr__(self, "_inner", inner_entity)
        object.__setattr__(self, "_model", model)

    def __setattr__(self, name, value):
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        old = getattr(self._inner, name)
        if old != value:
            self._model._emit(ModifyAttribute(
                guid=self._inner.GlobalId,
                attribute=name,
                previous_value=serialize_value(old),
                new_value=serialize_value(value),
            ))
        setattr(self._inner, name, value)

    def __getattr__(self, name):
        return getattr(self._inner, name)
```

### Applying incoming ops

When the addon receives an op from the server, it must apply it to the IFC model **without re-emitting** (otherwise we'd loop). The `SyncedIfcModel` has a context manager:

```python
with model.suppress_emission():
    apply_op_directly(model._inner, incoming_op)
bpy.ops.bim.refresh_ifc()  # or equivalent — tell Bonsai to redraw
```

### Open questions for implementation

These need to be resolved during Milestone 1 implementation, not in the design doc:

- Bonsai uses `ifcopenshell.api` for many operations rather than calling `file.create_entity` directly. Do we need to wrap the `ifcopenshell.api` module as well, or does its internal use of `file.create_entity` flow through our wrapper naturally?
- How does the addon know which IFC file is "active" and should be synced? Bonsai supports multiple loaded files.
- What's the right Bonsai/Blender hook to trigger viewport refresh after applying an incoming op?
- Some Bonsai operations emit many small IfcOpenShell calls in a tight loop. Do we batch ops at the client before sending, or rely on WebSocket batching?

---

## 7. Server Design

### Components

- **WebSocket handler:** Accepts connections, dispatches messages, maintains per-file client lists
- **Op log:** Per `file_id`, an append-only list of `IfcOpEnvelope`s with assigned server positions
- **Audit log:** Per `file_id`, records of LWW overwrites
- **Conflict detector:** Given a new op and the log, returns the set of concurrent ops and conflicts
- **LWW resolver:** Given a conflict, decides which value wins and produces audit log entries
- **Broadcast hub:** Sends messages to all clients of a `file_id` except the originator

### State (v1, in-memory)

```python
class FileState:
    file_id: str
    op_log: list[StoredOp]               # ordered by server position
    audit_log: list[AuditEntry]
    clients: set[WebSocketConnection]
    head_op_id: UUID | None              # latest op_id

class StoredOp:
    server_position: int
    envelope: IfcOpEnvelope
    resolved: bool                       # was this op modified by LWW?
```

### HTTP endpoints (v1)

- `GET /files` — list known file_ids (debug only)
- `GET /files/{file_id}/log` — return full op log as JSON (debug only)
- `GET /files/{file_id}/audit` — return audit log (debug only)
- `GET /healthz` — liveness check

All real-time traffic goes through the single WebSocket endpoint `WS /sync/{file_id}`.

---

## 8. Bonsai Addon Design

### Distribution

A standard Blender addon, packaged as a ZIP. Installable via Blender's Preferences → Add-ons → Install. The addon depends on `ifcopenshell` (already present alongside Bonsai) and a small set of pure-Python libraries shipped inside the ZIP (`pydantic`, `websockets`).

### Components

- `__init__.py` — Blender addon entry point, registers operators and panels
- `client.py` — WebSocket client, runs on a background thread
- `synced_model.py` — `SyncedIfcModel` + `SyncedEntity` wrappers
- `interception.py` — Monkey-patch logic for `bonsai.tool.Ifc.get`
- `apply.py` — Apply incoming ops to the local model
- `panel.py` — Blender UI panel showing connection status, peer count, audit log

### UI surface (minimal for v1)

A single panel in the N-panel ("ifc-live"):

- Connection status: Connected / Disconnected / Connecting
- Server URL field (defaults to `ws://localhost:8765`)
- File ID field
- Connect / Disconnect button
- Recent activity log (last 20 ops, with author + timestamp)
- Conflict notifications (when LWW resolves a conflict involving this client)

### Lifecycle

1. User installs addon, opens Blender, loads an IFC file via Bonsai as normal
2. User opens ifc-live panel, sets file_id, clicks Connect
3. Addon monkey-patches `bonsai.tool.Ifc.get`, replaces active model with `SyncedIfcModel`
4. Addon opens WebSocket to server, sends `hello` with `last_known_op_id = null`
5. Server responds with `sync` containing the full op log (if any)
6. Addon applies all ops to bootstrap the local model into sync
7. Addon enters steady state — emits ops on local mutations, applies ops from server

---

## 9. Tooling & Repo Layout

### Top-level structure

```
ifc-live/
├── packages/
│   ├── ifc-ops/                  # Pydantic models, no runtime deps on IFC
│   ├── ifc-sync-core/            # SyncedIfcModel, op apply/serialize, depends on ifc-ops + ifcopenshell
│   ├── ifc-sync-server/          # FastAPI app, depends on ifc-ops
│   └── ifc-sync-bonsai/          # Blender addon, depends on ifc-sync-core
├── docs/
│   ├── DESIGN.md                 # this file
│   ├── PROTOCOL.md               # WebSocket message format spec
│   └── ROADMAP.md
├── tests/
│   ├── unit/
│   └── integration/
├── examples/
├── .github/workflows/
├── pyproject.toml                # uv workspace root
├── LICENSE                       # Apache 2.0
├── README.md
└── CONTRIBUTING.md
```

### Tooling

- **Package manager:** `uv` (with workspace support)
- **Linter + formatter:** `ruff`
- **Type checker:** `pyright` (strict mode)
- **Tests:** `pytest`, with `pytest-asyncio` for WebSocket tests
- **CI:** GitHub Actions — lint, type-check, test on every PR
- **Python version:** 3.11+ (matches Bonsai's Blender 4.x requirement)

---

## 10. Glossary

- **IFC:** Industry Foundation Classes, ISO 16739, the open data model for BIM
- **IfcOpenShell:** Open-source library implementing the IFC schema, with Python bindings
- **Bonsai BIM:** Blender addon (formerly BlenderBIM) that uses IfcOpenShell for native IFC editing
- **GlobalId / GUID:** A 22-character base64-encoded UUID, IFC's permanent identity for an entity
- **IfcOp:** Our internal representation of a single mutation to an IFC model
- **Op log:** The append-only sequence of all IfcOps for a file, server-authoritative
- **Audit log:** A record of conflict resolutions, distinct from the op log
- **LWW:** Last-write-wins, the conflict resolution policy for v1
- **HEAD:** The most recent op in the log
- **Parent op:** The op a client's view of the model was based on when it created a new op
- **CDE:** Common Data Environment, ISO 19650 — out of scope for v1
- **Pset / Property set:** IFC's mechanism for attaching arbitrary structured data to entities

---

## Appendix A — Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Bonsai's internal use of IfcOpenShell doesn't flow through our wrapper | Identify all entry points during M1 implementation; wrap `ifcopenshell.api` if needed |
| High-frequency op streams overwhelm WebSocket | Client-side batching with short debounce (e.g. 50ms); evaluate during M1 |
| IFC entity serialization is complex for nested types | Start with the four supported building elements; let other entity types pass through as opaque attribute bags |
| Server restart loses all state | Accepted for v1. M2 introduces SQLite persistence |
| Concurrent edits to the same file_id from a single user (two Blenders, same model) get into a loop | Use `suppress_emission` context manager rigorously when applying incoming ops |
| LWW silently destroys work | Audit log preserves every overwritten value; UI shows notifications |

## Appendix B — Out of Scope (Explicit)

For absolute clarity, these are **not** part of v1:

- Authentication, authorization, user accounts, permissions
- Multi-machine deployment (server and clients are all on localhost)
- Persistent storage of the op log across server restarts
- File-based workflow (the on-disk .ifc is not authoritative)
- Snapshot/version-pinning ("save this revision")
- Branching, merging across branches
- CDE state machine (WIP/Shared/Published/Archived)
- AI assistant features
- Web UI of any kind (no version history browser, no conflict resolution UI)
- Editor support beyond Bonsai BIM
- IFC2x3 native support (import-only, upgraded to IFC4)
- IFC4.3 features (infrastructure, alignments)
- Federated discipline models
- Clash detection
- Conflict resolution beyond automatic LWW
- Performance optimization for models > 10k entities
- Entity reconstruction from audit log snapshots (`previous_snapshot` stores raw
  Python primitives for human-readable audit; it is not a reversible serialization
  format and is not designed to rebuild entities)
