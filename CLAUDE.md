# Context for Claude Code

This file is loaded at the start of every Claude Code session in this repo.
Read it first, then read whatever else you need.

## What this project is

`ifc-live` is a real-time synchronization service for IFC models, modeled on
how Google Docs syncs character-level edits — but for IFC entity mutations
instead of text. Two users editing the same IFC model in Bonsai BIM see each
other's changes propagated live, with no manual save / push / pull step.

## Where to find authoritative information

- **[`README.md`](README.md)** — high-level overview, install/run instructions
- **[`docs/DESIGN.md`](docs/DESIGN.md)** — the architecture, op model, conflict
  rules, and component design. This is the source of truth for *what* the
  system is. Always consult before making non-trivial design decisions.
- **[`docs/MILESTONE_1.md`](docs/MILESTONE_1.md)** — the current milestone:
  scope, acceptance criteria, demo script, implementation order. This is the
  source of truth for *what to build next*.
- **[`docs/PROTOCOL.md`](docs/PROTOCOL.md)** — wire format for WebSocket
  messages
- **[`docs/ROADMAP.md`](docs/ROADMAP.md)** — what comes after v1 (not active
  scope)

## Repository shape

```
packages/
  ifc-ops/            Pydantic data model for IfcOps. Pure types, no IFC dep.
  ifc-sync-core/      SyncedIfcModel + op application. Depends on ifcopenshell.
  ifc-sync-server/    FastAPI WebSocket relay. Depends on ifc-ops.
  ifc-sync-bonsai/    Blender addon. Depends on ifc-sync-core.
```

Each package has `src/<name>/`, `tests/`, and its own `pyproject.toml`. The
workspace root `pyproject.toml` declares them as members and holds tool
configuration (`ruff`, `pyright`, `pytest`).

## Working agreements

1. **Stay in M1 scope.** If a task drifts into things from
   [`docs/ROADMAP.md`](docs/ROADMAP.md) (auth, persistence, snapshots, FreeCAD,
   etc.), stop and check with the user. We deliberately deferred those.

2. **Update `DESIGN.md` when design changes.** Implementation detail can live
   in code; cross-cutting design decisions must be in the design doc so the
   whole project stays consistent.

3. **The op model is load-bearing.** Changes to `ifc-ops` ripple through
   every other package. Be deliberate about them and write tests that pin
   down the wire format.

4. **Tests pin behaviour, not implementation.** Test that conflict resolution
   produces the right outcome, not that it calls a particular internal
   function.

5. **Type annotations on every public function.** `pyright --strict` runs in
   CI. Use type-hint `from __future__ import annotations` at the top of new
   modules.

6. **`ruff format` is authoritative.** Don't hand-format.

7. **Commit messages follow [`CONTRIBUTING.md`](CONTRIBUTING.md).** Conventional
   prefixes (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`).

## Commands

```sh
uv sync                           # install everything
uv run ruff check                 # lint
uv run ruff format                # format
uv run pyright                    # type check (strict)
uv run pytest                     # all tests
uv run pytest -k <expr>           # subset by name
uv run pytest -m "not requires_bonsai"  # skip Blender-dependent tests
uv run ifc-sync-server            # start the server (once implemented)
```

## Current implementation status

Everything is a stub. The scaffold builds, the smoke tests pass, but no real
functionality exists yet. The first eight implementation steps are listed in
[`docs/MILESTONE_1.md`](docs/MILESTONE_1.md). Start with step 1 (the `ifc-ops`
data model) unless the user says otherwise.

## Things to investigate before implementation step 4

[`docs/MILESTONE_1.md`](docs/MILESTONE_1.md) lists four "known unknowns" that
should be spiked before the integration step. If you find yourself blocked
on any of them, surface that to the user rather than guessing.
