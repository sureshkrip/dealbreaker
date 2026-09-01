"""Command-line entry point: `dealbreaker serve|seed`."""

from __future__ import annotations

import sys


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "serve"

    if cmd == "seed":
        from .seed import run

        run()
    elif cmd == "serve":
        import uvicorn

        host = "0.0.0.0"  # noqa: S104 — intended to be reachable in a container
        port = 8000
        uvicorn.run("dealbreaker.main:app", host=host, port=port, reload=False)
    else:
        print(f"Unknown command: {cmd!r}. Use 'serve' or 'seed'.")
        raise SystemExit(2)
