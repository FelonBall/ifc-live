"""SyncedIfcModel and SyncedEntity — interception wrappers for ifcopenshell.file.

Every mutation applied through these wrappers emits an ``IfcMutation`` op via the
``on_op`` callback, allowing the sync layer to stream changes to the server.

# Spike result: ifcopenshell.api interception (step 4a)
#
# Question: does ifcopenshell.api.run("attribute.edit_attributes", raw_model,
#   product=synced_entity, attributes={...}) trigger SyncedEntity.__setattr__?
#
# Answer: YES. The attribute.edit_attributes module calls setattr(settings.product,
#   name, value) in Python. Since product is our SyncedEntity Python object,
#   Python's attribute protocol fires SyncedEntity.__setattr__ correctly.
#
# Known gap: API calls that create entities internally (e.g. geometry operations
#   that call raw_model.create_entity() directly) bypass SyncedIfcModel.create_entity
#   and do NOT emit AddEntity ops. Step 7 will determine whether module-level
#   patching is needed to close this gap.
#
# Evidence: test_spike_ifcopenshell_api_interception passes without xfail.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import Any

import ifcopenshell
import ifcopenshell.entity_instance
import ifcopenshell.guid

from ifc_ops import AddEntity, DeleteEntity, IfcMutation, ModifyAttribute
from ifc_sync_core.serialize import (
    get_synthetic_guid,
    register_non_root,
    serialize_entity,
    serialize_value,
)

logger = logging.getLogger(__name__)


class SyncedEntity:
    """Proxy for an ``ifcopenshell.entity_instance`` that emits ``ModifyAttribute``
    ops on every attribute set.

    Callers should obtain instances via ``SyncedIfcModel.create_entity``,
    ``by_guid``, or ``by_type`` rather than constructing directly.
    """

    _inner: ifcopenshell.entity_instance
    _model: SyncedIfcModel

    def __init__(
        self,
        entity: ifcopenshell.entity_instance,
        model: SyncedIfcModel,
    ) -> None:
        # Use object.__setattr__ to bypass our own __setattr__ override.
        object.__setattr__(self, "_inner", entity)
        object.__setattr__(self, "_model", model)

    def __setattr__(self, name: str, value: Any) -> None:
        """Intercept attribute sets, emit ModifyAttribute, then apply the change.

        Attributes prefixed with ``_`` are stored on the wrapper object itself
        without emission (used for internal bookkeeping).

        If the entity cannot be identified (unregistered non-root entity whose
        creation bypassed ``SyncedIfcModel.create_entity``), the mutation is
        still applied but no op is emitted; a debug message is logged.
        """
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return

        inner: ifcopenshell.entity_instance = object.__getattribute__(self, "_inner")
        model: SyncedIfcModel = object.__getattribute__(self, "_model")

        # Unwrap SyncedEntity values so IfcOpenShell receives raw entity_instances.
        raw_value: Any = unwrap(value) if isinstance(value, SyncedEntity) else value

        old_value: Any = getattr(inner, name)
        if old_value == raw_value:
            return

        # Resolve the entity's identity for the op.
        # Access to model._model and model._emit is intentional cross-class access
        # within the same module — SyncedEntity and SyncedIfcModel are tightly coupled.
        raw_model = model._model  # type: ignore[reportPrivateUsage]
        guid: str | None
        try:
            guid = inner.GlobalId  # type: ignore[attr-defined]
        except AttributeError:
            guid = get_synthetic_guid(raw_model, inner)

        if guid is not None:
            # TODO: NominalValue changes on IfcPropertySingleValue emit
            # ModifyAttribute here (not SetPropertyValue) because we lack the
            # semantic context to know which pset this property belongs to.
            # Step 7 adds that context and can upgrade these to SetPropertyValue.
            # See DESIGN.md §6 decision #5.
            model._emit(  # type: ignore[reportPrivateUsage]
                ModifyAttribute(
                    guid=guid,
                    attribute=name,
                    previous_value=serialize_value(raw_model, old_value),
                    new_value=serialize_value(raw_model, raw_value),
                )
            )
        else:
            logger.debug(
                "Skipping ModifyAttribute emit for unregistered entity %r — "
                "create via SyncedIfcModel.create_entity to enable op tracking.",
                inner,
            )

        setattr(inner, name, raw_value)

    def __getattr__(self, name: str) -> Any:
        """Proxy attribute access to the inner entity, wrapping entity results."""
        inner: ifcopenshell.entity_instance = object.__getattribute__(self, "_inner")
        model: SyncedIfcModel = object.__getattribute__(self, "_model")
        result: Any = getattr(inner, name)

        if isinstance(result, ifcopenshell.entity_instance):
            return SyncedEntity(result, model)
        if isinstance(result, (list, tuple)):
            # Preserve container type (IfcOpenShell returns tuples for some
            # aggregates, e.g. HasProperties).
            wrapped = [  # type: ignore[reportUnknownVariableType]
                SyncedEntity(item, model)
                if isinstance(item, ifcopenshell.entity_instance)
                else item
                for item in result  # type: ignore[reportUnknownVariableType]
            ]
            return type(result)(wrapped)  # type: ignore[reportUnknownArgumentType]
        return result

    def is_a(self, ifc_class: str | None = None) -> bool | str:
        """Return whether the entity is of the given IFC class (or its subclass).

        When called without arguments, returns the IFC type name as a string.
        Delegates directly to the inner entity to avoid proxy overhead.
        """
        inner: ifcopenshell.entity_instance = object.__getattribute__(self, "_inner")
        if ifc_class is None:
            return inner.is_a()  # type: ignore[return-value]
        return inner.is_a(ifc_class)  # type: ignore[return-value]


def unwrap(
    entity: ifcopenshell.entity_instance | SyncedEntity,
) -> ifcopenshell.entity_instance:
    """Return the raw ``entity_instance``, unwrapping a ``SyncedEntity`` if needed."""
    if isinstance(entity, SyncedEntity):
        return object.__getattribute__(entity, "_inner")
    return entity


class SyncedIfcModel:
    """Wraps an ``ifcopenshell.file``, emitting ``IfcMutation`` ops on every mutation.

    Args:
        model: The underlying IfcOpenShell file to wrap.
        file_id: Identifier for this file; included in every op envelope by the
            transport layer (step 7).
        on_op: Synchronous callback invoked with each emitted ``IfcMutation``.
            Tests pass ``list.append``; step 7 wraps this in envelope construction
            and WebSocket send.

    Attributes:
        parent_op_id: The op_id of the most recent acknowledged server op.
            Initialised to ``None``; step 7 updates it as ops are acknowledged
            so envelopes carry the correct causal link.
    """

    _model: ifcopenshell.file
    _file_id: str
    _on_op: Callable[[IfcMutation], None]
    _suppressed: bool
    parent_op_id: str | None

    def __init__(
        self,
        model: ifcopenshell.file,
        file_id: str,
        on_op: Callable[[IfcMutation], None],
    ) -> None:
        # SyncedIfcModel does NOT override __setattr__, so regular assignment is safe.
        self._model = model
        self._file_id = file_id
        self._on_op = on_op
        self._suppressed = False
        self.parent_op_id = None

    def _emit(self, op: IfcMutation) -> None:
        if not self._suppressed:
            self._on_op(op)

    @contextmanager
    def suppress_emission(self) -> Generator[None, None, None]:
        """Context manager that temporarily suppresses op emission.

        Use when applying incoming ops from the server to prevent re-emitting
        ops we just received. Nested calls are safe: the outer context manager
        restores its pre-entry suppression state in ``finally``.
        """
        old = self._suppressed
        self._suppressed = True
        try:
            yield
        finally:
            self._suppressed = old

    def create_entity(self, ifc_type: str, **kwargs: Any) -> SyncedEntity:
        """Create an IFC entity and emit an ``AddEntity`` op.

        For ``IfcRoot`` subclasses, ``GlobalId`` is auto-assigned if not provided
        in *kwargs*. For non-root entities, a synthetic GUID is assigned via
        ``register_non_root`` and used as the op's ``guid`` field.

        Args:
            ifc_type: IFC class name, e.g. ``"IfcWall"``.
            **kwargs: Attribute values forwarded to ``ifcopenshell.file.create_entity``.

        Returns:
            A ``SyncedEntity`` wrapping the newly created entity.
        """
        entity = self._model.create_entity(ifc_type, **kwargs)

        guid: str
        try:
            raw_guid: str | None = entity.GlobalId  # type: ignore[attr-defined]
            if raw_guid is None:
                # IfcOpenShell leaves GlobalId as None when not passed in kwargs.
                entity.GlobalId = ifcopenshell.guid.new()  # type: ignore[attr-defined]
            guid = entity.GlobalId  # type: ignore[attr-defined]
        except AttributeError:
            # Non-root entity — assign a synthetic GUID and register it.
            # Registration happens before the attributes loop so any attribute
            # that itself references a non-root entity is already registered.
            guid = register_non_root(self._model, entity)

        # Serialize non-None attributes for the AddEntity op.
        # Skip 'id' and 'type' (IfcOpenShell metadata), and 'GlobalId' (already
        # captured as guid above).
        info: dict[str, Any] = entity.get_info()  # type: ignore[assignment]
        attributes: dict[str, Any] = {}
        for key, val in info.items():
            if key in ("id", "type", "GlobalId"):
                continue
            if val is None:
                continue
            attributes[key] = serialize_value(self._model, val)

        self._emit(AddEntity(guid=guid, ifc_type=ifc_type, attributes=attributes))
        return SyncedEntity(entity, self)

    def remove(
        self,
        entity: ifcopenshell.entity_instance | SyncedEntity,
    ) -> None:
        """Remove an entity and emit a ``DeleteEntity`` op.

        The snapshot is captured before removal; the op is emitted before the
        entity is deleted from the model.

        Args:
            entity: The entity to remove (raw or wrapped).
        """
        inner = unwrap(entity)

        # Capture snapshot before removal — entity attributes may be inaccessible
        # once the entity is deleted from the model.
        snapshot = serialize_entity(self._model, inner)

        guid: str | None
        try:
            guid = inner.GlobalId  # type: ignore[attr-defined]
        except AttributeError:
            guid = get_synthetic_guid(self._model, inner)

        if guid is not None:
            self._emit(DeleteEntity(guid=guid, previous_snapshot=snapshot))

        self._model.remove(inner)

    def by_guid(self, guid: str) -> SyncedEntity | None:
        """Look up an entity by IFC GlobalId, returning a wrapped entity or ``None``.

        Args:
            guid: The IFC GlobalId to look up.

        Returns:
            A ``SyncedEntity`` if found, ``None`` if the guid is not present.
        """
        try:
            entity = self._model.by_guid(guid)
        except RuntimeError:
            return None
        return SyncedEntity(entity, self)

    def by_type(
        self,
        ifc_type: str,
        include_subtypes: bool = True,
    ) -> list[SyncedEntity]:
        """Return all entities of the given IFC type as wrapped entities.

        Args:
            ifc_type: IFC class name, e.g. ``"IfcWall"``.
            include_subtypes: Whether to include subclass instances (default ``True``).

        Returns:
            List of ``SyncedEntity`` instances.
        """
        results = self._model.by_type(ifc_type, include_subtypes)
        return [SyncedEntity(e, self) for e in results]

    def __getattr__(self, name: str) -> Any:
        """Proxy all other attribute access to the underlying model.

        Note: attributes stored in ``self.__dict__`` (``_model``, ``_suppressed``,
        ``parent_op_id``, etc.) are found before ``__getattr__`` is called and
        are NOT proxied. Only truly missing attributes reach this method.
        """
        return getattr(self._model, name)


__all__ = [
    "SyncedEntity",
    "SyncedIfcModel",
    "unwrap",
]
