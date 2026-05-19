# Cross-package integration tests

Tests in this directory exercise multiple packages together — e.g. a server
process plus a `SyncedIfcModel` client, verifying end-to-end op flow.

Package-internal unit tests live in each package's own `tests/` directory.

See [`../docs/MILESTONE_1.md`](../docs/MILESTONE_1.md) for the integration
test scope at M1.
