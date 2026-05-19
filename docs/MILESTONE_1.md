# Milestone 1 — Two Bonsai Instances, Live Sync

**Status:** Not started
**Target:** Working end-to-end demo
**Depends on:** `DESIGN.md`

---

## Goal

Two instances of Blender + Bonsai BIM running on the same machine can edit the same IFC model simultaneously, and changes propagate between them in real time via a local sync server.

This milestone proves the core hypothesis of the project: that IfcOpenShell mutations can be intercepted, streamed, and re-applied cleanly enough to support live multi-user editing.

---

## Demo Script (the acceptance test)

A reviewer can perform the following sequence and observe the expected outcomes:

1. **Start the server.** Run `uv run ifc-sync-server` in a terminal. Server logs "Listening on ws://localhost:8765".
2. **Launch Blender instance A.** Install the `ifc-live` addon. Open Bonsai's "New Project" wizard, create a fresh IFC4 file. The ifc-live panel shows "Disconnected".
3. **Connect instance A.** In the ifc-live panel, set file_id to `demo` and click Connect. Panel shows "Connected — 1 client (you)".
4. **Launch Blender instance B.** Install the same addon. **Do not** create a new file. Open the ifc-live panel, set file_id to `demo`, click Connect. Within ~2 seconds, the project, site, building, and storey created in A appear in B. Panel shows "Connected — 2 clients".
5. **Add a wall in A.** Use Bonsai's wall tool to draw a wall. Within ~1 second, the wall appears in B's viewport with the same geometry, position, and properties.
6. **Modify the wall in B.** Select the wall in B, change its Name property to "Wall-North". Within ~1 second, A's viewport reflects the new name.
7. **Modify a property in A.** Open the wall's Property Sets, set `Pset_WallCommon.FireRating` to `REI 60`. Within ~1 second, B shows the updated property.
8. **Concurrent edit.** Both users select the wall at the same time. A changes the Name to "Wall-A-Edit". B changes the Name to "Wall-B-Edit" within ~500ms of A. The later-received value wins on both clients (LWW). The losing client sees a notification "Your edit to 'Name' was overridden by [other]".
9. **Add a door in A.** Use Bonsai's door tool to insert a door into the wall. The door, its opening, and the void relationship appear in B.
10. **Delete the wall in B.** The wall disappears from A. The door and opening referencing it remain in B's model (LWW: delete wins; orphan references are an accepted limitation for v1).
11. **Disconnect B, edit in A.** B clicks Disconnect. A adds three more walls. B clicks Connect again. Within ~3 seconds, B's model catches up — all three walls appear.
12. **Check the audit log.** Visit `http://localhost:8765/files/demo/audit` in a browser. See the LWW overwrite from step 8 recorded with both values, both authors, and timestamps.

All twelve steps must work without restarts, file saves, or any manual sync action.

---

## Acceptance Criteria

The milestone is complete when **all** of the following are true:

### Functional
- [ ] The full demo script above runs end-to-end without errors or restarts
- [ ] Add, modify, delete, and property-set operations sync in both directions
- [ ] Bootstrap sync (step 4) works — a fresh client receives the full op log and reaches the same state as connected clients
- [ ] Catch-up sync (step 11) works — a client that disconnects and reconnects gets only the ops it missed
- [ ] LWW conflict resolution is applied correctly and recorded in the audit log
- [ ] Disconnect / reconnect during an active session does not corrupt either client's model

### Non-functional
- [ ] Op latency (mutation in A → visible in B) is under 1 second for single-entity ops on a model with fewer than 1000 entities
- [ ] Server handles at least 5 concurrent client connections to the same file_id without dropping ops
- [ ] No client-side loops — applying an incoming op never re-emits that op
- [ ] No memory leaks over a 30-minute session with continuous editing (heap profile flat ±10MB)

### Code quality
- [ ] All four packages pass `ruff check` with no warnings
- [ ] All four packages pass `pyright --strict` with no errors
- [ ] Test coverage > 70% for `ifc-ops` and `ifc-sync-core`
- [ ] CI runs lint, type-check, and test on every PR

### Documentation
- [ ] `README.md` includes installation instructions, server start, and addon install
- [ ] `PROTOCOL.md` documents the WebSocket message format with examples
- [ ] Inline docstrings on every public function in `ifc-ops` and `ifc-sync-core`

---

## Out of Scope (Reaffirmed)

Things that are tempting to add but explicitly **not** part of M1:

- Persistent op storage — server restart wipes state, this is fine
- Authentication — no user accounts, no permissions
- Multi-machine deployment — localhost only
- Editors other than Bonsai
- IFC entities beyond walls, slabs, doors, windows, and their supporting structure
- Snapshot/checkpoint feature
- Conflict resolution UI beyond a simple notification
- Performance optimization beyond the 1-second/1000-entity bar above
- Cleaning up orphaned references after a delete (the wall-with-door scenario in step 10)
- A web UI for the audit log (the JSON endpoint is enough)

