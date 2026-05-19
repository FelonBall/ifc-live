"""Package the Bonsai addon into a Blender-installable ZIP.

Blender addons are distributed as ZIPs whose top-level directory contains
an ``__init__.py`` with a ``bl_info`` dict. This script produces such a ZIP
from the ``ifc_sync_bonsai`` source tree, vendoring its workspace and
external dependencies inline so Blender can install it without `pip`.

Usage:

    uv run ifc-sync-bonsai-package
    # writes dist/ifc-sync-bonsai-<version>.zip

TODO(M1 step 6):
    * Vendor ``ifc_sync_core`` and ``ifc_ops`` into the addon ZIP
    * Vendor pure-Python deps (``websockets``, ``pydantic``) — Blender 4.x
      ships these for some addons, but not reliably. Bundling them is safer.
    * Verify the resulting ZIP installs cleanly in a stock Blender 4.x
"""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "ifc-sync-bonsai-package is not implemented yet.\nSee docs/MILESTONE_1.md step 6.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
