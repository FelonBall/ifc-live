"""Pydantic models for all WebSocket messages exchanged by the sync server.

Client-to-server messages are parsed via ``ClientMessage`` (a discriminated
union keyed on ``type``). Server-to-client messages are serialised via the
``ServerMessage`` variants. Response models for HTTP debug endpoints are also
defined here.

See ``docs/PROTOCOL.md`` for the full wire format specification.
"""

from __future__ import annotations

from typing import Annotated, Literal, TypeAlias
from uuid import UUID

from pydantic import BaseModel, Field, TypeAdapter

from ifc_ops import IfcOpEnvelope, IfcValue

# ---------------------------------------------------------------------------
# Client → Server
# ---------------------------------------------------------------------------


class HelloMessage(BaseModel):
    """First message a client sends after connecting.

    ``last_known_op_id`` is the ``op_id`` of the last op the client has
    already applied locally, or ``None`` if the client has no prior state.
    The server uses this to decide which ops to include in the ``sync``
    response.
    """

    type: Literal["hello"] = "hello"
    client_id: str
    last_known_op_id: str | None = None


class ClientOpMessage(BaseModel):
    """A mutation the client wants appended to the server log."""

    type: Literal["op"] = "op"
    envelope: IfcOpEnvelope


ClientMessage: TypeAlias = Annotated[
    HelloMessage | ClientOpMessage,
    Field(discriminator="type"),
]

_client_message_adapter: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)


def parse_client_message(raw: str) -> ClientMessage:
    """Parse a raw JSON string into a ``ClientMessage``.

    Args:
        raw: JSON-encoded message from the client.

    Returns:
        A ``HelloMessage`` or ``ClientOpMessage`` instance.

    Raises:
        pydantic.ValidationError: if ``raw`` is malformed JSON or does not
            match any known message type.
    """
    return _client_message_adapter.validate_json(raw)


# ---------------------------------------------------------------------------
# Server → Client
# ---------------------------------------------------------------------------


class SyncMessage(BaseModel):
    """Sent after ``hello`` to bootstrap the client's local op log.

    ``ops`` contains every ``IfcOpEnvelope`` since ``last_known_op_id``
    (exclusive), in server-position order. ``head_op_id`` is the ``op_id``
    at the top of the log after the sync — the client stores this as its new
    ``last_known_op_id`` for future reconnects.
    """

    type: Literal["sync"] = "sync"
    ops: list[IfcOpEnvelope]
    head_op_id: str | None = None


class ReadyMessage(BaseModel):
    """Sent after ``sync`` to signal the client is in steady state."""

    type: Literal["ready"] = "ready"


class OpAckMessage(BaseModel):
    """Acknowledges that the server has appended the client's op to the log.

    ``server_position`` is the 0-based index assigned to this op in the log.
    """

    type: Literal["op_ack"] = "op_ack"
    op_id: str
    server_position: int


class ServerOpMessage(BaseModel):
    """Broadcast of a peer's op to all other connected clients.

    ``resolved`` is ``True`` when LWW conflict resolution modified the op's
    values — the client should expect the envelope's attribute values to
    differ from the original submission (step 5).
    """

    type: Literal["op"] = "op"
    envelope: IfcOpEnvelope
    server_position: int
    resolved: bool = False


class ConflictResolvedMessage(BaseModel):
    """Broadcast when LWW resolves a conflict between concurrent ops.

    Clients use this to surface a notification to the user. Sent to ALL
    connected clients (including the originator of the winning op).
    """

    type: Literal["conflict_resolved"] = "conflict_resolved"
    winning_op_id: str
    losing_op_id: str
    guid: str
    attribute: str | None = None


ServerMessage: TypeAlias = Annotated[
    SyncMessage | ReadyMessage | OpAckMessage | ServerOpMessage | ConflictResolvedMessage,
    Field(discriminator="type"),
]

# ---------------------------------------------------------------------------
# HTTP response models (debug endpoints)
# ---------------------------------------------------------------------------


class FileInfoResponse(BaseModel):
    """Summary of a tracked file for ``GET /files``."""

    file_id: str
    client_count: int


class StoredOpResponse(BaseModel):
    """A single stored-op entry for ``GET /files/{file_id}/log``."""

    server_position: int
    envelope: IfcOpEnvelope
    resolved: bool


class AuditEntry(BaseModel):
    """Conflict-resolution audit record for ``GET /files/{file_id}/audit``.

    Populated when LWW conflict resolution overwrites a concurrent op.

    Args:
        winning_op_id: The op that was kept (later-received, or delete in
            a delete-vs-modify conflict).
        losing_op_id: The op that was overwritten or dropped.
        guid: The entity GUID both ops targeted.
        attribute: Attribute name (or ``"pset.prop"`` for
            ``SetPropertyValue``), or ``None`` for entity-level conflicts.
        winning_value: The winning op's new value (``None`` for deletes).
        losing_value: The losing op's new value, preserved for audit.
        resolved_at: Server unix timestamp when the conflict was resolved.
    """

    winning_op_id: UUID
    losing_op_id: UUID
    guid: str
    attribute: str | None = None
    winning_value: IfcValue | None = None
    losing_value: IfcValue | None = None
    resolved_at: float
