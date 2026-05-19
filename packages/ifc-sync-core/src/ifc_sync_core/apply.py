"""Op application: mutate an ifcopenshell.file given an IfcOpEnvelope."""

from __future__ import annotations

from typing import Any

import ifcopenshell.guid  # type: ignore[import-untyped]

from ifc_ops import (
    AddEntity,
    DeleteEntity,
    IfcBool,
    IfcEnum,
    IfcFloat,
    IfcInt,
    IfcNull,
    IfcOpEnvelope,
    IfcString,
    IfcValue,
    ModifyAttribute,
    SetPropertyValue,
)
from ifc_sync_core.serialize import deserialize_value, lookup_entity, register_non_root


def apply_op(model: Any, op: IfcOpEnvelope) -> None:
    """Apply a single ``IfcOpEnvelope`` to an ``ifcopenshell.file``, mutating it in place.

    All four mutation types are supported.  The function dispatches on the
    concrete type of ``op.payload`` and delegates to a private handler.
    """
    payload = op.payload
    if isinstance(payload, AddEntity):
        _apply_add_entity(model, payload)
    elif isinstance(payload, DeleteEntity):
        _apply_delete_entity(model, payload)
    elif isinstance(payload, ModifyAttribute):
        _apply_modify_attribute(model, payload)
    else:
        _apply_set_property_value(model, payload)


def _apply_add_entity(model: Any, op: AddEntity) -> None:
    entity = model.create_entity(op.ifc_type)
    try:
        entity.GlobalId = op.guid
    except Exception:
        # Geometric support entities (IfcLocalPlacement, IfcAxis2Placement3D, …)
        # have no GlobalId in IFC4.  Register the synthetic GUID so IfcRef values
        # pointing at this entity can be resolved later.
        register_non_root(model, op.guid, entity)
    for attr_name, ifc_val in op.attributes.items():
        if attr_name == "GlobalId":
            continue  # already set above
        setattr(entity, attr_name, deserialize_value(ifc_val, model))


def _apply_delete_entity(model: Any, op: DeleteEntity) -> None:
    entity = lookup_entity(model, op.guid)
    model.remove(entity)


def _apply_modify_attribute(model: Any, op: ModifyAttribute) -> None:
    entity = lookup_entity(model, op.guid)
    setattr(entity, op.attribute, deserialize_value(op.new_value, model))


def _apply_set_property_value(model: Any, op: SetPropertyValue) -> None:
    entity = model.by_guid(op.entity_guid)

    # Walk the inverse relationship to find an existing pset by name.
    pset: Any = None
    for rel in entity.IsDefinedBy or ():
        if not rel.is_a("IfcRelDefinesByProperties"):
            continue
        pdef = rel.RelatingPropertyDefinition
        if pdef.is_a("IfcPropertySet") and pdef.Name == op.pset_name:
            pset = pdef
            break

    if pset is None:
        pset = model.create_entity(
            "IfcPropertySet",
            GlobalId=ifcopenshell.guid.new(),
            Name=op.pset_name,
            HasProperties=[],
        )
        model.create_entity(
            "IfcRelDefinesByProperties",
            GlobalId=ifcopenshell.guid.new(),
            RelatedObjects=[entity],
            RelatingPropertyDefinition=pset,
        )

    nominal = _to_nominal_value(model, op.new_value)
    existing: list[Any] = list(pset.HasProperties or ())
    for prop in existing:
        if prop.Name == op.property_name:
            prop.NominalValue = nominal
            return
    new_prop = model.create_entity(
        "IfcPropertySingleValue",
        Name=op.property_name,
        NominalValue=nominal,
    )
    pset.HasProperties = [*existing, new_prop]


def _to_nominal_value(model: Any, ifc_val: IfcValue) -> Any:
    """Wrap an ``IfcValue`` in the IfcOpenShell entity type required for
    ``IfcPropertySingleValue.NominalValue``.

    ``NominalValue`` is an IFC SELECT type; IfcOpenShell requires a wrapped
    entity instance (e.g. ``IfcLabel``, ``IfcReal``) rather than a plain Python
    value.  ``IfcRef`` and ``IfcList`` are not valid NominalValue types in v1
    and are silently mapped to ``None`` (unset).
    """
    if isinstance(ifc_val, IfcNull):
        return None
    if isinstance(ifc_val, (IfcString, IfcEnum)):
        return model.create_entity("IfcLabel", ifc_val.value)
    if isinstance(ifc_val, IfcFloat):
        return model.create_entity("IfcReal", ifc_val.value)
    if isinstance(ifc_val, IfcInt):
        return model.create_entity("IfcInteger", ifc_val.value)
    if isinstance(ifc_val, IfcBool):
        return model.create_entity("IfcBoolean", ifc_val.value)
    return None  # IfcRef / IfcList — not supported as NominalValue in v1


__all__ = ["apply_op"]
