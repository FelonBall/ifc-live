"""In-memory server state for the ifc-live sync server.

Contains the per-file op log, audit log, and connected client set. All state
is ephemeral — it is lost on server restart. Persistence is out of scope for
Milestone 1 (see ``docs/DESIGN.md`` §2 non-goals).

Because uvicorn runs a single asyncio event loop per worker, cooperative
scheduling serialises all mutations between ``await`` points. No explicit lock
is required for single-worker deployments.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from uuid import UUID

from fastapi import WebSocket

from ifc_ops import (
    AddEntity,
    DeleteEntity,
    IfcMutation,
    IfcOpEnvelope,
    IfcValue,
    ModifyAttribute,
    SetPropertyValue,
)
from ifc_sync_server.models import AuditEntry

# ---------------------------------------------------------------------------
# Conflict detection helpers (module-level for testability)
# ---------------------------------------------------------------------------


def _get_op_guid(payload: IfcMutation) -> str:
    """Return the entity GUID targeted by *payload*."""
    if isinstance(payload, SetPropertyValue):
        return payload.entity_guid
    return payload.guid  # AddEntity | DeleteEntity | ModifyAttribute


def _get_op_attribute(payload: IfcMutation) -> tuple[str, ...] | None:
    """Return a composite key for the attribute targeted by *payload*, or ``None``.

    Returns ``None`` for ``AddEntity`` and ``DeleteEntity`` — those ops have
    no attribute granularity in the conflict matrix.
    """
    if isinstance(payload, ModifyAttribute):
        return (payload.attribute,)
    if isinstance(payload, SetPropertyValue):
        return (payload.pset_name, payload.property_name)
    return None


def _get_op_new_value(payload: IfcMutation) -> IfcValue | None:
    """Return the new value produced by *payload*, or ``None`` for non-value ops."""
    if isinstance(payload, (ModifyAttribute, SetPropertyValue)):
        return payload.new_value
    return None


def _attr_str(attr: tuple[str, ...] | None) -> str | None:
    """Render *attr* as a dot-joined string (``"Name"`` or ``"Pset.prop"``), or ``None``."""
    return ".".join(attr) if attr is not None else None


@dataclass
class _PairOutcome:
    """Result of checking a single concurrent (A, B) pair for conflicts.

    Args:
        drop_incoming: B should not be appended to the log.
        stop: Stop checking further concurrent ops (break out of the loop).
        resolved_pos: ``op_log`` index to mark ``resolved=True``, or ``None``.
        audit: Audit entry to record, or ``None`` when there is no conflict.
    """

    drop_incoming: bool = False
    stop: bool = False
    resolved_pos: int | None = None
    audit: AuditEntry | None = None


def _find_concurrent_ops(
    op_log: list[StoredOp],
    parent_op_id: UUID | None,
) -> list[StoredOp]:
    """Return all ops in *op_log* that are concurrent with an incoming op.

    An op is concurrent when its ``server_position`` is strictly after the
    position of *parent_op_id* in the log. If *parent_op_id* is ``None`` or
    not found (stale / post-restart), all log entries are treated as concurrent.
    """
    if parent_op_id is None:
        return list(op_log)
    for i, stored in enumerate(op_log):
        if stored.envelope.op_id == parent_op_id:
            return list(op_log[i + 1 :])
    return list(op_log)  # not found — treat all as concurrent


def _check_concurrent_pair(
    stored_a: StoredOp,
    incoming: StoredOp,
    now: float,
) -> _PairOutcome | None:
    """Return how to resolve the conflict between concurrent ops A and B.

    Returns ``None`` when there is no conflict (different GUIDs, or same GUID
    but different attributes).  Implements the full conflict matrix from
    DESIGN.md §5.

    Args:
        stored_a: Concurrent op already in the log (op A).
        incoming: Candidate op not yet in the log (op B).
        now: Unix timestamp to stamp any audit entry produced.
    """
    a_payload = stored_a.envelope.payload
    b_payload = incoming.envelope.payload

    if _get_op_guid(a_payload) != _get_op_guid(b_payload):
        return None  # different entity — no conflict

    b_guid = _get_op_guid(b_payload)
    a_attr = _get_op_attribute(a_payload)
    b_attr = _get_op_attribute(b_payload)
    a_is_delete = isinstance(a_payload, DeleteEntity)
    b_is_delete = isinstance(b_payload, DeleteEntity)

    # Both deletes on same GUID — idempotent, drop B silently.
    if a_is_delete and b_is_delete:
        return _PairOutcome(drop_incoming=True, stop=True)

    # A is delete, B is modify — delete wins, B dropped, audit recorded.
    if a_is_delete:
        return _PairOutcome(
            drop_incoming=True,
            stop=True,
            audit=AuditEntry(
                winning_op_id=stored_a.envelope.op_id,
                losing_op_id=incoming.envelope.op_id,
                guid=b_guid,
                attribute=_attr_str(b_attr),
                winning_value=None,
                losing_value=_get_op_new_value(b_payload),
                resolved_at=now,
            ),
        )

    # B is delete, A is modify — delete wins, A resolved.
    if b_is_delete:
        return _PairOutcome(
            resolved_pos=stored_a.server_position,
            audit=AuditEntry(
                winning_op_id=incoming.envelope.op_id,
                losing_op_id=stored_a.envelope.op_id,
                guid=b_guid,
                attribute=_attr_str(a_attr),
                winning_value=None,
                losing_value=_get_op_new_value(a_payload),
                resolved_at=now,
            ),
        )

    # Both AddEntity on same GUID — GUID collision, LWW (B wins).
    if isinstance(a_payload, AddEntity) and isinstance(b_payload, AddEntity):
        return _PairOutcome(
            resolved_pos=stored_a.server_position,
            audit=AuditEntry(
                winning_op_id=incoming.envelope.op_id,
                losing_op_id=stored_a.envelope.op_id,
                guid=b_guid,
                attribute=None,
                winning_value=None,
                losing_value=None,
                resolved_at=now,
            ),
        )

    # Both modify/set — check attribute granularity.
    if a_attr is None or b_attr is None or a_attr != b_attr:
        return None  # different or absent attributes — no conflict

    # Same GUID, same attribute — LWW: B (later-received) wins.
    return _PairOutcome(
        resolved_pos=stored_a.server_position,
        audit=AuditEntry(
            winning_op_id=incoming.envelope.op_id,
            losing_op_id=stored_a.envelope.op_id,
            guid=b_guid,
            attribute=_attr_str(b_attr),
            winning_value=_get_op_new_value(b_payload),
            losing_value=_get_op_new_value(a_payload),
            resolved_at=now,
        ),
    )


# ---------------------------------------------------------------------------
# ConflictResult — return type of FileState.detect_and_resolve
# ---------------------------------------------------------------------------


@dataclass
class ConflictResult:
    """Result of conflict detection for a single incoming op.

    Args:
        should_append: Whether the incoming op should be appended to the log.
            ``False`` for idempotent double-deletes and delete-wins-over-modify.
        audit_entries: Audit records to append (may be non-empty even when
            ``should_append`` is ``False``, e.g. delete-wins-over-modify).
        resolved_op_positions: Indices in ``op_log`` to mark ``resolved=True``
            before appending the incoming op.
    """

    should_append: bool
    audit_entries: list[AuditEntry]
    resolved_op_positions: list[int]


# ---------------------------------------------------------------------------
# StoredOp and FileState
# ---------------------------------------------------------------------------


@dataclass
class StoredOp:
    """An op that has been appended to the server log.

    Args:
        server_position: 0-based index assigned in receive order (not
            client clock order — clock skew is irrelevant).
        envelope: The full ``IfcOpEnvelope`` as submitted by the client.
        resolved: ``True`` when LWW conflict resolution marks this op as
            overwritten by a later-received concurrent op.
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
        audit_log: Conflict-resolution records populated by step 5.
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

    def detect_and_resolve(self, incoming: StoredOp) -> ConflictResult:
        """Check *incoming* against the log and return a conflict resolution.

        Identifies all ops concurrent with *incoming* (those with
        ``server_position`` strictly after *incoming*'s ``parent_op_id``
        position), then applies the conflict matrix from DESIGN.md §5 to
        each pair via ``_check_concurrent_pair``.

        Args:
            incoming: The candidate ``StoredOp`` (not yet in the log).

        Returns:
            A ``ConflictResult`` describing what to do with *incoming*.
        """
        should_append = True
        audit_entries: list[AuditEntry] = []
        resolved_positions: list[int] = []
        now = time.time()

        concurrent = _find_concurrent_ops(self.op_log, incoming.envelope.parent_op_id)
        for stored_a in concurrent:
            if stored_a.resolved:
                continue
            outcome = _check_concurrent_pair(stored_a, incoming, now)
            if outcome is None:
                continue
            if outcome.drop_incoming:
                should_append = False
            if outcome.resolved_pos is not None:
                resolved_positions.append(outcome.resolved_pos)
            if outcome.audit is not None:
                audit_entries.append(outcome.audit)
            if outcome.stop:
                break

        return ConflictResult(
            should_append=should_append,
            audit_entries=audit_entries,
            resolved_op_positions=resolved_positions,
        )
