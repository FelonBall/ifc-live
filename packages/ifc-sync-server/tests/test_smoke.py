"""Smoke tests for ifc-sync-server."""

import ifc_sync_server
from ifc_sync_server.cli import main


def test_package_importable() -> None:
    assert ifc_sync_server.__version__ == "0.1.0"


def test_cli_exits_nonzero_until_implemented() -> None:
    """Until M1 step 3 lands, the CLI prints a planned message and exits 1.

    This test exists so CI fails loudly if someone removes the stub without
    replacing it.
    """
    rc = main(["--port", "8765"])
    assert rc == 1
