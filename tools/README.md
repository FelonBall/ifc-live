# ifc-live-dev

Internal dev tooling for the `ifc-live` workspace.

This is not a published package and not part of the runtime product — it
exists so contributors get a single command for the local CI suite:

```sh
uv run check                  # full suite (lint + typecheck + tests)
uv run check --fast           # quick feedback, skips slow tests
uv run check --skip-tests     # just lint + typecheck
```

The `check` script runs exactly the same commands as
[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) in the same order,
so passing `check` locally is a strong signal that CI will pass on push.
