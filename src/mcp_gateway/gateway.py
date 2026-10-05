"""MCP protocol gateway that exposes a namespaced union of stdio upstreams."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from mcp.server import Server, ServerRequestContext

from .config import UpstreamConfig


class GatewayError(RuntimeError):
    """Raised when an upstream cannot safely be represented by the gateway."""


@dataclass(frozen=True)
class RoutedTool:
    """A public gateway name and its corresponding upstream tool."""

    server_name: str
    upstream_name: str
    session: ClientSession
    tool: types.Tool


class Gateway:
    """Connect to configured upstreams once and route only advertised tools."""

    def __init__(self, upstreams: tuple[UpstreamConfig, ...]) -> None:
        self._upstreams = upstreams
        self._stack = AsyncExitStack()
        self._tools: dict[str, RoutedTool] = {}

    async def __aenter__(self) -> Gateway:
        try:
            for upstream in self._upstreams:
                await self._connect(upstream)
        except BaseException:
            await self._stack.aclose()
            raise
        return self

    async def __aexit__(self, *args: object) -> None:
        await self._stack.aclose()

    async def _connect(self, upstream: UpstreamConfig) -> None:
        connection = AsyncExitStack()
        try:
            parameters = StdioServerParameters(
                command=upstream.command,
                args=list(upstream.args),
                env=upstream.resolved_environment(),
            )
            read_stream, write_stream = await connection.enter_async_context(
                stdio_client(parameters)
            )
            session = await connection.enter_async_context(ClientSession(read_stream, write_stream))
            await session.initialize()
            tools = (await session.list_tools()).tools
            self._register_tools(upstream.name, session, tools)
        except Exception as error:
            await connection.aclose()
            if upstream.required:
                message = f"Unable to initialize required MCP server '{upstream.name}'"
                raise GatewayError(message) from error
        else:
            self._stack.push_async_callback(connection.aclose)

    def _register_tools(
        self, server_name: str, session: ClientSession, tools: list[types.Tool]
    ) -> None:
        for tool in tools:
            public_name = f"{server_name}__{tool.name}"
            if public_name in self._tools:
                raise GatewayError(f"Duplicate gateway tool name: {public_name}")
            public_tool = tool.model_copy(update={"name": public_name})
            self._tools[public_name] = RoutedTool(
                server_name=server_name,
                upstream_name=tool.name,
                session=session,
                tool=public_tool,
            )

    async def list_tools(
        self,
        _context: ServerRequestContext[Gateway],
        _params: types.PaginatedRequestParams | None,
    ) -> types.ListToolsResult:
        return types.ListToolsResult(tools=[route.tool for route in self._tools.values()])

    async def call_tool(
        self, _context: ServerRequestContext[Gateway], params: types.CallToolRequestParams
    ) -> types.CallToolResult:
        route = self._tools.get(params.name)
        if route is None:
            return types.CallToolResult(
                is_error=True,
                content=[
                    types.TextContent(type="text", text=f"Unknown gateway tool: {params.name}")
                ],
            )
        return await route.session.call_tool(route.upstream_name, params.arguments or {})


def create_server(upstreams: tuple[UpstreamConfig, ...]) -> Server[Gateway]:
    """Create an MCP server that becomes ready only after its upstreams connect."""

    @asynccontextmanager
    async def lifespan(_: Server[Gateway]) -> AsyncIterator[Gateway]:
        async with Gateway(upstreams) as gateway:
            yield gateway

    async def list_tools(
        context: ServerRequestContext[Gateway], params: types.PaginatedRequestParams | None
    ) -> types.ListToolsResult:
        gateway = context.lifespan_context
        return await gateway.list_tools(context, params)

    async def call_tool(
        context: ServerRequestContext[Gateway], params: types.CallToolRequestParams
    ) -> types.CallToolResult:
        gateway = context.lifespan_context
        return await gateway.call_tool(context, params)

    return Server(
        "mcp-gateway",
        version="0.1.3",
        instructions="Namespaced tools are proxied to configured downstream MCP servers.",
        lifespan=lifespan,
        on_list_tools=list_tools,
        on_call_tool=call_tool,
    )
