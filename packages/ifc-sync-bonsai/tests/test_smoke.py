"""Smoke tests for ifc-sync-bonsai.

The addon code is testable as a normal Python package up to the point where
it imports ``bpy``. These smoke tests stay above that line.
"""

import ifc_sync_bonsai


def test_addon_metadata() -> None:
    """``bl_info`` is the contract Blender uses to load the addon."""
    info = ifc_sync_bonsai.bl_info
    assert info["name"] == "ifc-live"
    assert info["category"] == "BIM"
    assert info["blender"][0] >= 4


def test_register_unregister_exist() -> None:
    """Blender will call these by name at addon enable/disable."""
    assert callable(ifc_sync_bonsai.register)
    assert callable(ifc_sync_bonsai.unregister)
