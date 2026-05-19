# ifc-live

**Real-time collaboration for IFC models.** Multiple users edit the same IFC file in Bonsai BIM, changes sync between them as they happen — no save, no push, no merge.

> ⚠️ **Status: pre-alpha.** Nothing works yet. This repo is being scaffolded toward [Milestone 1](docs/MILESTONE_1.md). Not yet usable.

---

## What this is

The open-source BIM ecosystem (IfcOpenShell, Bonsai BIM, FreeCAD) has no real-time multi-user editing story. Existing tools either treat IFC files as opaque blobs (Git, file sync) and produce nonsensical text-level conflicts, or require everyone to switch to a single proprietary editor (Revit Worksharing).

`ifc-live` fills that gap. It works the way Google Docs works: the document is never sent between users, only the operations that mutate it. Every change a user makes in their editor becomes a structured `IfcOp`, streamed over WebSocket to a sync server and broadcast to everyone else editing the same model.

Because IFC entities are addressed by stable GUIDs, most concurrent edits don't conflict — two users editing different walls, or different properties of the same wall, just work. The rare genuine conflicts (same attribute, same instant) are resolved last-write-wins with a full audit log.

The v1 target is Bonsai BIM only. Other editors come later.

## What this is not

- A new IFC editor (we integrate with existing editors)
- A file format (IFC is the format; we sync mutations to it)
- A replacement for ISO 19650 CDE workflows (that's planned for v2)
- Production-ready (see status above)

## Architecture in 30 seconds

```
Bonsai BIM A  ──┐                              ┌──  Bonsai BIM B
                │  WebSocket (JSON ops)        │
                └──►  ifc-sync server  ────────┘
                       (op log + LWW merge)
```

Each Bonsai instance runs an addon that wraps the live IfcOpenShell model, intercepts mutations, and emits ops. The server is a thin relay that appends ops to a per-file log, detects concurrent edits, applies last-write-wins, and broadcasts to peers.

See [`docs/DESIGN.md`](docs/DESIGN.md) for the full architecture.

## Repository layout

```
ifc-live/
├── packages/
│   ├── ifc-ops/              Pydantic data model for IfcOps
│   ├── ifc-sync-core/        SyncedIfcModel + op application
│   ├── ifc-sync-server/      FastAPI WebSocket relay
│   └── ifc-sync-bonsai/      Blender addon
├── docs/
│   ├── DESIGN.md             Architectural decisions and op model
│   ├── MILESTONE_1.md        Acceptance criteria for v1
│   ├── PROTOCOL.md           WebSocket message format
│   └── ROADMAP.md            Beyond v1
├── tests/
└── pyproject.toml            uv workspace root
```

## Getting started

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) for package management
- Blender 4.x with [Bonsai BIM](https://bonsai-bim.org/) installed (for the addon)

### Setup

```bash
git clone https://github.com/FelonBall/ifc-live.git
cd ifc-live
uv sync
```

### Running the server

```bash
uv run ifc-sync-server
# Listening on ws://localhost:8765
```

### Installing the Bonsai addon

```bash
uv run ifc-sync-bonsai-package
# Produces dist/ifc-sync-bonsai-<version>.zip

# In Blender: Edit → Preferences → Add-ons → Install → select the ZIP
# Enable "BIM: ifc-live"
```

### Running the demo

See [`docs/MILESTONE_1.md`](docs/MILESTONE_1.md#demo-script-the-acceptance-test) for the full demo script that exercises every supported operation.

## Development

### Running tests

```bash
uv run pytest                    # all tests
uv run pytest packages/ifc-ops   # one package
uv run pytest -k conflict        # by name
```

### Linting and type checking

```bash
uv run ruff check                # lint
uv run ruff format               # format
uv run pyright                   # type check (strict)
```

CI runs all three on every PR. PRs that don't pass don't merge.

### Working on the addon

The Bonsai addon can't be developed entirely outside Blender, but most of the logic (op interception, WebSocket client) is in `packages/ifc-sync-core` and is testable standalone. Use the addon package mostly for the Blender-specific glue: panels, operators, registration.

Bonsai dev workflow:

1. Make changes in `packages/ifc-sync-bonsai`
2. Run `uv run python -m ifc_sync_bonsai.package` to re-zip
3. In Blender: Preferences → Add-ons → find "ifc-live" → Remove → Install fresh ZIP → enable

A live-reload setup is on the roadmap.

## How it works (a bit more detail)

### The op model

Every mutation is one of a small closed set:

- `add_entity` — a new IFC entity appeared
- `delete_entity` — an entity was removed
- `modify_attribute` — an entity's direct attribute changed
- `set_property_value` — a property set value changed

Each op carries a `parent_op_id` — the server's op log HEAD as the client knew it when the op was created. The server uses this to detect concurrent edits.

### Conflict handling

Two ops are concurrent if they share a `parent_op_id` and were both received after that parent. The conflict matrix:

| Scenario | Resolution |
|---|---|
| Different entities | Both apply |
| Same entity, different attributes | Both apply |
| Same entity, same attribute | Last-write-wins, audit logged |
| Delete vs modify same entity | Delete wins, audit logged |
| Delete vs delete same entity | Idempotent |

LWW is applied silently but everything is recorded — overwritten values can be inspected and restored from the audit log.

### Why not CRDTs or OT?

CRDTs (Automerge, Yjs) and Operational Transform (Google Docs) both solve the general problem of "two clients edit a document concurrently". They're overkill for IFC.

The hard part of Google Docs is that positions shift: if Alice inserts a character at position 5, Bob's pending delete at position 7 needs to become a delete at position 8. That requires the transform function.

IFC doesn't have this problem. Entities are addressed by GUID, not position. A wall with GUID `3Hx9...` is always `3Hx9...`. Two clients can mutate the same model with no positional coupling at all. A simple op log with parent pointers and a small conflict matrix is sufficient. See [`docs/DESIGN.md`](docs/DESIGN.md) for the full reasoning.

## Roadmap

| Version | Focus |
|---|---|
| **v0.1 (M1)** | Two Bonsai instances on localhost, in-memory server, walls/slabs/doors/windows only |
| v0.2 (M2) | Persistent op log (SQLite), authentication, multi-machine deployment |
| v0.3 (M3) | FreeCAD addon, broader IFC entity coverage |
| v0.4 (M4) | Snapshot / version history with restore |
| v0.5 (M5) | Better conflict resolution UI; surface conflicts inline in Blender |
| v1.0 | CDE state machine (ISO 19650): WIP / Shared / Published / Archived |
| Future | AI assistant layer; federated discipline models; web-based viewer |

See [`docs/ROADMAP.md`](docs/ROADMAP.md) for details.

## Contributing

Contributions welcome, with the caveat that the project is in pre-alpha and the architecture is still settling. Before sending a substantial PR:

1. Read [`docs/DESIGN.md`](docs/DESIGN.md) to understand the op model and conflict rules
2. Read [`docs/MILESTONE_1.md`](docs/MILESTONE_1.md) to understand what's in scope for v1
3. Open an issue describing what you want to change before writing code

Small PRs (typo fixes, docs improvements, test additions) don't need an issue first — just send them.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for code style, commit conventions, and the PR checklist.

## License

[Apache License 2.0](LICENSE).

This project depends on, but does not include, IfcOpenShell (LGPL-3.0) and Bonsai BIM (LGPL-3.0). Their licenses apply to your use of those libraries.

## Acknowledgements

This project would not be possible without:

- [**IfcOpenShell**](https://ifcopenshell.org/) — the IFC schema and geometry library that underpins the open-source BIM ecosystem
- [**Bonsai BIM**](https://bonsai-bim.org/) — the Blender addon that makes native IFC editing possible
- [**buildingSMART**](https://www.buildingsmart.org/) — for stewarding the IFC standard as an open ISO specification
