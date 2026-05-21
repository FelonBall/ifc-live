"""Smoke tests for ifc-sync-server."""

import ifc_sync_server


def test_package_importable() -> None:
    """Package imports cleanly and exposes the expected version string."""
    assert ifc_sync_server.__version__ == "0.1.0"
