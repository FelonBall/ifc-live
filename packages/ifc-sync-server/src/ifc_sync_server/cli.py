"""Command-line entry point for the ifc-sync-server.

Invoked as ``ifc-sync-server`` (declared in pyproject.toml).
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``ifc-sync-server`` console script."""
    parser = argparse.ArgumentParser(
        prog="ifc-sync-server",
        description="WebSocket relay for ifc-live real-time IFC collaboration",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind (default: 127.0.0.1, localhost only)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port to bind (default: 8765)",
    )
    args = parser.parse_args(argv)

    # TODO(M1 step 3): launch the FastAPI app via uvicorn.
    #   from ifc_sync_server.app import create_app
    #   uvicorn.run(create_app(), host=args.host, port=args.port)
    print(
        f"ifc-sync-server is not implemented yet.\n"
        f"Planned: would bind ws://{args.host}:{args.port}/sync/<file_id>\n"
        f"See docs/MILESTONE_1.md step 3.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
