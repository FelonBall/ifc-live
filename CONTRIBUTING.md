# Contributing to ifc-live

Thanks for your interest. The project is pre-alpha and the architecture is
still settling, but contributions are welcome.

## Before sending a PR

1. **Read [`docs/DESIGN.md`](docs/DESIGN.md)** — it captures the op model, the
   sync protocol, and the conflict rules. Most non-trivial changes touch one
   of these and need to be consistent with it.
2. **For substantial changes, open an issue first.** Describe what you want
   to change and why. This saves both of us time vs. landing a PR that needs
   rework.
3. **Stay in scope for the active milestone.** Right now that's
   [`docs/MILESTONE_1.md`](docs/MILESTONE_1.md). If your change is out of
   scope but valuable, open an issue tagged `roadmap` for later.

Small PRs — typo fixes, docs improvements, additional tests for existing code
— don't need a prior issue. Just send them.

## Local setup

```sh
git clone https://github.com/FelonBall/ifc-live.git
cd ifc-live
uv sync
```

## Code style

- **Formatting + linting:** `ruff` — `uv run ruff check` and `uv run ruff format`
- **Type checking:** `pyright --strict` — `uv run pyright`
- **Tests:** `pytest` — `uv run pytest`

All three run in CI on every PR. PRs that don't pass don't merge.

Type hints are required on every public function and method. Internal helpers
should still be typed unless the cost is clearly disproportionate.

## Commits

We follow a relaxed version of Conventional Commits. Reasonable prefixes:

- `feat:` — new functionality
- `fix:` — bug fix
- `docs:` — documentation only
- `test:` — adding or fixing tests
- `refactor:` — code change with no behaviour change
- `chore:` — tooling, CI, dependency bumps

The body should describe **why**, not what (the diff already says what).
Reference issues with `Refs #123` or `Closes #123`.

## PR checklist

- [ ] Tests added or updated for the change
- [ ] `uv run ruff check` passes
- [ ] `uv run pyright` passes
- [ ] `uv run pytest` passes
- [ ] Docs updated if behaviour or API changed
- [ ] PR description explains the motivation and any trade-offs

## License

By contributing, you agree that your contributions are licensed under the
[Apache License 2.0](LICENSE) (the project's license). You retain copyright
of your contributions; the license is granted to the project and its users.
