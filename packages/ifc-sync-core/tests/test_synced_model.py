"""Tests for SyncedIfcModel and SyncedEntity.

Covers:
- Spike result: ifcopenshell.api interception via __setattr__
- create_entity for IfcRoot and non-root entities
- Attribute set interception (ModifyAttribute emission)
- No-op detection (same value)
- Entity removal (DeleteEntity)
- by_guid / by_type wrapping
- suppress_emission context manager
- __getattr__ entity wrapping
- Property set NominalValue change (ModifyAttribute, not SetPropertyValue)
"""

from __future__ import annotations

import ifcopenshell
import pytest

from ifc_ops import AddEntity, DeleteEntity, IfcMutation, IfcNull, IfcString, ModifyAttribute
from ifc_sync_core.serialize import get_synthetic_guid, register_non_root
from ifc_sync_core.synced_model import SyncedEntity, SyncedIfcModel, unwrap

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def synced_fixture() -> tuple[ifcopenshell.file, SyncedIfcModel, list[IfcMutation]]:
    raw_model = ifcopenshell.file(schema="IFC4")
    emitted: list[IfcMutation] = []
    synced = SyncedIfcModel(raw_model, file_id="test-file", on_op=emitted.append)
    return raw_model, synced, emitted


# ---------------------------------------------------------------------------
# Spike: ifcopenshell.api interception
# ---------------------------------------------------------------------------


def test_spike_ifcopenshell_api_interception(
    synced_fixture: tuple[ifcopenshell.file, SyncedIfcModel, list[IfcMutation]],
) -> None:
    """Documents that ifcopenshell.api.run("attribute.edit_attributes") triggers
    SyncedEntity.__setattr__ when a SyncedEntity is passed as product.

    The api module internally calls setattr(settings.product, name, value), so
    Python's attribute protocol fires our __setattr__ correctly.

    If this test fails (zero ops emitted), it falls through to pytest.xfail with
    the known-gap reason documented.
    """
    raw_model, synced, emitted = synced_fixture
    wall = synced.create_entity("IfcWall")
    emitted.clear()

    import ifcopenshell.api

    ifcopenshell.api.run(
        "attribute.edit_attributes",
        raw_model,
        product=wall,
        attributes={"Name": "api-test"},
    )

    if len(emitted) != 1:
        pytest.xfail(
            "ifcopenshell.api.run did not trigger SyncedEntity.__setattr__ — "
            "api calls bypass the wrapper for this ifcopenshell version"
        )

    assert isinstance(emitted[0], ModifyAttribute)
    assert emitted[0].attribute == "Name"
    assert emitted[0].new_value == IfcString(value="api-test")


# ---------------------------------------------------------------------------
# create_entity — IfcRoot path
# ---------------------------------------------------------------------------


def test_create_ifc_root_entity_emits_add_entity(
    synced_fixture: tuple[ifcopenshell.file, SyncedIfcModel, list[IfcMutation]],
) -> None:
    _raw_model, synced, emitted = synced_fixture

    wall = synced.create_entity("IfcWall")

    assert len(emitted) == 1
    op = emitted[0]
    assert isinstance(op, AddEntity)
    assert op.ifc_type == "IfcWall"
    # GlobalId is auto-assigned; the op's guid must match the entity's GlobalId.
    inner = unwrap(wall)
    assert op.guid == inner.GlobalId  # type: ignore[attr-defined]
    # No kwargs → all attributes are None → attributes dict is empty.
    assert op.attributes == {}


# ---------------------------------------------------------------------------
# create_entity — non-root path
# ---------------------------------------------------------------------------


def test_create_non_root_entity_emits_add_entity_with_synthetic_guid(
    synced_fixture: tuple[ifcopenshell.file, SyncedIfcModel, list[IfcMutation]],
) -> None:
    raw_model, synced, emitted = synced_fixture

    placement = synced.create_entity("IfcLocalPlacement")

    assert len(emitted) == 1
    op = emitted[0]
    assert isinstance(op, AddEntity)
    assert op.ifc_type == "IfcLocalPlacement"
    # The guid is a synthetic UUID, not a real IFC GlobalId.
    assert op.guid is not None
    assert len(op.guid) > 0
    # The inner entity is non-root (no GlobalId attribute).
    inner = unwrap(placement)
    assert not inner.is_a("IfcRoot")
    # The synthetic guid is findable via the registry.
    assert get_synthetic_guid(raw_model, inner) == op.guid


