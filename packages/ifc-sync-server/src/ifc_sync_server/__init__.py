"""ifc-sync-server — WebSocket relay and op log for ifc-live.

This package contains the FastAPI app that clients connect to. It receives
ops over WebSocket, appends them to an in-memory log, detects concurrent
edits, applies last-write-wins, and broadcasts to peers.

For v1, the server is localhost-only and state is in-memory (lost on restart).
See ``docs/DESIGN.md`` section 7 for the design and ``docs/MILESTONE_1.md``
steps 3 and 5 for the work items.
"""

from __future__ import annotations

from ifc_sync_server.app import create_app
from ifc_sync_server.models import parse_client_message
from ifc_sync_server.state import FileState, StoredOp

__version__ = "0.1.0"

__all__ = [
    "FileState",
    "StoredOp",
    "create_app",
    "parse_client_message",
]
