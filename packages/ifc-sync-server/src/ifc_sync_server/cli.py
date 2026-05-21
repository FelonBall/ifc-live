"""Command-line entry point for the ifc-sync-server.

Invoked as ``ifc-sync-server`` (declared in pyproject.toml).
"""

from __future__ import annotations

import argparse

import uvicorn

from ifc_sync_server.app import create_app


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``ifc-sync-server`` console script.

    Args:
        argv: Argument list to parse. Uses ``sys.argv[1:]`` when ``None``.

    Returns:
        Exit code (always ``0`` — uvicorn blocks until interrupted).
    """
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

    app = create_app(host=args.host, port=args.port)
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
