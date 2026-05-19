"""Integration tests for ifc_sync_core.apply and ifc_sync_core.serialize."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from ifc_ops import (
    AddEntity,
    DeleteEntity,
    IfcBool,
    IfcEnum,
    IfcFloat,
    IfcInt,
    IfcList,
    IfcMutation,
    IfcNull,
    IfcOpEnvelope,
    IfcRef,
    IfcString,
    ModifyAttribute,
    SetPropertyValue,
)
from ifc_sync_core import apply_op, serialize_entity, serialize_value
from ifc_sync_core.serialize import deserialize_value

_GUID = "3fSEzHa$D1Hv_MlW1vNfSa"
_OP_ID = uuid.UUID("00000000-0000-7000-8000-000000000001")


def _make_envelope(payload: IfcMutation) -> IfcOpEnvelope:
    return IfcOpEnvelope(
        op_id=_OP_ID,
        parent_op_id=None,
        file_id="test",
        author="test-session",
        timestamp=1_716_000_000.0,
        payload=payload,
    )


# ---------------------------------------------------------------------------
# AddEntity
# ---------------------------------------------------------------------------


def test_add_entity_creates_entity(model: Any) -> None:
    apply_op(
        model,
        _make_envelope(
            AddEntity(
                guid=_GUID, ifc_type="IfcWall", attributes={"Name": IfcString(value="Wall-1")}
            )
        ),
    )
    entity = model.by_guid(_GUID)
    assert entity is not None
    assert entity.Name == "Wall-1"


def test_add_entity_null_attribute(model: Any) -> None:
    apply_op(
        model,
        _make_envelope(
            AddEntity(guid=_GUID, ifc_type="IfcWall", attributes={"ObjectType": IfcNull()})
        ),
    )
    assert model.by_guid(_GUID).ObjectType is None


def test_add_entity_float_attribute(model: Any) -> None:
    apply_op(
        model,
        _make_envelope(
            AddEntity(
                guid=_GUID,
                ifc_type="IfcBuildingStorey",
                attributes={"Elevation": IfcFloat(value=3.5)},
            )
        ),
    )
    entity = model.by_guid(_GUID)
    # serialize_value unwraps both plain float and IfcLengthMeasure wrapper transparently
    assert serialize_value(entity.Elevation) == IfcFloat(value=3.5)


# ---------------------------------------------------------------------------
# ModifyAttribute
# ---------------------------------------------------------------------------


def test_modify_attribute(model: Any) -> None:
    apply_op(
        model,
        _make_envelope(
            AddEntity(guid=_GUID, ifc_type="IfcWall", attributes={"Name": IfcString(value="Old")})
        ),
    )
    apply_op(
        model,
        _make_envelope(
            ModifyAttribute(
                guid=_GUID,
                attribute="Name",
                previous_value=IfcString(value="Old"),
                new_value=IfcString(value="New"),
            )
        ),
    )
    assert model.by_guid(_GUID).Name == "New"


def test_modify_attribute_to_null(model: Any) -> None:
    apply_op(
        model,
        _make_envelope(
            AddEntity(guid=_GUID, ifc_type="IfcWall", attributes={"Name": IfcString(value="Wall")})
        ),
    )
    apply_op(
        model,
        _make_envelope(
            ModifyAttribute(
                guid=_GUID,
                attribute="Name",
                previous_value=IfcString(value="Wall"),
                new_value=IfcNull(),
            )
        ),
    )
    assert model.by_guid(_GUID).Name is None


# ---------------------------------------------------------------------------
# DeleteEntity
# ---------------------------------------------------------------------------


def test_delete_entity(model: Any) -> None:
    apply_op(model, _make_envelope(AddEntity(guid=_GUID, ifc_type="IfcWall", attributes={})))
    assert model.by_guid(_GUID) is not None
    apply_op(model, _make_envelope(DeleteEntity(guid=_GUID, previous_snapshot={})))
    with pytest.raises(RuntimeError):
        model.by_guid(_GUID)


def test_delete_then_readd(model: Any) -> None:
    apply_op(model, _make_envelope(AddEntity(guid=_GUID, ifc_type="IfcWall", attributes={})))
    apply_op(model, _make_envelope(DeleteEntity(guid=_GUID, previous_snapshot={})))
    with pytest.raises(RuntimeError):
        model.by_guid(_GUID)
    apply_op(
        model,
        _make_envelope(
            AddEntity(
                guid=_GUID, ifc_type="IfcWall", attributes={"Name": IfcString(value="Reborn")}
            )
        ),
    )
    assert model.by_guid(_GUID).Name == "Reborn"


# ---------------------------------------------------------------------------
# SetPropertyValue
# ---------------------------------------------------------------------------


def _get_pset(model: Any, entity_guid: str, pset_name: str) -> Any:
    entity = model.by_guid(entity_guid)
    for rel in entity.IsDefinedBy or ():
        if rel.is_a("IfcRelDefinesByProperties"):
            pdef = rel.RelatingPropertyDefinition
            if pdef.is_a("IfcPropertySet") and pdef.Name == pset_name:
                return pdef
    return None


def test_set_property_value_new_property(model: Any) -> None:
    apply_op(model, _make_envelope(AddEntity(guid=_GUID, ifc_type="IfcWall", attributes={})))
    apply_op(
        model,
        _make_envelope(
            SetPropertyValue(
                entity_guid=_GUID,
                pset_name="Pset_WallCommon",
                property_name="FireRating",
                previous_value=None,
                new_value=IfcString(value="REI 60"),
            )
        ),
    )
    pset = _get_pset(model, _GUID, "Pset_WallCommon")
    assert pset is not None
    prop = next((p for p in pset.HasProperties if p.Name == "FireRating"), None)
    assert prop is not None
    assert prop.NominalValue.wrappedValue == "REI 60"


def test_set_property_value_update(model: Any) -> None:
    apply_op(model, _make_envelope(AddEntity(guid=_GUID, ifc_type="IfcWall", attributes={})))
    apply_op(
        model,
        _make_envelope(
            SetPropertyValue(
                entity_guid=_GUID,
                pset_name="Pset_WallCommon",
                property_name="IsExternal",
                previous_value=None,
                new_value=IfcBool(value=False),
            )
        ),
    )
    apply_op(
        model,
        _make_envelope(
            SetPropertyValue(
                entity_guid=_GUID,
                pset_name="Pset_WallCommon",
                property_name="IsExternal",
                previous_value=IfcBool(value=False),
                new_value=IfcBool(value=True),
            )
        ),
    )
    pset = _get_pset(model, _GUID, "Pset_WallCommon")
    assert pset is not None
    prop = next((p for p in pset.HasProperties if p.Name == "IsExternal"), None)
    assert prop is not None
    assert prop.NominalValue.wrappedValue is True


# ---------------------------------------------------------------------------
# Serialize round-trips
# ---------------------------------------------------------------------------


def test_property_set_roundtrip(model: Any) -> None:
    apply_op(model, _make_envelope(AddEntity(guid=_GUID, ifc_type="IfcWall", attributes={})))
    apply_op(
        model,
        _make_envelope(
            SetPropertyValue(
                entity_guid=_GUID,
                pset_name="Pset_WallCommon",
                property_name="FireRating",
                previous_value=None,
                new_value=IfcString(value="REI 90"),
            )
        ),
    )
    pset = _get_pset(model, _GUID, "Pset_WallCommon")
    assert pset is not None
    prop = next((p for p in pset.HasProperties if p.Name == "FireRating"), None)
    assert prop is not None
    assert serialize_value(prop.NominalValue) == IfcString(value="REI 90")


def test_wall_serialize_roundtrip(model: Any) -> None:
    name_val = IfcString(value="Wall-North")
    apply_op(
        model,
        _make_envelope(AddEntity(guid=_GUID, ifc_type="IfcWall", attributes={"Name": name_val})),
    )
    entity = model.by_guid(_GUID)
    assert serialize_value(entity.Name) == name_val


def test_serialize_entity_snapshot(model: Any) -> None:
    apply_op(
        model,
        _make_envelope(
            AddEntity(
                guid=_GUID, ifc_type="IfcWall", attributes={"Name": IfcString(value="SnapshotWall")}
            )
        ),
    )
    snapshot = serialize_entity(model.by_guid(_GUID))
    assert snapshot["GlobalId"] == _GUID
    assert snapshot["Name"] == "SnapshotWall"
    assert "id" not in snapshot


def test_serialize_value_primitives() -> None:
    assert serialize_value(None) == IfcNull()
    assert serialize_value(True) == IfcBool(value=True)
    assert serialize_value(False) == IfcBool(value=False)
    assert serialize_value(42) == IfcInt(value=42)
    assert serialize_value(3.14) == IfcFloat(value=3.14)
    assert serialize_value("hello") == IfcString(value="hello")
    assert serialize_value([1, 2]) == IfcList(values=[IfcInt(value=1), IfcInt(value=2)])


def test_deserialize_value_primitives(model: Any) -> None:
    apply_op(model, _make_envelope(AddEntity(guid=_GUID, ifc_type="IfcWall", attributes={})))
    assert deserialize_value(IfcNull(), model) is None
    assert deserialize_value(IfcString(value="x"), model) == "x"
    assert deserialize_value(IfcInt(value=7), model) == 7
    assert deserialize_value(IfcFloat(value=1.5), model) == pytest.approx(1.5)
    assert deserialize_value(IfcBool(value=True), model) is True
    assert deserialize_value(IfcEnum(value="SOLIDWALL"), model) == "SOLIDWALL"
    assert deserialize_value(IfcList(values=[IfcInt(value=1), IfcInt(value=2)]), model) == [1, 2]
    entity = deserialize_value(IfcRef(guid=_GUID), model)
    assert entity is not None
    assert entity.GlobalId == _GUID


# ---------------------------------------------------------------------------
# Multi-op sequence
# ---------------------------------------------------------------------------


def test_apply_multiple_ops_sequence(model: Any) -> None:
    apply_op(
        model,
        _make_envelope(
            AddEntity(
                guid=_GUID, ifc_type="IfcWall", attributes={"Name": IfcString(value="Initial")}
            )
        ),
    )
    apply_op(
        model,
        _make_envelope(
            ModifyAttribute(
                guid=_GUID,
                attribute="Name",
                previous_value=IfcString(value="Initial"),
                new_value=IfcString(value="Updated"),
            )
        ),
    )
    apply_op(
        model,
        _make_envelope(
            SetPropertyValue(
                entity_guid=_GUID,
                pset_name="Pset_WallCommon",
                property_name="FireRating",
                previous_value=None,
                new_value=IfcString(value="REI 120"),
            )
        ),
    )
    wall = model.by_guid(_GUID)
    assert wall.Name == "Updated"
    pset = _get_pset(model, _GUID, "Pset_WallCommon")
    assert pset is not None
    prop = next((p for p in pset.HasProperties if p.Name == "FireRating"), None)
    assert prop is not None
    assert prop.NominalValue.wrappedValue == "REI 120"
