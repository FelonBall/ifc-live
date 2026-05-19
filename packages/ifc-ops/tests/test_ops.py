"""Round-trip JSON serialization tests for every IfcOp type and IfcValue type."""

from __future__ import annotations

import uuid

import pytest
from pydantic import TypeAdapter, ValidationError

from ifc_ops import (
    SCHEMA_VERSION,
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
    IfcValue,
    ModifyAttribute,
    SetPropertyValue,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_value_adapter: TypeAdapter[IfcValue] = TypeAdapter(IfcValue)
_mutation_adapter: TypeAdapter[IfcMutation] = TypeAdapter(IfcMutation)

_OP_ID = uuid.UUID("00000000-0000-7000-8000-000000000001")
_PARENT_OP_ID = uuid.UUID("00000000-0000-7000-8000-000000000000")
_GUID = "3fSEzHa$D1Hv_MlW1vNfSa"
_FILE_ID = "demo"
_AUTHOR = "session-1"
_TIMESTAMP = 1_716_000_000.0


def _make_envelope(payload: IfcMutation) -> IfcOpEnvelope:
    return IfcOpEnvelope(
        op_id=_OP_ID,
        parent_op_id=_PARENT_OP_ID,
        file_id=_FILE_ID,
        author=_AUTHOR,
        timestamp=_TIMESTAMP,
        payload=payload,
    )


def _value_roundtrip(
    v: IfcString | IfcInt | IfcFloat | IfcBool | IfcEnum | IfcRef | IfcList | IfcNull,
) -> IfcValue:
    return _value_adapter.validate_json(v.model_dump_json())


def _envelope_roundtrip(env: IfcOpEnvelope) -> IfcOpEnvelope:
    return IfcOpEnvelope.model_validate_json(env.model_dump_json())


# ---------------------------------------------------------------------------
# IfcValue round-trips
# ---------------------------------------------------------------------------


def test_ifc_string_roundtrip() -> None:
    v = IfcString(value="Wall-North")
    assert _value_roundtrip(v) == v


def test_ifc_string_empty() -> None:
    v = IfcString(value="")
    assert _value_roundtrip(v) == v


def test_ifc_int_roundtrip() -> None:
    v = IfcInt(value=42)
    assert _value_roundtrip(v) == v


def test_ifc_int_negative() -> None:
    v = IfcInt(value=-7)
    assert _value_roundtrip(v) == v


def test_ifc_float_roundtrip() -> None:
    v = IfcFloat(value=3.14)
    assert _value_roundtrip(v) == v


def test_ifc_float_zero() -> None:
    v = IfcFloat(value=0.0)
    assert _value_roundtrip(v) == v


def test_ifc_bool_true_roundtrip() -> None:
    v = IfcBool(value=True)
    assert _value_roundtrip(v) == v


def test_ifc_bool_false_roundtrip() -> None:
    v = IfcBool(value=False)
    assert _value_roundtrip(v) == v


def test_ifc_enum_roundtrip() -> None:
    v = IfcEnum(value="ELEMENT")
    assert _value_roundtrip(v) == v


def test_ifc_ref_roundtrip() -> None:
    v = IfcRef(guid=_GUID)
    assert _value_roundtrip(v) == v


def test_ifc_null_roundtrip() -> None:
    v = IfcNull()
    assert _value_roundtrip(v) == v


def test_ifc_list_empty_roundtrip() -> None:
    v = IfcList(values=[])
    assert _value_roundtrip(v) == v


def test_ifc_list_homogeneous_roundtrip() -> None:
    v = IfcList(values=[IfcFloat(value=1.0), IfcFloat(value=0.0), IfcFloat(value=0.0)])
    assert _value_roundtrip(v) == v


def test_ifc_list_mixed_roundtrip() -> None:
    """IfcList can hold any IfcValue variant, including nested IfcLists."""
    v = IfcList(
        values=[
            IfcString(value="name"),
            IfcInt(value=1),
            IfcNull(),
            IfcList(values=[IfcFloat(value=0.5), IfcFloat(value=1.5)]),
        ]
    )
    assert _value_roundtrip(v) == v


def test_ifc_list_with_ref_roundtrip() -> None:
    v = IfcList(values=[IfcRef(guid=_GUID), IfcRef(guid="AnotherGuid000")])
    assert _value_roundtrip(v) == v


def test_ifc_list_nested_list_of_refs_roundtrip() -> None:
    """Depth-2 nesting: IfcList → IfcList → IfcRef.

    This is the recursion case most likely to expose broken discriminated-union
    resolution — if model_rebuild() failed silently, IfcRef inside a nested
    IfcList would deserialize as a plain dict instead of an IfcRef.
    """
    v = IfcList(
        values=[
            IfcList(values=[IfcRef(guid="Guid0000001"), IfcRef(guid="Guid0000002")]),
            IfcList(values=[IfcRef(guid="Guid0000003")]),
        ]
    )
    restored = _value_roundtrip(v)
    assert restored == v
    assert isinstance(restored, IfcList)
    inner = restored.values[0]
    assert isinstance(inner, IfcList)
    assert isinstance(inner.values[0], IfcRef)


# ---------------------------------------------------------------------------
# IfcMutation round-trips (via IfcOpEnvelope)
# ---------------------------------------------------------------------------


def test_add_entity_empty_attributes_roundtrip() -> None:
    env = _make_envelope(AddEntity(guid=_GUID, ifc_type="IfcProject", attributes={}))
    assert _envelope_roundtrip(env) == env


def test_add_entity_with_attributes_roundtrip() -> None:
    env = _make_envelope(
        AddEntity(
            guid=_GUID,
            ifc_type="IfcWall",
            attributes={
                "Name": IfcString(value="Wall-1"),
                "ObjectType": IfcNull(),
                "PredefinedType": IfcEnum(value="SOLIDWALL"),
                "Height": IfcFloat(value=3.0),
                "Placement": IfcRef(guid="PlacementGuid0"),
            },
        )
    )
    assert _envelope_roundtrip(env) == env


def test_add_entity_all_value_types_roundtrip() -> None:
    """AddEntity.attributes can hold every IfcValue variant."""
    env = _make_envelope(
        AddEntity(
            guid=_GUID,
            ifc_type="IfcWall",
            attributes={
                "s": IfcString(value="x"),
                "i": IfcInt(value=1),
                "f": IfcFloat(value=1.5),
                "b": IfcBool(value=True),
                "e": IfcEnum(value="ELEMENT"),
                "r": IfcRef(guid="SomeGuid0000"),
                "l": IfcList(values=[IfcFloat(value=0.0)]),
                "n": IfcNull(),
            },
        )
    )
    assert _envelope_roundtrip(env) == env


def test_delete_entity_roundtrip() -> None:
    env = _make_envelope(
        DeleteEntity(
            guid=_GUID,
            previous_snapshot={
                "GlobalId": _GUID,
                "Name": "Wall-1",
                "Height": 3.0,
                "IsExternal": True,
            },
        )
    )
    assert _envelope_roundtrip(env) == env


def test_delete_entity_empty_snapshot_roundtrip() -> None:
    env = _make_envelope(DeleteEntity(guid=_GUID, previous_snapshot={}))
    assert _envelope_roundtrip(env) == env


def test_modify_attribute_roundtrip() -> None:
    env = _make_envelope(
        ModifyAttribute(
            guid=_GUID,
            attribute="Name",
            previous_value=IfcString(value="Wall-1"),
            new_value=IfcString(value="Wall-North"),
        )
    )
    assert _envelope_roundtrip(env) == env


def test_modify_attribute_null_to_string_roundtrip() -> None:
    env = _make_envelope(
        ModifyAttribute(
            guid=_GUID,
            attribute="ObjectType",
            previous_value=IfcNull(),
            new_value=IfcString(value="LOADBEARING"),
        )
    )
    assert _envelope_roundtrip(env) == env


@pytest.mark.parametrize(
    ("prev", "new"),
    [
        (IfcInt(value=0), IfcInt(value=1)),
        (IfcFloat(value=2.5), IfcFloat(value=3.0)),
        (IfcBool(value=False), IfcBool(value=True)),
        (IfcEnum(value="NOTDEFINED"), IfcEnum(value="SOLIDWALL")),
        (IfcRef(guid="OldGuid0000"), IfcRef(guid="NewGuid0000")),
        (IfcList(values=[IfcFloat(value=0.0)]), IfcList(values=[IfcFloat(value=1.0)])),
        (IfcNull(), IfcNull()),
    ],
)
def test_modify_attribute_value_variants(
    prev: IfcString | IfcInt | IfcFloat | IfcBool | IfcEnum | IfcRef | IfcList | IfcNull,
    new: IfcString | IfcInt | IfcFloat | IfcBool | IfcEnum | IfcRef | IfcList | IfcNull,
) -> None:
    env = _make_envelope(
        ModifyAttribute(guid=_GUID, attribute="x", previous_value=prev, new_value=new)
    )
    assert _envelope_roundtrip(env) == env


def test_set_property_value_new_property_roundtrip() -> None:
    """previous_value=None when the property did not exist before."""
    env = _make_envelope(
        SetPropertyValue(
            entity_guid=_GUID,
            pset_name="Pset_WallCommon",
            property_name="FireRating",
            previous_value=None,
            new_value=IfcString(value="REI 60"),
        )
    )
    assert _envelope_roundtrip(env) == env


def test_set_property_value_update_roundtrip() -> None:
    env = _make_envelope(
        SetPropertyValue(
            entity_guid=_GUID,
            pset_name="Pset_WallCommon",
            property_name="IsExternal",
            previous_value=IfcBool(value=False),
            new_value=IfcBool(value=True),
        )
    )
    assert _envelope_roundtrip(env) == env


def test_set_property_value_float_roundtrip() -> None:
    env = _make_envelope(
        SetPropertyValue(
            entity_guid=_GUID,
            pset_name="Pset_SlabCommon",
            property_name="ThermalTransmittance",
            previous_value=IfcFloat(value=0.25),
            new_value=IfcFloat(value=0.18),
        )
    )
    assert _envelope_roundtrip(env) == env


# ---------------------------------------------------------------------------
# IfcOpEnvelope — envelope-level behaviour
# ---------------------------------------------------------------------------


def test_envelope_schema_version_is_one() -> None:
    env = _make_envelope(AddEntity(guid=_GUID, ifc_type="IfcProject", attributes={}))
    assert env.schema_version == SCHEMA_VERSION == "1"


def test_envelope_no_parent_op_id_roundtrip() -> None:
    """First op in a session has parent_op_id=None."""
    env = IfcOpEnvelope(
        op_id=_OP_ID,
        parent_op_id=None,
        file_id=_FILE_ID,
        author=_AUTHOR,
        timestamp=_TIMESTAMP,
        payload=AddEntity(guid=_GUID, ifc_type="IfcProject", attributes={}),
    )
    assert _envelope_roundtrip(env) == env


def test_envelope_preserves_uuid_roundtrip() -> None:
    op_id = uuid.uuid4()
    parent_id = uuid.uuid4()
    env = IfcOpEnvelope(
        op_id=op_id,
        parent_op_id=parent_id,
        file_id=_FILE_ID,
        author=_AUTHOR,
        timestamp=_TIMESTAMP,
        payload=DeleteEntity(guid=_GUID, previous_snapshot={}),
    )
    restored = _envelope_roundtrip(env)
    assert restored.op_id == op_id
    assert restored.parent_op_id == parent_id


def test_envelope_mutation_discriminator_roundtrip() -> None:
    """Each mutation kind deserializes to the correct concrete type."""
    for payload in [
        AddEntity(guid=_GUID, ifc_type="IfcWall", attributes={}),
        DeleteEntity(guid=_GUID, previous_snapshot={}),
        ModifyAttribute(
            guid=_GUID, attribute="Name", previous_value=IfcNull(), new_value=IfcString(value="x")
        ),
        SetPropertyValue(
            entity_guid=_GUID,
            pset_name="P",
            property_name="q",
            previous_value=None,
            new_value=IfcNull(),
        ),
    ]:
        env = _make_envelope(payload)
        restored = _envelope_roundtrip(env)
        assert type(restored.payload) is type(payload)
        assert restored.payload.kind == payload.kind


# ---------------------------------------------------------------------------
# Validation / negative tests — pin that Pydantic rejects bad input
# ---------------------------------------------------------------------------

_VALID_ENVELOPE_PREFIX = (
    '{"schema_version":"1",'
    f'"op_id":"{_OP_ID}",'
    '"parent_op_id":null,'
    f'"file_id":"{_FILE_ID}",'
    f'"author":"{_AUTHOR}",'
    f'"timestamp":{_TIMESTAMP},'
)


def test_envelope_rejects_unknown_payload_kind() -> None:
    json_str = _VALID_ENVELOPE_PREFIX + '"payload":{"kind":"bogus"}}'
    with pytest.raises(ValidationError):
        IfcOpEnvelope.model_validate_json(json_str)


def test_envelope_rejects_wrong_schema_version() -> None:
    json_str = (
        '{"schema_version":"99",'
        f'"op_id":"{_OP_ID}",'
        '"parent_op_id":null,'
        f'"file_id":"{_FILE_ID}",'
        f'"author":"{_AUTHOR}",'
        f'"timestamp":{_TIMESTAMP},'
        f'"payload":{{"kind":"add_entity","guid":"{_GUID}","ifc_type":"IfcWall","attributes":{{}}}}}}'
    )
    with pytest.raises(ValidationError):
        IfcOpEnvelope.model_validate_json(json_str)


def test_envelope_rejects_missing_payload() -> None:
    json_str = _VALID_ENVELOPE_PREFIX.rstrip(",") + "}"
    with pytest.raises(ValidationError):
        IfcOpEnvelope.model_validate_json(json_str)


def test_ifc_value_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        _value_adapter.validate_json('{"kind":"unknown","value":"x"}')
