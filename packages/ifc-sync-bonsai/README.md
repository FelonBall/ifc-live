# ifc-sync-bonsai

The Blender addon that brings `ifc-live` real-time sync to Bonsai BIM.

The addon wraps Bonsai's live IfcOpenShell model with `SyncedIfcModel` (from
`ifc-sync-core`) so every mutation in the editor becomes an `IfcOp` sent over
WebSocket to the sync server. Incoming ops from peers are applied to the
local model, and the Blender viewport refreshes.

## Building the installable ZIP

```sh
uv run ifc-sync-bonsai-package
# produces dist/ifc-sync-bonsai-<version>.zip
```

## Installing in Blender

1. Open Blender 4.x (with Bonsai BIM already installed)
2. Edit → Preferences → Add-ons → Install
3. Select the ZIP from `dist/`
4. Enable "BIM: ifc-live"

The addon panel appears in the N-panel (`N` to toggle) under the "ifc-live" tab.

See [`../../docs/DESIGN.md`](../../docs/DESIGN.md) section 8 for the design.