If we find ourselves working on any of these during M1, that's a signal to stop and re-scope.

---

## Implementation Order

A suggested order to build things. Each step should produce something runnable that can be exercised, even in isolation.

### Step 1 — `ifc-ops` package
The foundational data types. No dependencies on IfcOpenShell or anything else.

- Pydantic models for `IfcOpEnvelope`, all `IfcMutation` variants, `IfcValue` union
- JSON serialize/deserialize round-trip tests
- Schema version constant
- This package is publishable as a standalone library

**Done when:** can construct an op, serialize to JSON, parse back, get equal object.

### Step 2 — `ifc-sync-core` op application
Apply an op to an `ifcopenshell.file`. No interception, no server, just one-way "given this op and this model, mutate the model".

- `apply(model, op)` function for each mutation type
- `serialize_entity(entity) → dict` and `deserialize_value(value) → ifc_value`
- Round-trip tests: create a wall via op, apply to fresh model, serialize back, compare

**Done when:** can take a list of ops representing a small building and produce a valid `.ifc` file.

### Step 3 — `ifc-sync-server` minimal
Stateless WebSocket relay, no conflict logic yet.

- FastAPI app with `/sync/{file_id}` WebSocket endpoint
- In-memory op log per file_id
- `hello` / `sync` / `op` / `op_ack` message handling
- Broadcast to other clients
- HTTP debug endpoints

**Done when:** two `websocat` clients can connect, one sends an op, the other receives it.

### Step 4 — `ifc-sync-core` interception
The `SyncedIfcModel` wrapper. Used in isolation, without Blender.

- `SyncedIfcModel` wraps `ifcopenshell.file`
- `SyncedEntity` wraps entities, intercepts attribute sets
- `suppress_emission()` context manager
- Tests: create a wall via the wrapper, verify the right ops are emitted

**Done when:** can wrap a file, mutate it via the normal IfcOpenShell API, observe the right ops captured.

### Step 5 — Conflict detection and LWW
Add to server.

- Parent-pointer concurrency detection
- Conflict matrix logic
- LWW resolver
- Audit log

**Done when:** unit tests cover every row of the conflict matrix.

### Step 6 — `ifc-sync-bonsai` addon shell
The minimum Blender addon: a panel, a connect button, no actual sync yet.

- Blender addon `__init__.py` with operator registration
- N-panel UI with connection status and connect/disconnect
- WebSocket client on a background thread
- Logs incoming/outgoing messages to Blender's console

**Done when:** addon installs, panel appears, can connect to the server and exchange hello messages.

### Step 7 — Wire it all together
The integration step.

- Monkey-patch `bonsai.tool.Ifc.get`
- Hook `SyncedIfcModel` into the connection lifecycle
- Apply incoming ops to the local model with `suppress_emission`
- Trigger Bonsai viewport refresh after applying ops

**Done when:** demo script step 5 works (add wall in A, see it in B).

### Step 8 — Polish & demo prep
Make the demo script run cleanly start to finish.

- Bootstrap sync on connect
- Catch-up sync on reconnect
- LWW notifications in the UI
- Audit log endpoint
- Recording a demo video for the README

**Done when:** the full demo script runs without surprises in front of an audience.

---

## Known Unknowns (Things to Investigate Early)

These came up in `DESIGN.md` section 6 — they need real answers before step 7 can succeed. They should be spiked **before** step 4, not discovered during step 7.

1. **Does Bonsai's use of `ifcopenshell.api` flow through our wrapper?** Quickest check: read the relevant Bonsai source, look for `tool.Ifc.get().create_entity()` vs direct `ifcopenshell.api` calls. If `ifcopenshell.api` is heavily used, we may need to wrap it too.

2. **Active file detection.** How does the addon know which IFC file to sync when Bonsai has multiple loaded? Likely answer: only sync the active project file, expose a "this file is synced" toggle in the panel.

3. **Viewport refresh trigger.** What's the cleanest way to tell Bonsai "the IFC model changed, redraw"? Candidates: `bpy.ops.bim.refresh` (if it exists), tagging the Blender mesh as needing update, full scene reload.

4. **Op batching.** Bonsai operations sometimes do dozens of IfcOpenShell mutations in a tight loop (e.g. "extrude this profile" creates many entities). Decide: batch on the client (debounce 50ms), batch on the server (group by parent_op_id chains), or don't batch (and accept the WebSocket chatter).

Recommendation: spend half a day on each of these before starting step 4. The answers shape the rest of the implementation.

---

## Definition of Done

Milestone 1 is done when a reviewer who has never seen this project before can:

1. Clone the repo
2. Run `uv sync && uv run ifc-sync-server` in one terminal
3. Open two Blender instances, install the addon ZIP in each, connect both to the server
4. Edit a model in one and watch it sync to the other

…with no help, no missing steps in the README, and no warnings or errors in the console along the way.

When that works, we ship a v0.1 release and start planning M2.