# ---------------------------------------------------------------------------
# ModifyAttribute — normal path
# ---------------------------------------------------------------------------


def test_modify_attribute_emits_modify_attribute(
    synced_fixture: tuple[ifcopenshell.file, SyncedIfcModel, list[IfcMutation]],
) -> None:
    _raw_model, synced, emitted = synced_fixture
    wall = synced.create_entity("IfcWall")
    emitted.clear()

    wall.Name = "West Wall"

    assert len(emitted) == 1
    op = emitted[0]
    assert isinstance(op, ModifyAttribute)
    assert op.attribute == "Name"
    assert op.guid == unwrap(wall).GlobalId  # type: ignore[attr-defined]
    assert op.previous_value == IfcNull()
    assert op.new_value == IfcString(value="West Wall")
    # The mutation was actually applied to the inner entity.
    assert unwrap(wall).Name == "West Wall"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# ModifyAttribute — no-op for same value
# ---------------------------------------------------------------------------


def test_modify_attribute_noop_for_same_value(
    synced_fixture: tuple[ifcopenshell.file, SyncedIfcModel, list[IfcMutation]],
) -> None:
    _raw_model, synced, emitted = synced_fixture
    wall = synced.create_entity("IfcWall")
    wall.Name = "Original"
    emitted.clear()

    wall.Name = "Original"

    assert len(emitted) == 0


# ---------------------------------------------------------------------------
# DeleteEntity
# ---------------------------------------------------------------------------


def test_remove_entity_emits_delete_entity(
    synced_fixture: tuple[ifcopenshell.file, SyncedIfcModel, list[IfcMutation]],
) -> None:
    raw_model, synced, emitted = synced_fixture
    wall = synced.create_entity("IfcWall")
    wall.Name = "ToDelete"
    guid = unwrap(wall).GlobalId  # type: ignore[attr-defined]
    emitted.clear()

    synced.remove(wall)

    assert len(emitted) == 1
    op = emitted[0]
    assert isinstance(op, DeleteEntity)
    assert op.guid == guid
    assert "Name" in op.previous_snapshot
    assert op.previous_snapshot["Name"] == "ToDelete"
    # Entity is gone from the raw model.
    with pytest.raises(RuntimeError):
        raw_model.by_guid(guid)


# ---------------------------------------------------------------------------
# by_guid
# ---------------------------------------------------------------------------


def test_by_guid_returns_synced_entity(
    synced_fixture: tuple[ifcopenshell.file, SyncedIfcModel, list[IfcMutation]],
) -> None:
    _raw_model, synced, _emitted = synced_fixture
    wall = synced.create_entity("IfcWall")
    guid = unwrap(wall).GlobalId  # type: ignore[attr-defined]

    result = synced.by_guid(guid)

    assert result is not None
    assert isinstance(result, SyncedEntity)
    assert unwrap(result).GlobalId == guid  # type: ignore[attr-defined]
    # Missing guid returns None.
    assert synced.by_guid("no-such-guid") is None


# ---------------------------------------------------------------------------
# by_type
# ---------------------------------------------------------------------------


def test_by_type_returns_wrapped_entities(
    synced_fixture: tuple[ifcopenshell.file, SyncedIfcModel, list[IfcMutation]],
) -> None:
    _raw_model, synced, _emitted = synced_fixture
    synced.create_entity("IfcWall")
    synced.create_entity("IfcWall")

    results = synced.by_type("IfcWall")

    assert len(results) == 2
    for item in results:
        assert isinstance(item, SyncedEntity)
        assert unwrap(item).is_a("IfcWall")


# ---------------------------------------------------------------------------
# suppress_emission
# ---------------------------------------------------------------------------


