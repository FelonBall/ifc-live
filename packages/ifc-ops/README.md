# ifc-ops

Pure-Python data model for IFC operations, used throughout `ifc-live`.

This package contains only Pydantic schemas — no IfcOpenShell dependency, no
I/O, no business logic. It defines the wire format that flows between client
and server.

See [`../../docs/DESIGN.md`](../../docs/DESIGN.md) section 3 for the op model
specification.
