"""ifc-sync-core — IfcOpenShell-aware sync logic for ifc-live.

This package contains the parts of ifc-live that interact directly with
IfcOpenShell: the ``SyncedIfcModel`` wrapper that intercepts mutations, the
op application logic that turns an ``IfcOp`` back into IfcOpenShell calls,
and the serialization helpers that convert between IFC values and the wire
format defined in ``ifc-ops``.

See ``docs/DESIGN.md`` section 6 (interception strategy) and ``docs/MILESTONE_1.md``
steps 2 and 4 for the work items.
"""

__version__ = "0.1.0"

# Public API to be populated as Milestone 1 progresses.
# Expected exports:
#   SyncedIfcModel
#   SyncedEntity
#   apply_op(model, op)              # M1 step 2
#   serialize_entity(entity)         # M1 step 2
#   serialize_value(value)           # M1 step 2
#   deserialize_value(value)         # M1 step 2

__all__: list[str] = []
