"""Run the gateway over stdio for an MCP client such as Hermes."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

from mcp.server.stdio import stdio_server

from .config import ConfigurationError, UpstreamConfig, load_config
from .gateway import create_server


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), stream=sys.stderr)
    config_path = Path(os.environ.get("MCP_GATEWAY_CONFIG", "/config/servers.json"))
    try:
        upstreams = load_config(config_path)
    except ConfigurationError as error:
        raise SystemExit(f"Invalid MCP gateway configuration: {error}") from error
    asyncio.run(_serve(upstreams))


async def _serve(upstreams: tuple[UpstreamConfig, ...]) -> None:
    server = create_server(upstreams)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    main()
