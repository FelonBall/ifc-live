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

# Step 2 — op application and serialization
from ifc_sync_core.apply import apply_op
from ifc_sync_core.serialize import (
    deserialize_value,
    get_synthetic_guid,
    register_non_root,
    serialize_entity,
    serialize_value,
)

# Step 4 — interception wrappers
from ifc_sync_core.synced_model import SyncedEntity, SyncedIfcModel, unwrap

__all__ = [
    "SyncedEntity",
    "SyncedIfcModel",
    "apply_op",
    "deserialize_value",
    "get_synthetic_guid",
    "register_non_root",
    "serialize_entity",
    "serialize_value",
    "unwrap",
]
