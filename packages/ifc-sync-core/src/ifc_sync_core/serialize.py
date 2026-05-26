"""Serialize and deserialize IfcOpenShell values to/from the IfcValue wire type.

Also maintains the per-model non-root entity registry — see DESIGN.md section 3
"Non-root entity identity" for why this exists.
"""

from __future__ import annotations

import uuid
from typing import Any
from weakref import WeakKeyDictionary

import ifcopenshell
import ifcopenshell.entity_instance

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
# Non-root entity registry (see DESIGN.md §3 "Non-root entity identity")
# ---------------------------------------------------------------------------

# Maps STEP entity ID (int) → synthetic GUID (str), keyed per model.
_entity_to_guid: WeakKeyDictionary[ifcopenshell.file, dict[int, str]] = WeakKeyDictionary()
# Reverse: synthetic GUID → STEP entity ID, keyed per model.
_guid_to_entity_id: WeakKeyDictionary[ifcopenshell.file, dict[str, int]] = WeakKeyDictionary()


def register_non_root(
    model: ifcopenshell.file,
    entity: ifcopenshell.entity_instance,
    synthetic_guid: str | None = None,
) -> str:
    """Register a non-IfcRoot entity with a synthetic GUID.

    Returns the GUID used (auto-generated if *synthetic_guid* is ``None``).
    """
    if synthetic_guid is None:
        synthetic_guid = str(uuid.uuid4())

    if model not in _entity_to_guid:
        _entity_to_guid[model] = {}
        _guid_to_entity_id[model] = {}

    entity_id = entity.id()
    _entity_to_guid[model][entity_id] = synthetic_guid
    _guid_to_entity_id[model][synthetic_guid] = entity_id
    return synthetic_guid


def _synthetic_guid_for(
    model: ifcopenshell.file,
    entity: ifcopenshell.entity_instance,
) -> str | None:
    """Return the synthetic GUID for *entity* in *model*, or ``None``."""
    mapping = _entity_to_guid.get(model)
    if mapping is None:
        return None
    return mapping.get(entity.id())


def _entity_by_synthetic_guid(
    model: ifcopenshell.file,
    guid: str,
) -> ifcopenshell.entity_instance | None:
    """Return the entity registered under *guid* in *model*, or ``None``."""
    mapping = _guid_to_entity_id.get(model)
    if mapping is None:
        return None
    entity_id = mapping.get(guid)
    if entity_id is None:
        return None
    return model.by_id(entity_id)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def serialize_value(
    model: ifcopenshell.file,
    value: Any,
) -> IfcValue:
    """Serialize an IfcOpenShell attribute value to an ``IfcValue``.

    All Python ``str`` values emit as ``IfcString`` — see DESIGN.md §3
    "Enum/string handling" for the rationale.

    Raises ``ValueError`` for entity instances that have no ``GlobalId`` and
    are not in the non-root registry. Call ``register_non_root`` first.
    """
    if value is None:
        return IfcNull()
    # bool before int — Python bool is a subclass of int
    if isinstance(value, bool):
        return IfcBool(value=value)
    if isinstance(value, int):
        return IfcInt(value=value)
    if isinstance(value, float):
        return IfcFloat(value=value)
    if isinstance(value, str):
        return IfcString(value=value)
    if isinstance(value, ifcopenshell.entity_instance):
        try:
            wrapped = value.wrappedValue  # type: ignore[attr-defined]
            return serialize_value(model, wrapped)
        except AttributeError:
            pass
        try:
            guid: str = value.GlobalId  # type: ignore[attr-defined]
            return IfcRef(guid=guid)
        except AttributeError:
            pass
        synthetic = _synthetic_guid_for(model, value)
        if synthetic is None:
            raise ValueError(
                f"Entity {value!r} has no GlobalId and is not in the non-root "
                "registry. Call register_non_root() before serializing."
            )
        return IfcRef(guid=synthetic)
    if isinstance(value, (list, tuple)):
        return IfcList(values=[serialize_value(model, v) for v in value])  # type: ignore[misc]
    raise TypeError(
        f"Cannot serialize value of type {type(value).__name__!r} to IfcValue. "
        "Expected: None, bool, int, float, str, entity_instance, list, or tuple."
    )


def deserialize_value(
    model: ifcopenshell.file,
    value: IfcValue,
) -> Any:
    """Deserialize an ``IfcValue`` to an IfcOpenShell-compatible Python value.

    ``IfcRef`` resolves against real ``GlobalId`` first, then the synthetic
    registry. Raises ``ValueError`` if the GUID is not found in either.
    ``IfcEnum`` is treated identically to ``IfcString`` — see DESIGN.md §3.
    """
    if isinstance(value, IfcString):
        return value.value
    if isinstance(value, IfcInt):
        return value.value
    if isinstance(value, IfcFloat):
        return value.value
    if isinstance(value, IfcBool):
        return value.value
    if isinstance(value, IfcEnum):
        # IfcOpenShell accepts plain strings for enum-typed attributes
        return value.value
    if isinstance(value, IfcRef):
        try:
            return model.by_guid(value.guid)
        except RuntimeError:
            pass
        entity = _entity_by_synthetic_guid(model, value.guid)
        if entity is None:
            raise ValueError(
                f"No entity found for GUID {value.guid!r} (checked both "
                "GlobalId index and non-root registry)."
            )
        return entity
    if isinstance(value, IfcList):
        return [deserialize_value(model, v) for v in value.values]
    # IfcNull — only remaining variant in the closed IfcValue union
    return None


def serialize_entity(
    model: ifcopenshell.file,
    entity: ifcopenshell.entity_instance,
) -> dict[str, Any]:
    """Serialize an entity's attributes to raw Python primitives.

    Intended for ``DeleteEntity.previous_snapshot`` — audit use only, not a
    reversible serialization format.
    """
    info: dict[str, Any] = entity.get_info()  # type: ignore[assignment]
    result: dict[str, Any] = {}
    for key, val in info.items():
        if key in ("id", "type"):
            continue
        if isinstance(val, ifcopenshell.entity_instance):
            result[key] = {"id": val.id(), "type": val.is_a()}
        elif isinstance(val, (list, tuple)):
            result[key] = [
                {"id": v.id(), "type": v.is_a()}  # type: ignore[union-attr]
                if isinstance(v, ifcopenshell.entity_instance)
                else v
                for v in val
            ]
        else:
            result[key] = val
    return result


def get_synthetic_guid(
    model: ifcopenshell.file,
    entity: ifcopenshell.entity_instance,
) -> str | None:
    """Return the synthetic GUID registered for *entity* in *model*, or ``None``.

    Returns ``None`` if the entity is not in the non-root registry (i.e. it was
    created directly on the raw model without going through
    ``SyncedIfcModel.create_entity``).
    """
    return _synthetic_guid_for(model, entity)


__all__ = [
    "deserialize_value",
    "get_synthetic_guid",
    "register_non_root",
    "serialize_entity",
    "serialize_value",
]