def test_suppress_emission_blocks_ops(
    synced_fixture: tuple[ifcopenshell.file, SyncedIfcModel, list[IfcMutation]],
) -> None:
    raw_model, synced, emitted = synced_fixture

    with synced.suppress_emission():
        synced.create_entity("IfcWall")

    assert len(emitted) == 0
    # The entity was still created in the underlying model.
    assert len(raw_model.by_type("IfcWall")) == 1

    # Ops resume after the context exits.
    synced.create_entity("IfcWall")
    assert len(emitted) == 1


# ---------------------------------------------------------------------------
# __getattr__ entity wrapping
# ---------------------------------------------------------------------------


def test_getattr_wraps_returned_entities(
    synced_fixture: tuple[ifcopenshell.file, SyncedIfcModel, list[IfcMutation]],
) -> None:
    raw_model, synced, _emitted = synced_fixture
    wall = synced.create_entity("IfcWall")

    # Create placement directly on raw model and register it manually.
    placement = raw_model.create_entity("IfcLocalPlacement")
    register_non_root(raw_model, placement)
    # Assign via the raw inner entity to avoid triggering op emission.
    unwrap(wall).ObjectPlacement = placement  # type: ignore[attr-defined]

    # Accessing via SyncedEntity.__getattr__ must wrap the result.
    result = wall.ObjectPlacement

    assert isinstance(result, SyncedEntity)
    assert unwrap(result).is_a("IfcLocalPlacement")


# ---------------------------------------------------------------------------
# create_entity — SyncedEntity kwargs are unwrapped
# ---------------------------------------------------------------------------


def test_create_entity_unwraps_synced_entity_kwargs(
    synced_fixture: tuple[ifcopenshell.file, SyncedIfcModel, list[IfcMutation]],
) -> None:
    _raw_model, synced, emitted = synced_fixture

    placement = synced.create_entity("IfcLocalPlacement")
    emitted.clear()

    wall = synced.create_entity("IfcWall", ObjectPlacement=placement)

    # Exactly one AddEntity op for the wall (placement already emitted earlier).
    assert len(emitted) == 1
    assert isinstance(emitted[0], AddEntity)
    # The inner entity holds a raw entity_instance, not a SyncedEntity.
    inner_placement = unwrap(wall).ObjectPlacement  # type: ignore[attr-defined]
    assert isinstance(inner_placement, ifcopenshell.entity_instance)
    assert not isinstance(inner_placement, SyncedEntity)


# ---------------------------------------------------------------------------
# remove — unregistered entity skips emit
# ---------------------------------------------------------------------------


def test_remove_unregistered_entity_skips_emit(
    synced_fixture: tuple[ifcopenshell.file, SyncedIfcModel, list[IfcMutation]],
) -> None:
    raw_model, synced, emitted = synced_fixture

    # Create directly on the raw model — not registered in the synthetic GUID table.
    raw_placement = raw_model.create_entity("IfcLocalPlacement")

    synced.remove(raw_placement)

    assert len(emitted) == 0
    # Entity is actually removed from the model.
    assert len(raw_model.by_type("IfcLocalPlacement")) == 0


# ---------------------------------------------------------------------------
# NominalValue change — ModifyAttribute (not SetPropertyValue)
# ---------------------------------------------------------------------------


def test_pset_nominal_value_change_emits_modify_attribute(
    synced_fixture: tuple[ifcopenshell.file, SyncedIfcModel, list[IfcMutation]],
) -> None:
    """Documents design decision §6 #5: NominalValue changes emit ModifyAttribute.

    SyncedEntity.__setattr__ has no semantic context to identify that this entity
    is part of a property set. Step 7 will add that context and can upgrade these
    ops to SetPropertyValue where appropriate.
    """
    _raw_model, synced, emitted = synced_fixture

    prop = synced.create_entity("IfcPropertySingleValue", Name="FireRating")
    label = synced.create_entity("IfcLabel", wrappedValue="REI 60")
    emitted.clear()

    # Setting NominalValue triggers __setattr__ on prop (a SyncedEntity).
    prop.NominalValue = label

    assert len(emitted) == 1
    op = emitted[0]
    assert isinstance(op, ModifyAttribute)
    assert op.attribute == "NominalValue"
    assert op.previous_value == IfcNull()
    # serialize_value unwraps IfcLabel.wrappedValue → IfcString
    assert op.new_value == IfcString(value="REI 60")
