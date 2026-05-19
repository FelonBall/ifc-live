# ifc-sync-core

The bridge between IfcOpenShell and the `ifc-live` wire format.

This package contains:
- `SyncedIfcModel` — a wrapper around `ifcopenshell.file` that intercepts
  every mutation and emits an `IfcOp` to a registered handler
- `apply_op(model, op)` — the inverse: given an `IfcOp`, mutate an
  IfcOpenShell file accordingly
- Serialization helpers — IFC value ↔ wire format (defined in `ifc-ops`)

See [`../../docs/DESIGN.md`](../../docs/DESIGN.md) section 6 for the design.
