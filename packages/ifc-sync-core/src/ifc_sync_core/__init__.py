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

from ifc_sync_core.apply import apply_op as apply_op
from ifc_sync_core.serialize import (
    deserialize_value as deserialize_value,
)
from ifc_sync_core.serialize import (
    serialize_entity as serialize_entity,
)
from ifc_sync_core.serialize import (
    serialize_value as serialize_value,
)

# SyncedIfcModel and SyncedEntity are implemented in M1 step 4.

__all__ = [
    "apply_op",
    "deserialize_value",
    "serialize_entity",
    "serialize_value",
]
