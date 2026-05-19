"""Apply an IfcMutation op to an ifcopenshell.file in-place.

One-way: this module mutates the model; it does not emit new ops. Callers
that need to suppress op emission (e.g. the Bonsai addon receiving a remote
op) should use the suppress_emission context manager from SyncedIfcModel.
"""

from __future__ import annotations

import ifcopenshell
import ifcopenshell.entity_instance
import ifcopenshell.guid

from ifc_ops import (
    AddEntity,
    DeleteEntity,
    IfcBool,
    IfcFloat,
    IfcInt,
    IfcList,
    IfcMutation,
    IfcRef,
    IfcString,
    IfcValue,
    ModifyAttribute,
    SetPropertyValue,
)
from ifc_sync_core.serialize import deserialize_value, register_non_root

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def apply_op(model: ifcopenshell.file, op: IfcMutation) -> None:
    """Apply *op* to *model* in-place."""
    if isinstance(op, AddEntity):
        _apply_add_entity(model, op)
    elif isinstance(op, DeleteEntity):
        _apply_delete_entity(model, op)
    elif isinstance(op, ModifyAttribute):
        _apply_modify_attribute(model, op)
    else:
        _apply_set_property_value(model, op)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _apply_add_entity(model: ifcopenshell.file, op: AddEntity) -> None:
    entity = model.create_entity(op.ifc_type)

    # Explicit IfcRoot check — avoids a bare except that would silently swallow
    # AttributeError for non-root types. See DESIGN.md §3 "Non-root entity identity".
    if entity.is_a("IfcRoot"):
        entity.GlobalId = op.guid  # type: ignore[attr-defined]
    else:
        register_non_root(model, entity, op.guid)

    for attr_name, attr_value in op.attributes.items():
        if attr_name == "GlobalId":
            continue  # already handled above
        setattr(entity, attr_name, deserialize_value(model, attr_value))


def _apply_delete_entity(model: ifcopenshell.file, op: DeleteEntity) -> None:
    entity = model.by_guid(op.guid)
    model.remove(entity)


def _apply_modify_attribute(model: ifcopenshell.file, op: ModifyAttribute) -> None:
    entity = model.by_guid(op.guid)
    setattr(entity, op.attribute, deserialize_value(model, op.new_value))


def _apply_set_property_value(
    model: ifcopenshell.file,
    op: SetPropertyValue,
) -> None:
    entity = model.by_guid(op.entity_guid)
    pset = _find_or_create_pset(model, entity, op.pset_name)
    nominal = _to_nominal_value(model, op.new_value)
    _set_or_create_property(model, pset, op.property_name, nominal)


def _find_or_create_pset(
    model: ifcopenshell.file,
    entity: ifcopenshell.entity_instance,
    pset_name: str,
) -> ifcopenshell.entity_instance:
    """Return the named IfcPropertySet for *entity*, creating it if absent."""
    for rel in model.get_inverse(entity):
        if rel.is_a("IfcRelDefinesByProperties"):
            pdef = rel.RelatingPropertyDefinition
            if pdef.is_a("IfcPropertySet") and pdef.Name == pset_name:
                return pdef

    pset = model.create_entity("IfcPropertySet", Name=pset_name, HasProperties=[])
    model.create_entity(
        "IfcRelDefinesByProperties",
        GlobalId=ifcopenshell.guid.new(),
        RelatedObjects=[entity],
        RelatingPropertyDefinition=pset,
    )
    return pset


def _set_or_create_property(
    model: ifcopenshell.file,
    pset: ifcopenshell.entity_instance,
    property_name: str,
    nominal_value: ifcopenshell.entity_instance,
) -> None:
    """Set the NominalValue of an IfcPropertySingleValue in *pset*, creating it if absent."""
    existing = list(pset.HasProperties or [])
    for prop in existing:
        if prop.is_a("IfcPropertySingleValue") and prop.Name == property_name:
            prop.NominalValue = nominal_value
            return

    new_prop = model.create_entity(
        "IfcPropertySingleValue",
        Name=property_name,
        NominalValue=nominal_value,
    )
    pset.HasProperties = [*existing, new_prop]


def _to_nominal_value(
    model: ifcopenshell.file,
    value: IfcValue,
) -> ifcopenshell.entity_instance:
    """Convert an IfcValue to an IfcOpenShell NominalValue wrapper.

    Raises ``ValueError`` for ``IfcRef`` and ``IfcList`` — NominalValue must
    be a scalar. See DESIGN.md §3 "IfcValue → NominalValue type mapping".
    """
    if isinstance(value, IfcString):
        return model.create_entity("IfcLabel", wrappedValue=value.value)
    if isinstance(value, IfcFloat):
        return model.create_entity("IfcReal", wrappedValue=value.value)
    if isinstance(value, IfcInt):
        return model.create_entity("IfcInteger", wrappedValue=value.value)
    if isinstance(value, IfcBool):
        return model.create_entity("IfcBoolean", wrappedValue=value.value)
    if isinstance(value, (IfcRef, IfcList)):
        raise ValueError(
            f"IfcValue variant {type(value).__name__!r} cannot be stored as "
            "NominalValue — NominalValue must be a scalar (string, int, float, bool)."
        )
    raise ValueError(f"Unsupported IfcValue variant {type(value).__name__!r} for NominalValue.")


__all__ = ["apply_op"]
