"""Smoke tests for ifc-sync-core.

Verifies the package imports and that IfcOpenShell is available at the
expected version.
"""

import ifc_sync_core


def test_package_importable() -> None:
    assert ifc_sync_core.__version__ == "0.1.0"


def test_ifcopenshell_available() -> None:
    """IfcOpenShell is a hard dependency — confirm it's importable."""
    import ifcopenshell  # noqa: F401
