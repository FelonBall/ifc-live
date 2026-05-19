"""Smoke tests for the ifc-ops package.

These exist so CI has something to run before Milestone 1 step 1 is complete.
Replace and expand as the op model takes shape.
"""

from ifc_ops import SCHEMA_VERSION


def test_schema_version_is_one() -> None:
    """The wire format version starts at 1 and changes deliberately."""
    assert SCHEMA_VERSION == "1"


def test_package_importable() -> None:
    """The ifc-ops package can be imported with no side effects."""
    import ifc_ops

    assert ifc_ops.__version__ == "0.1.0"
