"""IfcOp data model — Pydantic schemas for all IFC mutations.

This package is the foundation of ifc-live. It defines the closed set of
operations that can mutate an IFC model, along with the envelope that wraps
each op as it flows through the system.

The package has no dependencies on IfcOpenShell or any other IFC library —
it is pure data types so it can be imported anywhere (client, server, test
fixtures) without pulling in heavy native dependencies.

See ``docs/DESIGN.md`` section 3 for the full op model specification.

Implementation status: stub. See ``docs/MILESTONE_1.md`` step 1 for the
work items needed to make this module functional.
"""

__version__ = "0.1.0"

# Public API will be populated as Milestone 1 step 1 progresses.
# Expected exports:
#   IfcOpEnvelope
#   AddEntity, DeleteEntity, ModifyAttribute, SetPropertyValue
#   IfcValue (and the variants: IfcString, IfcInt, IfcFloat, IfcBool,
#     IfcEnum, IfcRef, IfcList, IfcNull)
#   SCHEMA_VERSION

SCHEMA_VERSION = "1"

__all__ = ["SCHEMA_VERSION"]
