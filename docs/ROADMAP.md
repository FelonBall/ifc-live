# Roadmap

The roadmap below sketches what's after v1. Everything past M1 is provisional
and will be re-scoped based on what we learn.

## v0.1 — Milestone 1 (current target)

**Two Bonsai instances on localhost, live sync.**

- In-memory op log on the server
- Walls, slabs, doors, windows
- LWW conflict resolution with audit log
- Bonsai BIM addon, no other editors

Full specification in [`MILESTONE_1.md`](MILESTONE_1.md).

## v0.2 — Persistence and Authentication

The shortest path from "works on one machine" to "works across the internet".

- SQLite-backed op log (server restart is non-destructive)
- User accounts and per-file permissions
- Server can bind non-localhost, deploy on a remote machine
- TLS for the WebSocket connection
- Basic admin UI for inspecting files and the op log

## v0.3 — Broader IFC Coverage and a Second Editor

Make the system useful for real (small) projects.

- Full IFC4 entity coverage in the op model (not just the four building elements)
- FreeCAD addon as a second editor — proves the system isn't Bonsai-specific
- Robust handling of orphaned references (e.g. door whose host wall is deleted)
- Better op batching for high-frequency operations

## v0.4 — Snapshots and Version History

Make it possible to look backward.

- Tagged snapshots: "save this state as Revision P01"
- Browse history of a file as a timeline
- Restore a previous snapshot (creates a new commit, doesn't destroy newer ops)
- Diff between any two snapshots, rendered as a list of entity-level changes

## v0.5 — Better Conflict UX

So far conflicts are handled silently with LWW + audit log. v0.5 surfaces them.

- Inline conflict notification in the Blender viewport
- Quick "restore my version" action from the notification
- Per-attribute conflict policy (LWW vs. require-resolution vs. always-mine)

## v1.0 — CDE Workflow

Bring the system in line with ISO 19650.

- WIP / Shared / Published / Archived state machine per file
- Approval workflows for state transitions
- Suitability codes (S0–S7, CR, D1–D2)
- Audit trail suitable for contractual handoff
- Web UI for the CDE dashboard (not for editing — editing stays in editors)

## Beyond v1.0

The things we want eventually but won't commit to until we see the shape of
real usage:

- **AI assistant layer** — talk to the model, ask it questions, prompt
  parametric changes. The op model is a natural tool-use surface for an LLM.
- **Federated discipline models** — architecture, structure, MEP as separate
  files with cross-file references and per-discipline ownership
- **Clash detection** — geometric intersection between federated models,
  surfaced in the CDE
- **Web-based viewer** — read-only at first, eventually with basic editing
- **Additional editors** — Vectorworks, ArchiCAD (via IFC export hooks),
  potentially Revit (huge effort, separate discussion)
- **Property set schemas / IDS** — Information Delivery Specifications for
  validating models against project requirements

## What we're explicitly **not** planning

- A new IFC editor
- Replacing Bonsai or FreeCAD
- Hosting as a commercial SaaS (the project is open source; commercial
  hosting may emerge from the community but isn't a project goal)
- Supporting closed/proprietary BIM formats natively (we go through IFC)
