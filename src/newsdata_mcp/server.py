import sys
import argparse
import logging

from . import client
from .app import mcp

logging.basicConfig(level=logging.INFO, stream=sys.stderr)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    parser.add_argument("--host", default=mcp.settings.host)
    parser.add_argument("--port", type=int, default=mcp.settings.port)
    args = parser.parse_args()
    
    if args.transport == "streamable-http":
        mcp.settings.host = args.host
        mcp.settings.port = args.port
    
    mcp.run(transport=args.transport)

if __name__ == "__main__":
    main()
