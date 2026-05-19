"""Run the full local CI suite — the same checks as .github/workflows/ci.yml.

Invoke via the console script::

    uv run check                  # full suite (lint + typecheck + tests)
    uv run check --fast           # quick: skip slow/bonsai tests, no coverage
    uv run check --skip-tests     # just lint + typecheck
    uv run check --skip-lint --skip-typecheck   # just tests

Exits 0 if every step passes, 1 if any step fails. Failed steps are listed
together at the end so a single run surfaces every problem instead of stopping
at the first failure.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time

# ANSI colors. Disabled automatically if stdout is not a TTY.
_USE_COLOR = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    if not _USE_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


def _bold(text: str) -> str:
    return _c("1", text)


def _green(text: str) -> str:
    return _c("1;32", text)


def _red(text: str) -> str:
    return _c("1;31", text)


def _blue(text: str) -> str:
    return _c("1;34", text)


def _yellow(text: str) -> str:
    return _c("1;33", text)


def _run_step(name: str, cmd: list[str]) -> tuple[bool, float]:
    """Run one CI step. Returns (passed, elapsed_seconds)."""
    print(f"\n{_blue('▶')} {_bold(name)}")
    print(f"  $ {' '.join(cmd)}")
    start = time.perf_counter()
    rc = subprocess.call(cmd)
    elapsed = time.perf_counter() - start
    status = _green("PASS") if rc == 0 else _red("FAIL")
    print(f"  {status}  ({elapsed:.1f}s)")
    return rc == 0, elapsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check",
        description="Run the local CI suite (matches .github/workflows/ci.yml).",
    )
    parser.add_argument(
        "--skip-lint",
        action="store_true",
        help="Skip ruff check and ruff format --check",
    )
    parser.add_argument(
        "--skip-typecheck",
        action="store_true",
        help="Skip pyright",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip pytest",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help=(
            "Quick feedback mode: skip tests marked 'slow' or 'requires_bonsai', "
            "drop coverage reporting, run pytest in quiet mode."
        ),
    )
    args = parser.parse_args(argv)

    if shutil.which("uv") is None:
        print(
            _red("error: `uv` not found on PATH."),
            "Install uv from https://docs.astral.sh/uv/ then re-run.",
            file=sys.stderr,
        )
        return 2

    # Build the step list in the same order CI runs them.
    steps: list[tuple[str, list[str]]] = []

    if not args.skip_lint:
        steps.append(("ruff check", ["uv", "run", "ruff", "check"]))
        steps.append(("ruff format --check", ["uv", "run", "ruff", "format", "--check"]))

    if not args.skip_typecheck:
        steps.append(("pyright", ["uv", "run", "pyright"]))

    if not args.skip_tests:
        if args.fast:
            test_cmd = [
                "uv",
                "run",
                "pytest",
                "-q",
                "-m",
                "not requires_bonsai and not slow",
            ]
        else:
            test_cmd = [
                "uv",
                "run",
                "pytest",
                "-v",
                "--cov",
                "--cov-report=term-missing",
                "-m",
                "not requires_bonsai",
            ]
        steps.append(("pytest", test_cmd))

    if not steps:
        print(_yellow("All steps skipped — nothing to do."))
        return 0

    results: list[tuple[str, bool, float]] = []
    suite_start = time.perf_counter()
    for name, cmd in steps:
        passed, elapsed = _run_step(name, cmd)
        results.append((name, passed, elapsed))
    suite_elapsed = time.perf_counter() - suite_start

    # Summary
    print()
    print("=" * 60)
    print(_bold("Summary"))
    print("-" * 60)
    for name, passed, elapsed in results:
        marker = _green("✓") if passed else _red("✗")
        print(f"  {marker}  {name:<24}  {elapsed:>5.1f}s")
    print("-" * 60)
    print(f"  Total: {suite_elapsed:.1f}s")
    print()

    failures = [name for name, passed, _ in results if not passed]
    if failures:
        print(_red(f"✗ {len(failures)} step(s) failed: {', '.join(failures)}"))
        return 1
    print(_green("✓ All checks passed."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
