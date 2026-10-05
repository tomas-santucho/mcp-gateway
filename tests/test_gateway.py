from __future__ import annotations

import sys
from pathlib import Path
from typing import cast

import pytest
from mcp import types
from mcp.server import ServerRequestContext

from mcp_gateway.config import UpstreamConfig
from mcp_gateway.gateway import Gateway


@pytest.mark.asyncio
async def test_gateway_namespaces_and_forwards_upstream_tools(tmp_path: Path) -> None:
    adapter = tmp_path / "adapter.py"
    adapter.write_text(
        """
import asyncio
from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

server = Server("adapter")

async def list_tools(_context, _params):
    return types.ListToolsResult(tools=[types.Tool(name="echo", inputSchema={"type": "object"})])

async def call_tool(_context, params):
    content = [types.TextContent(type="text", text=params.arguments["value"])]
    return types.CallToolResult(content=content)

server = Server("adapter", on_list_tools=list_tools, on_call_tool=call_tool)

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

asyncio.run(main())
""",
        encoding="utf-8",
    )
    upstream = UpstreamConfig(
        name="example",
        command=sys.executable,
        args=(str(adapter),),
        env={},
        required=True,
    )

    async with Gateway((upstream,)) as gateway:
        tools = await gateway.list_tools(cast(ServerRequestContext[Gateway], None), None)
        result = await gateway.call_tool(
            cast(ServerRequestContext[Gateway], None),
            types.CallToolRequestParams(name="example__echo", arguments={"value": "forwarded"}),
        )

    assert [tool.name for tool in tools.tools] == ["example__echo"]
    assert result.is_error is False
    assert result.content[0].text == "forwarded"
