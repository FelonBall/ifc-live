"""Serialization helpers: convert between IfcOpenShell values and ifc-ops wire types."""

from __future__ import annotations

import weakref
from typing import Any

from ifc_ops import (
    IfcBool,
    IfcEnum,
    IfcFloat,
    IfcInt,
    IfcList,
    IfcNull,
    IfcRef,
    IfcString,
    IfcValue,
)

# ---------------------------------------------------------------------------
# Non-root entity registry
#
# IfcRoot subclasses (IfcWall, IfcPropertySet, …) have a native GlobalId that
# IfcOpenShell indexes via model.by_guid().  Geometric support entities
# (IfcLocalPlacement, IfcAxis2Placement3D, …) do not.  When an AddEntity op
# targets a non-root type, apply.py assigns a synthetic GUID and registers it
# here so that later IfcRef values pointing at that entity can be resolved.
#
# Both dicts are keyed weakly on the model object so they are automatically
# cleaned up when the model is garbage-collected.
# ---------------------------------------------------------------------------

_entity_to_guid: weakref.WeakKeyDictionary[Any, dict[int, str]] = weakref.WeakKeyDictionary()
_guid_to_step_id: weakref.WeakKeyDictionary[Any, dict[str, int]] = weakref.WeakKeyDictionary()


def register_non_root(model: Any, guid: str, entity: Any) -> None:
    """Map a synthetic GUID to a non-root entity (one without a native GlobalId)."""
    step_id: int = entity.id()
    _entity_to_guid.setdefault(model, {})[step_id] = guid
    _guid_to_step_id.setdefault(model, {})[guid] = step_id


def lookup_entity(model: Any, guid: str) -> Any:
    """Return the IfcOpenShell entity for *guid*.

    Checks the non-root registry first (for synthetic GUIDs assigned to
    geometric entities), then falls back to ``model.by_guid()`` for IfcRoot
    subclasses.  Raises ``RuntimeError`` (from IfcOpenShell) if the GUID is
    not found in either place.
    """
    inv = _guid_to_step_id.get(model, {})
    if guid in inv:
        return model.by_id(inv[guid])
    return model.by_guid(guid)


# ---------------------------------------------------------------------------
# Public serialization API
# ---------------------------------------------------------------------------


def serialize_value(val: Any) -> IfcValue:
    """Convert a raw IfcOpenShell attribute value to the ifc-ops wire type.

    Dispatch is pure Python-type-based — no IFC schema introspection.  As a
    consequence, all string values (including IFC enumeration literals such as
    ``"SOLIDWALL"``) are returned as ``IfcString``, not ``IfcEnum``.  ``IfcEnum``
    is only used in ops built from scratch by callers that know the attribute
    semantics; round-trip tests should therefore use non-enumeration attributes.
    """
    if val is None:
        return IfcNull()
    # bool is a subtype of int in Python — check first to avoid misclassification
    if isinstance(val, bool):
        return IfcBool(value=val)
    if isinstance(val, int):
        return IfcInt(value=val)
    if isinstance(val, float):
        return IfcFloat(value=val)
    if isinstance(val, str):
        return IfcString(value=val)
    if isinstance(val, (list, tuple)):
        return IfcList(values=[serialize_value(v) for v in val])
    # IfcOpenShell entity_instance — two sub-cases:
    if hasattr(val, "wrappedValue"):
        # Wrapped simple type: IfcLabel → str, IfcReal → float, IfcBoolean → bool, …
        return serialize_value(val.wrappedValue)
    if hasattr(val, "GlobalId") and val.GlobalId is not None:
        return IfcRef(guid=str(val.GlobalId))
    # Non-root entity without a native GlobalId.  Return IfcNull as a safe
    # fallback; callers that need IfcRef for these entities should ensure the
    # entity was registered via register_non_root before serializing.
    return IfcNull()


def deserialize_value(ifc_val: IfcValue, model: Any) -> Any:
    """Convert an ifc-ops wire value to the Python/IfcOpenShell value expected
    when setting an entity attribute.

    *model* is required so that ``IfcRef`` values can be resolved to the live
    entity object via ``lookup_entity``.
    """
    if isinstance(ifc_val, IfcNull):
        return None
    if isinstance(ifc_val, IfcString):
        return ifc_val.value
    if isinstance(ifc_val, IfcInt):
        return ifc_val.value
    if isinstance(ifc_val, IfcFloat):
        return ifc_val.value
    if isinstance(ifc_val, IfcBool):
        return ifc_val.value
    if isinstance(ifc_val, IfcEnum):
        return ifc_val.value  # IfcOpenShell accepts plain strings for enum attrs
    if isinstance(ifc_val, IfcRef):
        return lookup_entity(model, ifc_val.guid)
    return [deserialize_value(v, model) for v in ifc_val.values]


def _raw_to_json(val: Any) -> Any:
    """Recursively convert a raw IfcOpenShell value to a JSON-safe primitive."""
    if val is None:
        return None
    if isinstance(val, (bool, int, float, str)):
        return val
    if isinstance(val, (list, tuple)):
        return [_raw_to_json(v) for v in val]
    if hasattr(val, "wrappedValue"):
        return val.wrappedValue
    if hasattr(val, "GlobalId") and val.GlobalId is not None:
        return str(val.GlobalId)
    if hasattr(val, "id"):
        return f"#{val.id()}"  # STEP entity reference notation
    return str(val)


def serialize_entity(entity: Any) -> dict[str, Any]:
    """Serialize all attributes of an IfcOpenShell entity to a JSON-safe dict.

    Used to populate ``DeleteEntity.previous_snapshot``.  Values are raw Python
    primitives — not ``IfcValue``-typed.  See ``docs/DESIGN.md`` section 3 and
    Appendix B: snapshots feed the audit log only and are not designed for entity
    reconstruction.
    """
    info: dict[str, Any] = entity.get_info()
    return {k: _raw_to_json(v) for k, v in info.items() if k != "id"}


__all__ = [
    "deserialize_value",
    "lookup_entity",
    "serialize_entity",
    "serialize_value",
]
