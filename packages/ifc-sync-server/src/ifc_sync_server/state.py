"""In-memory server state for the ifc-live sync server.

Contains the per-file op log, audit log, and connected client set. All state
is ephemeral — it is lost on server restart. Persistence is out of scope for
Milestone 1 (see ``docs/DESIGN.md`` §2 non-goals).

Because uvicorn runs a single asyncio event loop per worker, cooperative
scheduling serialises all mutations between ``await`` points. No explicit lock
is required for single-worker deployments.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import WebSocket

from ifc_ops import IfcOpEnvelope
from ifc_sync_server.models import AuditEntry


@dataclass
class StoredOp:
    """An op that has been appended to the server log.

    Args:
        server_position: 0-based index assigned in receive order (not
            client clock order — clock skew is irrelevant).
        envelope: The full ``IfcOpEnvelope`` as submitted by the client.
        resolved: ``True`` when LWW conflict resolution modifies the op's
            values (step 5). Always ``False`` in step 3.
    """

    server_position: int
    envelope: IfcOpEnvelope
    resolved: bool = False


@dataclass
class FileState:
    """All server-side state for a single ``file_id``.

    Args:
        file_id: The identifier for the IFC file this state tracks.
        op_log: Append-only list of stored ops in server-position order.
        audit_log: Conflict-resolution records (empty until step 5).
        clients: Currently connected WebSocket connections for this file.
    """

    file_id: str
    op_log: list[StoredOp] = field(default_factory=list)
    audit_log: list[AuditEntry] = field(default_factory=list)
    clients: set[WebSocket] = field(default_factory=set)

    def ops_since(self, last_known_op_id: str | None) -> list[StoredOp]:
        """Return all ops after ``last_known_op_id``, or the full log.

        Scans the op log linearly for the matching ``op_id``. Falls back to
        the full log when ``last_known_op_id`` is ``None`` or absent — this
        handles fresh connections and clients that reconnect after a server
        restart with a stale op_id.

        Args:
            last_known_op_id: The ``op_id`` of the last op the client has
                applied, or ``None`` for a full sync.

        Returns:
            All ``StoredOp`` entries whose position is strictly after the
            matched entry, in server-position order.
        """
        if last_known_op_id is None:
            return list(self.op_log)
        for i, stored in enumerate(self.op_log):
            if str(stored.envelope.op_id) == last_known_op_id:
                return list(self.op_log[i + 1 :])
        return list(self.op_log)

    @property
    def head_op_id(self) -> str | None:
        """``op_id`` of the most recently appended op, or ``None`` if empty."""
        return str(self.op_log[-1].envelope.op_id) if self.op_log else None
