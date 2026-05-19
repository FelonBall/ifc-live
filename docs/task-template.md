# Task prompt template

This file is the template the user follows when giving Claude Code a
milestone task. Claude Code should expect prompts to follow this shape
and, if a prompt is less structured than this, mentally expand it to
match the template before starting work.

The template is reproduced below in two forms: an annotated version that
explains each section, and a blank version the user can copy and fill in.

---

## Annotated template

```
TASK: Milestone <M> Step <N> — <short name>

CONTEXT TO READ FIRST (in this order):
1. CLAUDE.md (especially "Before you finish any task — the design-doc
   check" and "Definition of done")
2. docs/DESIGN.md sections <X>, <Y>, <Z>
3. docs/MILESTONE_<M>.md step <N>
4. The package(s) being modified: <package paths>
5. <Any prior code Claude Code should read for context — e.g. "the
   ifc-ops package" if implementing something downstream of it>

SCOPE:
- Implement <specific deliverable, 1-3 sentences>
- Modify ONLY these files / directories: <list>
- Do NOT modify: <list of related things that are tempting but out of
  scope — e.g. "do not touch any other package"; "do not change
  PROTOCOL.md beyond updating the field schema if needed">

DESIGN-DOC IMPACT:
- This work is expected to introduce design decisions in these areas:
  <bulleted list, e.g. "value type mapping", "GUID resolution for
  non-root entities", "error handling strategy">
- For each design decision actually made, update DESIGN.md section <X>
  (or whichever section is most relevant) in the same task as the
  implementation
- If you make a design decision in an area NOT listed above, stop and
  flag it to the user before continuing — the design space may be
  larger than I anticipated

ACCEPTANCE:
- uv run check passes
- Test suite covers: <specific cases, behaviours, edge cases>
- Definition-of-done checklist in CLAUDE.md is satisfied
- DESIGN.md reflects every design decision per the criteria in CLAUDE.md

BEFORE DECLARING DONE:
- Walk through the Definition of Done checklist in CLAUDE.md explicitly
- Provide the "Design decisions made in this task" report per the
  format in CLAUDE.md
- Run `uv run check` and report the result (pass/fail; if fail, what
  failed)

If at any point you find the scope is unclear or the design space is
larger than I described, stop and ask the user rather than guessing.
```

---

## Section guide

### `TASK` line

Short, identifies the milestone and step. Lets Claude Code anchor on
the right section of `MILESTONE_*.md` immediately.

### `CONTEXT TO READ FIRST`

An ordered list, not a bag. Claude Code reads in order. Starting with
`CLAUDE.md` reinforces the design-doc rule on every session. Then the
relevant design sections (so Claude knows *what* is being built),
then the milestone step (so Claude knows *the deliverable*), then the
code (so Claude knows *the current state*).

Limit to ~5 items. Reading 15 files before starting work is
counterproductive.

### `SCOPE`

Three parts: what to do, what files are in bounds, what files are
explicitly out of bounds. The third part is the most important and
the most often skipped. Scope creep is the #1 failure mode of agentic
coding — telling Claude Code "don't touch X, Y, Z" up front prevents
it from "helpfully" refactoring something adjacent.

If you don't know what's out of bounds, ask yourself "what would I be
annoyed to see changed in the diff?" That's the out-of-bounds list.

### `DESIGN-DOC IMPACT`

This is the lever for the design-doc enforcement problem. Two
purposes:

1. **Priming.** Telling Claude Code in advance "you will probably
   make design decisions in these areas" makes it watch for them
   actively rather than recognizing them in hindsight.
2. **Trip-wire for unanticipated design.** "If you make a decision
   not in this list, stop and flag it" creates a checkpoint. Without
   it, Claude Code will quietly make unanticipated design choices and
   not document them.

If you genuinely think no design decisions will be made (e.g. a pure
bug fix), write that explicitly: `DESIGN-DOC IMPACT: None expected.
If you make any design decision, stop and flag it.`

### `ACCEPTANCE`

What "done" looks like, objectively. Reference the Definition of
Done in `CLAUDE.md` so it's not redundantly listed, but call out
test-specific cases here.

### `BEFORE DECLARING DONE`

Forces an explicit accounting step at the end. The
"Design decisions made in this task" report is the part that does
the real work — without it, Claude Code can quietly skip design-doc
updates. With it, the omission becomes visible.

---

## Blank template (copy-paste this)

```
TASK: Milestone <M> Step <N> — <name>

CONTEXT TO READ FIRST (in this order):
1. CLAUDE.md
2. docs/DESIGN.md sections <X>, <Y>
3. docs/MILESTONE_<M>.md step <N>
4. <package being modified>
5. <prerequisite code, if any>

SCOPE:
- Implement <deliverable>
- Modify ONLY: <files/dirs>
- Do NOT modify: <out-of-scope files/dirs>

DESIGN-DOC IMPACT:
- Expected design decisions: <areas, or "None expected">
- Update DESIGN.md section <X> for each decision made
- If you make a decision outside the expected areas, stop and flag it

ACCEPTANCE:
- uv run check passes
- Tests cover: <list>
- Definition-of-done checklist satisfied
- DESIGN.md reflects every design decision

BEFORE DECLARING DONE:
- Walk through the Definition of Done explicitly
- Provide the "Design decisions made in this task" report
- Run uv run check and report the result
```

---

## When to deviate from the template

The template is the default, not a straitjacket.

- **Pure bug fixes:** use the template but write
  `DESIGN-DOC IMPACT: None expected` and shorten `CONTEXT TO READ
  FIRST` to just the relevant file.
- **Tiny tweaks** (rename a function, fix a typo, add one test): a
  one-line prompt is fine. The overhead of a full template exceeds
  the risk of misunderstanding.
- **Exploratory work** ("what would it take to add X?"): use a
  different kind of prompt — ask Claude Code to *propose* an
  approach without implementing yet. Template is for execution, not
  exploration.

Everything else uses the template.
