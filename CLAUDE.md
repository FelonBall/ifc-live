# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
- **[`docs/task-template.md`](docs/task-template.md)** — the template the user
  will follow when giving you milestone tasks. Read it once at the start of
  every session so you know what to expect.

## Repository shape

```
packages/
  ifc-ops/            Pydantic data model for IfcOps. Pure types, no IFC dep.
  ifc-sync-core/      SyncedIfcModel + op application. Depends on ifcopenshell.
  ifc-sync-server/    FastAPI WebSocket relay. Depends on ifc-ops.
  ifc-sync-bonsai/    Blender addon. Depends on ifc-sync-core.
tools/                Dev tooling. Contains the `check` console script.
```

Each package has `src/<name>/`, `tests/`, and its own `pyproject.toml`. The
workspace root `pyproject.toml` declares them as members and holds tool
configuration (`ruff`, `pyright`, `pytest`).

---

## ⚠ Before you finish any task — the design-doc check

This is the single most important rule in this file. It is the rule most
likely to be skipped under task-focus pressure. Read it carefully, every
session.

**Before reporting that a task is done, classify every decision you made
during the task.** A decision counts as a *design decision* (must go in
`docs/DESIGN.md`) if any of these are true:

- It introduces a new component, module, registry, protocol, or
  cross-package convention that other components rely on
- It chooses one of several plausible approaches where the choice
  affects future work (e.g. type mappings, lifecycle assumptions,
  naming conventions for synthetic identifiers, data format choices)
- It adds a constraint or invariant that callers must respect
- It resolves something previously listed as a "known unknown" or
  open question in `MILESTONE_1.md` or `DESIGN.md`
- It changes the meaning of an existing concept in `DESIGN.md` (even
  subtly — "Y now also means Z" counts)

A decision does **not** need to go in `DESIGN.md` if it is:

