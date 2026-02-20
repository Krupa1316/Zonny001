"""
zonny-server  entry point
-------------------------
Starts the Zonny FastAPI REST server.

Usage (after pip install -e .):
    zonny-server
    zonny-server --host 0.0.0.0 --port 8000 --reload
"""

import sys
import uvicorn


def start():
    """Launch uvicorn with server:app.  Forwards any CLI flags."""
    import argparse

    parser = argparse.ArgumentParser(description="Zonny REST server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (dev mode)")
    args = parser.parse_args()

    uvicorn.run(
        "server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    start()
