"""Tests for ifc_sync_core.apply and ifc_sync_core.serialize.

Covers:
- Round-trip ops (AddEntity, DeleteEntity, ModifyAttribute, SetPropertyValue)
- Non-root entity path (IfcLocalPlacement with synthetic GUID)
- Error paths (bare ValueError for unsupported variants)
"""

from __future__ import annotations

import ifcopenshell
import ifcopenshell.guid
import pytest

from ifc_ops import (
    AddEntity,
    DeleteEntity,
    IfcBool,
    IfcFloat,
    IfcInt,
    IfcList,
    IfcNull,
    IfcRef,
    IfcString,
    ModifyAttribute,
    SetPropertyValue,
)
from ifc_sync_core.apply import _to_nominal_value, apply_op
from ifc_sync_core.serialize import (
    deserialize_value,
    register_non_root,
    serialize_value,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fresh_model() -> ifcopenshell.file:
    return ifcopenshell.file(schema="IFC4")


def _wall_guid() -> str:
    return ifcopenshell.guid.new()


# ---------------------------------------------------------------------------
# AddEntity — IfcRoot path
# ---------------------------------------------------------------------------


def test_apply_add_entity_ifc_root() -> None:
    model = _fresh_model()
    guid = _wall_guid()
    op = AddEntity(guid=guid, ifc_type="IfcWall", attributes={})

    apply_op(model, op)

    entity = model.by_guid(guid)
    assert entity is not None
    assert entity.is_a("IfcWall")
    assert entity.GlobalId == guid


def test_apply_add_entity_with_attributes() -> None:
    model = _fresh_model()
    guid = _wall_guid()
    op = AddEntity(
        guid=guid,
        ifc_type="IfcWall",
        attributes={"Name": IfcString(value="Wall-North")},
    )

    apply_op(model, op)

    entity = model.by_guid(guid)
    assert entity.Name == "Wall-North"


# ---------------------------------------------------------------------------
# DeleteEntity
# ---------------------------------------------------------------------------


def test_apply_delete_entity() -> None:
    model = _fresh_model()
    guid = _wall_guid()
    apply_op(model, AddEntity(guid=guid, ifc_type="IfcWall", attributes={}))

    apply_op(
        model,
        DeleteEntity(guid=guid, previous_snapshot={}),
    )

    with pytest.raises(RuntimeError):
        model.by_guid(guid)


# ---------------------------------------------------------------------------
# ModifyAttribute
# ---------------------------------------------------------------------------


def test_apply_modify_attribute() -> None:
    model = _fresh_model()
    guid = _wall_guid()
    apply_op(
        model,
        AddEntity(
            guid=guid,
            ifc_type="IfcWall",
            attributes={"Name": IfcString(value="Original")},
        ),
    )

    apply_op(
        model,
        ModifyAttribute(
            guid=guid,
            attribute="Name",
            previous_value=IfcString(value="Original"),
            new_value=IfcString(value="Modified"),
        ),
    )

    assert model.by_guid(guid).Name == "Modified"


# ---------------------------------------------------------------------------
# SetPropertyValue
# ---------------------------------------------------------------------------


def test_apply_set_property_value_creates_pset() -> None:
    model = _fresh_model()
    guid = _wall_guid()
    apply_op(model, AddEntity(guid=guid, ifc_type="IfcWall", attributes={}))

    apply_op(
        model,
        SetPropertyValue(
            entity_guid=guid,
            pset_name="Pset_WallCommon",
            property_name="FireRating",
            previous_value=None,
            new_value=IfcString(value="REI 60"),
        ),
    )

    # Verify the pset was created and linked
    entity = model.by_guid(guid)
    psets = [
        rel.RelatingPropertyDefinition
        for rel in model.get_inverse(entity)
        if rel.is_a("IfcRelDefinesByProperties")
        and rel.RelatingPropertyDefinition.is_a("IfcPropertySet")
        and rel.RelatingPropertyDefinition.Name == "Pset_WallCommon"
    ]
    assert len(psets) == 1
    props = {p.Name: p for p in psets[0].HasProperties}
    assert "FireRating" in props
    assert props["FireRating"].NominalValue.wrappedValue == "REI 60"


def test_apply_set_property_value_updates_existing() -> None:
    model = _fresh_model()
    guid = _wall_guid()
    apply_op(model, AddEntity(guid=guid, ifc_type="IfcWall", attributes={}))

    for value in ("REI 30", "REI 60"):
        apply_op(
            model,
            SetPropertyValue(
                entity_guid=guid,
                pset_name="Pset_WallCommon",
                property_name="FireRating",
                previous_value=None,
                new_value=IfcString(value=value),
            ),
        )

    entity = model.by_guid(guid)
    psets = [
        rel.RelatingPropertyDefinition
        for rel in model.get_inverse(entity)
        if rel.is_a("IfcRelDefinesByProperties")
        and rel.RelatingPropertyDefinition.is_a("IfcPropertySet")
        and rel.RelatingPropertyDefinition.Name == "Pset_WallCommon"
    ]
    props = {p.Name: p for p in psets[0].HasProperties}
    # Should still be only one property entry
    assert len(props) == 1
    assert props["FireRating"].NominalValue.wrappedValue == "REI 60"


# ---------------------------------------------------------------------------
# Non-root entity path (Commit C scope)
# ---------------------------------------------------------------------------


def test_add_non_root_entity() -> None:
    """AddEntity for a non-IfcRoot type registers the synthetic GUID."""
    model = _fresh_model()
    synthetic_guid = ifcopenshell.guid.new()
    op = AddEntity(
        guid=synthetic_guid,
        ifc_type="IfcLocalPlacement",
        attributes={},
    )

    apply_op(model, op)

    # Entity should be findable via the synthetic GUID through deserialize_value
    resolved = deserialize_value(model, IfcRef(guid=synthetic_guid))
    assert resolved is not None
    assert resolved.is_a("IfcLocalPlacement")


def test_resolve_non_root_via_ifc_ref() -> None:
    """deserialize_value resolves a synthetic GUID to the correct entity."""
    model = _fresh_model()
    synthetic_guid = ifcopenshell.guid.new()
    apply_op(
        model,
        AddEntity(guid=synthetic_guid, ifc_type="IfcLocalPlacement", attributes={}),
    )

    resolved = deserialize_value(model, IfcRef(guid=synthetic_guid))
    assert resolved.is_a("IfcLocalPlacement")


def test_non_root_entity_has_correct_type() -> None:
    """The resolved non-root entity is the same instance that was created."""
    model = _fresh_model()
    synthetic_guid = ifcopenshell.guid.new()
    apply_op(
        model,
        AddEntity(guid=synthetic_guid, ifc_type="IfcDirection", attributes={}),
    )

    resolved = deserialize_value(model, IfcRef(guid=synthetic_guid))
    assert resolved.is_a("IfcDirection")


# ---------------------------------------------------------------------------
# Error paths — _to_nominal_value
# ---------------------------------------------------------------------------


def test_to_nominal_value_raises_for_ref() -> None:
    model = _fresh_model()
    with pytest.raises(ValueError, match="NominalValue"):
        _to_nominal_value(model, IfcRef(guid="some-guid"))


def test_to_nominal_value_raises_for_list() -> None:
    model = _fresh_model()
    with pytest.raises(ValueError, match="NominalValue"):
        _to_nominal_value(model, IfcList(values=[IfcInt(value=1)]))


# ---------------------------------------------------------------------------
# Error paths — serialize_value
# ---------------------------------------------------------------------------


def test_serialize_value_raises_for_unregistered_entity() -> None:
    """serialize_value raises ValueError for an entity with no GlobalId that
    is not in the non-root registry."""
    model = _fresh_model()
    # IfcLocalPlacement has no GlobalId — create it directly without registering
    placement = model.create_entity("IfcLocalPlacement")

    with pytest.raises(ValueError, match="register_non_root"):
        serialize_value(model, placement)


# ---------------------------------------------------------------------------
# serialize_value basics
# ---------------------------------------------------------------------------


def test_serialize_value_scalars() -> None:
    model = _fresh_model()
    assert serialize_value(model, None) == IfcNull()
    assert serialize_value(model, True) == IfcBool(value=True)
    assert serialize_value(model, 42) == IfcInt(value=42)
    assert serialize_value(model, 3.14) == IfcFloat(value=3.14)
    assert serialize_value(model, "hello") == IfcString(value="hello")


def test_serialize_value_bool_before_int() -> None:
    """bool is a subclass of int; True must serialize as IfcBool not IfcInt."""
    model = _fresh_model()
    result = serialize_value(model, True)
    assert isinstance(result, IfcBool)


def test_serialize_value_root_entity() -> None:
    model = _fresh_model()
    guid = _wall_guid()
    wall = model.create_entity("IfcWall")
    wall.GlobalId = guid

    result = serialize_value(model, wall)
    assert result == IfcRef(guid=guid)


def test_serialize_value_non_root_registered() -> None:
    model = _fresh_model()
    placement = model.create_entity("IfcLocalPlacement")
    synthetic = register_non_root(model, placement)

    result = serialize_value(model, placement)
    assert result == IfcRef(guid=synthetic)