- A purely internal implementation detail with no external surface
  (private function names, local variable choices, inline algorithm
  choices that don't change behaviour)
- A test pattern or fixture that doesn't constrain production code
- A bug fix that restores intended behaviour rather than defining new
  behaviour

If you made any decisions of the first kind, **update `DESIGN.md` in the
same commit (or PR, or task) as the implementation**. The design doc is
the contract; code is the realization. A code change without the
corresponding doc change is a contract violation if the change introduces
design.

When in doubt, **update the doc**. A short doc note is cheaper than the
confusion of a future contributor (or future you) reading the code and
wondering whether a choice was deliberate.

### How to update `DESIGN.md`

- Find the section closest in topic to the decision. Most changes
  belong in section 3 (op model), 4 (sync protocol), 5 (conflicts), 6
  (interception), or 7 (server). If nothing fits, add a new subsection
  to the closest section rather than tacking onto the end.
- Match the style and tone of the existing doc — concise, predicate
  form, examples in fenced code blocks
- Include rationale, not just statement of fact. "X is done because Y"
  is better than "X is done."
- If the decision conflicts with what `DESIGN.md` previously said,
  rewrite the old text — don't append. The doc must read consistently
  end-to-end.

---

## Definition of done — apply to every task

A task is not done until **all** of the following are true. Walk
through this checklist explicitly before declaring completion; do not
rely on memory.

- [ ] `uv run check` passes end-to-end
- [ ] Tests added or updated for the change; new branches covered
- [ ] `DESIGN.md` updated for every design decision per the criteria
      above
- [ ] `PROTOCOL.md` updated if the wire format changed
- [ ] Public functions have docstrings explaining purpose, parameters,
      return values, and any constraints
- [ ] No new bare `except Exception:` — failures must be loud and
      specific. If you catch broadly, log or re-raise with context.
- [ ] No silent fallbacks that swallow data — invalid inputs raise
      explicit errors rather than returning defaults
- [ ] No new `Any` type annotations on parameters or returns of public
      functions; use concrete types (with `# type: ignore[...]` only
      when a third-party library genuinely lacks stubs)
- [ ] No code committed that you would object to in a code review

When you report task completion to the user, **list the design
decisions you made and where in `DESIGN.md` you documented them**.
This forces explicit accounting and surfaces gaps. The format:

```
Design decisions made in this task:

1. <one-sentence description>
   Documented in: docs/DESIGN.md §<section number/name>

2. <one-sentence description>
   Documented in: docs/DESIGN.md §<section number/name>

(or)

No design decisions were made in this task — pure implementation of
existing design.
```

If you cannot honestly write either of the above, the task is not
done.

---

## Working agreements

1. **Stay in M1 scope.** If a task drifts into things from
   [`docs/ROADMAP.md`](docs/ROADMAP.md) (auth, persistence, snapshots,
   FreeCAD, etc.), stop and check with the user. We deliberately
   deferred those.

2. **The op model is load-bearing.** Changes to `ifc-ops` ripple
   through every other package. Be deliberate about them and write
   tests that pin down the wire format.

3. **Tests pin behaviour, not implementation.** Test that conflict
   resolution produces the right outcome, not that it calls a
   particular internal function.

4. **Type annotations on every public function.** `pyright --strict`
   runs in CI. Use `from __future__ import annotations` at the top of
   new modules.

5. **`ruff format` is authoritative.** Don't hand-format.

6. **Run `uv run check` before declaring a task done.** It's the
   canonical local CI suite — same commands as
   `.github/workflows/ci.yml` in the same order. If it passes locally,
   CI almost always passes on push. Use `uv run check --fast` for
   quick feedback during dev and the full `uv run check` before
   committing.

7. **Commit messages follow [`CONTRIBUTING.md`](CONTRIBUTING.md).**
   Conventional prefixes (`feat:`, `fix:`, `docs:`, `test:`,
   `refactor:`, `chore:`).

8. **If you find yourself uncertain about scope or design, stop and
   ask the user.** The user has context you don't. Asking takes a
   minute; building the wrong thing wastes hours.

## Commands

```sh
uv sync                                    # install everything (creates .venv)
uv run check                               # full local CI suite (canonical)
uv run check --fast                        # quick: skip slow tests, no coverage
uv run check --skip-tests                  # just lint + typecheck
uv run ruff check                          # lint only
uv run ruff format                         # apply formatter (writes changes)
uv run pyright                             # type check (strict)
uv run pytest                              # all tests
uv run pytest -k <expr>                    # subset by name/expression
uv run pytest packages/ifc-sync-core/      # single package
uv run pytest -m "not requires_bonsai"     # skip Blender-dependent tests
uv run ifc-sync-server                     # start the server (once implemented)
```

Prefer `uv run check` over running tools individually unless you need
something finer-grained.

## Current implementation status

Steps 1 and 2 of Milestone 1 are complete:

- **Step 1 — `ifc-ops`**: Pydantic models for `IfcOpEnvelope`, all
  `IfcMutation` variants, and the `IfcValue` union. Wire format is
  stable; don't change it without updating `docs/PROTOCOL.md` too.

- **Step 2 — `ifc-sync-core` op application**: `apply_op()`,
  `serialize_value()`, `deserialize_value()`, `serialize_entity()`, and
  `register_non_root()` are implemented and exported from
  `packages/ifc-sync-core/src/ifc_sync_core/`.

Continue with Step 3 (`ifc-sync-server` minimal relay) unless the user
says otherwise. See [`docs/MILESTONE_1.md`](docs/MILESTONE_1.md) for
the full ordered list.

### Key architectural pattern: non-root entity identity

`IfcLocalPlacement`, `IfcDirection`, profile definitions, and other
IFC entities that don't inherit `IfcRoot` have no `GlobalId`. The op
model is GUID-addressed, so `serialize.py` maintains a per-model
registry (`WeakKeyDictionary`) mapping STEP entity IDs ↔ synthetic
GUIDs. Callers must call `register_non_root()` before serializing such
entities; `apply_op()` does this automatically when applying an
`AddEntity` op for a non-root type. See `DESIGN.md §3 "Non-root entity
identity"` for the full rationale and lifecycle constraints.

## Things to investigate before implementation step 4

[`docs/MILESTONE_1.md`](docs/MILESTONE_1.md) lists four "known
unknowns" that should be spiked before the integration step. If you
find yourself blocked on any of them, surface that to the user rather
than guessing.
