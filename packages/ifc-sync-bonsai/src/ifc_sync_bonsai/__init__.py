"""ifc-live addon for Blender + Bonsai BIM.

This module is the Blender addon entry point. When loaded by Blender, the
``register()`` function will monkey-patch Bonsai's ``tool.Ifc.get`` to
return a ``SyncedIfcModel``, register operators and panels for the N-panel
UI, and prepare the WebSocket client.

See ``docs/DESIGN.md`` section 8 for the addon architecture and
``docs/MILESTONE_1.md`` steps 6 and 7 for the work items.
"""

from __future__ import annotations

bl_info = {
    "name": "ifc-live",
    "author": "ifc-live contributors",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "category": "BIM",
    "description": "Real-time collaboration for IFC models",
    "location": "View3D > N-Panel > ifc-live",
    "warning": "Pre-alpha — see docs/MILESTONE_1.md",
    "doc_url": "https://github.com/FelonBall/ifc-live",
}


def register() -> None:
    """Called by Blender when the addon is enabled.

    Responsibilities (M1 step 6 & 7):
      * Register Blender operators and panels
      * Monkey-patch ``bonsai.tool.Ifc.get`` to return a ``SyncedIfcModel``
      * Initialize the WebSocket client (but do not connect — wait for the
        user to click Connect in the panel)
    """
    # TODO(M1 step 6): implement
    pass


def unregister() -> None:
    """Called by Blender when the addon is disabled.

    Responsibilities:
      * Disconnect the WebSocket client cleanly
      * Restore the original ``bonsai.tool.Ifc.get`` reference
      * Unregister operators and panels
    """
    # TODO(M1 step 6): implement
    pass
