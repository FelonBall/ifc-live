"""IfcOp data model — Pydantic schemas for all IFC mutations.

This package is the foundation of ifc-live. It defines the closed set of
operations that can mutate an IFC model, along with the envelope that wraps
each op as it flows through the system.

The package has no dependencies on IfcOpenShell or any other IFC library —
it is pure data types so it can be imported anywhere (client, server, test
fixtures) without pulling in heavy native dependencies.

See ``docs/DESIGN.md`` section 3 for the full op model specification.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, TypeAlias
from uuid import UUID

from pydantic import BaseModel, Field

__version__ = "0.1.0"

SCHEMA_VERSION: Literal["1"] = "1"

# ---------------------------------------------------------------------------
# IfcValue — tagged union of every scalar and aggregate value IFC supports
# ---------------------------------------------------------------------------


class IfcString(BaseModel):
    """A plain string IFC attribute value."""

    kind: Literal["string"] = "string"
    value: str


class IfcInt(BaseModel):
    """An integer IFC attribute value."""

    kind: Literal["int"] = "int"
    value: int


class IfcFloat(BaseModel):
    """A floating-point IFC attribute value."""

    kind: Literal["float"] = "float"
    value: float


class IfcBool(BaseModel):
    """A boolean IFC attribute value."""

    kind: Literal["bool"] = "bool"
    value: bool


class IfcEnum(BaseModel):
    """An IFC enumeration value, stored as its string token (e.g. ``"ELEMENT"``)."""

    kind: Literal["enum"] = "enum"
    value: str


class IfcRef(BaseModel):
    """A reference to another IFC entity, identified by its IFC ``GlobalId``."""

    kind: Literal["ref"] = "ref"
    guid: str


class IfcList(BaseModel):
    """An ordered aggregate of ``IfcValue`` items (e.g. a coordinate list)."""

    kind: Literal["list"] = "list"
    values: list[IfcValue]


class IfcNull(BaseModel):
    """A null or explicitly unset IFC attribute value."""

    kind: Literal["null"] = "null"


IfcValue: TypeAlias = Annotated[
    IfcString | IfcInt | IfcFloat | IfcBool | IfcEnum | IfcRef | IfcList | IfcNull,
    Field(discriminator="kind"),
]

# IfcList references IfcValue, which was not yet defined when the class was
# created. Rebuild now that IfcValue exists in the module namespace.
IfcList.model_rebuild()

# ---------------------------------------------------------------------------
# IfcMutation — the closed set of operations that can mutate an IFC model
# ---------------------------------------------------------------------------


class AddEntity(BaseModel):
    """Create a new IFC entity with the given GUID, type, and initial attributes.

    ``attributes`` maps IFC attribute names to their initial values. Complex
    geometry is expressed as ``IfcRef`` values pointing to previously emitted
    ``AddEntity`` ops for placement and representation entities.
    """

    kind: Literal["add_entity"] = "add_entity"
    guid: str
    ifc_type: str
    attributes: dict[str, IfcValue]


class DeleteEntity(BaseModel):
    """Remove an IFC entity from the model.

    ``previous_snapshot`` records the full attribute state of the entity at
    deletion time so the audit log can reconstruct prior states and support
    future undo.
    """

    kind: Literal["delete_entity"] = "delete_entity"
    guid: str
    previous_snapshot: dict[str, Any]


class ModifyAttribute(BaseModel):
    """Change a single direct attribute on an existing IFC entity.

    Both ``previous_value`` and ``new_value`` are stored so conflict detection
    can compare concurrent ops and the audit log can record what was overwritten.
    """

    kind: Literal["modify_attribute"] = "modify_attribute"
    guid: str
    attribute: str
    previous_value: IfcValue
    new_value: IfcValue


class SetPropertyValue(BaseModel):
    """Set a single property in a named property set attached to an IFC entity.

    ``previous_value`` is ``None`` when the property did not exist before this
    op (i.e. first write). The server uses this to detect concurrent writes to
    the same property.
    """

    kind: Literal["set_property_value"] = "set_property_value"
    entity_guid: str
    pset_name: str
    property_name: str
    previous_value: IfcValue | None
    new_value: IfcValue


IfcMutation: TypeAlias = Annotated[
    AddEntity | DeleteEntity | ModifyAttribute | SetPropertyValue,
    Field(discriminator="kind"),
]

# ---------------------------------------------------------------------------
# IfcOpEnvelope — wire format wrapper for every mutation
# ---------------------------------------------------------------------------


class IfcOpEnvelope(BaseModel):
    """Top-level wire format for every IFC mutation streamed over WebSocket.

    Every op that flows through the system is wrapped in this envelope so the
    server can route, log, and conflict-check it without inspecting the payload.

    ``op_id`` should be a UUIDv7 (time-ordered) generated by the originating
    client. ``parent_op_id`` is the ``op_id`` of the HEAD op the client
    believed was current when this op was created; ``None`` means the client
    had no prior ops (freshly connected).
    """

    schema_version: Literal["1"] = "1"
    op_id: UUID
    parent_op_id: UUID | None = None
    file_id: str
    author: str
    timestamp: float
    payload: IfcMutation


__all__ = [
    "SCHEMA_VERSION",
    "AddEntity",
    "DeleteEntity",
    "IfcBool",
    "IfcEnum",
    "IfcFloat",
    "IfcInt",
    "IfcList",
    "IfcMutation",
    "IfcNull",
    "IfcOpEnvelope",
    "IfcRef",
    "IfcString",
    "IfcValue",
    "ModifyAttribute",
    "SetPropertyValue",
]
