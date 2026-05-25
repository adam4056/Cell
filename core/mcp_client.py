"""
MCP (Model Context Protocol) client.
Connects to MCP servers defined in config.yaml and exposes their tools
to the brain as auto-generated function files in core/functions/.

Config structure in config.yaml:
    mcp_servers:
      filesystem:
        command: "npx"
        args: ["-y", "@modelcontextprotocol/server-filesystem", "/data"]
      remote:
        url: "http://localhost:8000/sse"
"""

import json
import logging
import os
import threading

logger = logging.getLogger("mcp_client")

_FUNCTIONS_DIR = os.path.join(os.path.dirname(__file__), "functions")


class MCPServer:
    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config
        self.tools: list[dict] = []
        self._lock = threading.Lock()
        self._connected = False

    def connect(self) -> bool:
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

            if "url" in self.config:
                return self._connect_sse()
            return self._connect_stdio()
        except ImportError:
            logger.warning("MCP SDK not installed. Install with: pip install mcp")
            return False

    def _connect_stdio(self) -> bool:
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

            cmd = self.config.get("command", "")
            args = self.config.get("args", [])
            env_vars = self.config.get("env", {})
            env = {**os.environ, **env_vars}

            params = StdioServerParameters(command=cmd, args=args, env=env)

            async def _connect():
                async with stdio_client(params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.list_tools()
                        with self._lock:
                            self.tools = [
                                {
                                    "name": t.name,
                                    "description": t.description or "",
                                    "input_schema": (
                                        t.inputSchema
                                        if hasattr(t, "inputSchema")
                                        else {"type": "object", "properties": {}}
                                    ),
                                }
                                for t in result.tools
                            ]
                            self._connected = True

            import asyncio

            try:
                asyncio.get_running_loop()
                asyncio.create_task(_connect())
            except RuntimeError:
                asyncio.run(_connect())
            return True
        except Exception as e:
            logger.error(f"MCP stdio {self.name}: {e}")
            return False

    def _connect_sse(self) -> bool:
        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client

            url = self.config["url"]

            async def _connect():
                async with sse_client(url) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.list_tools()
                        with self._lock:
                            self.tools = [
                                {
                                    "name": t.name,
                                    "description": t.description or "",
                                    "input_schema": (
                                        t.inputSchema
                                        if hasattr(t, "inputSchema")
                                        else {"type": "object", "properties": {}}
                                    ),
                                }
                                for t in result.tools
                            ]
                            self._connected = True

            import asyncio

            try:
                asyncio.get_running_loop()
                asyncio.create_task(_connect())
            except RuntimeError:
                asyncio.run(_connect())
            return True
        except Exception as e:
            logger.error(f"MCP SSE {self.name}: {e}")
            return False

    def call_tool(self, tool_name: str, arguments: dict) -> str:
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

            c = self.config
            cmd = c.get("command", "")
            args = c.get("args", [])
            env_vars = c.get("env", {})
            env = {**os.environ, **env_vars}

            params = StdioServerParameters(command=cmd, args=args, env=env)

            async def _call():
                async with stdio_client(params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool(tool_name, arguments)
                        return result

            import asyncio

            try:
                asyncio.get_running_loop()
            except RuntimeError:
                result = asyncio.run(_call())

            if hasattr(result, "content") and result.content:
                parts = [c.text for c in result.content if hasattr(c, "text")]
                return "\n".join(parts)
            return json.dumps(result, default=str)
        except Exception as e:
            return f"MCP tool error: {e}"

    def disconnect(self) -> None:
        self._connected = False
        self.tools = []


_registry: dict[str, MCPServer] = {}
_lock = threading.Lock()


def _make_function_code(server_name: str, tool: dict) -> tuple[str, str]:
    safe_name = tool["name"].replace("-", "_").replace(".", "_")
    filename = f"mcp_{server_name}_{safe_name}"
    schema = tool.get("input_schema", {"type": "object", "properties": {}})
    schema_json = json.dumps(schema, indent=4)
    desc = tool.get("description", "").replace('"', '\\"')[:2000]

    code = (
        f"def run(**kwargs) -> str:\n"
        f"    from core_rpc import mcp_call_tool\n"
        f'    return mcp_call_tool("{server_name}", "{tool["name"]}", kwargs)\n'
        f"\n"
        f"SPEC = {{\n"
        f'    "description": "{desc}",\n'
        f'    "parameters": {schema_json},\n'
        f"}}\n"
    )
    return code, filename


def _write_function_file(filename: str, code: str) -> None:
    os.makedirs(_FUNCTIONS_DIR, exist_ok=True)
    path = os.path.join(_FUNCTIONS_DIR, filename + ".py")
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)


def _remove_function_file(filename: str) -> None:
    path = os.path.join(_FUNCTIONS_DIR, filename + ".py")
    if os.path.exists(path):
        os.remove(path)


def load_servers(mcp_configs: dict[str, dict]) -> int:
    count = 0
    for name, cfg in mcp_configs.items():
        if name in _registry:
            continue
        server = MCPServer(name, cfg)
        if server.connect():
            with _lock:
                _registry[name] = server
            for tool in server.tools:
                code, fname = _make_function_code(name, tool)
                _write_function_file(fname, code)
            count += 1
    return count


def call_tool(server_name: str, tool_name: str, arguments: dict) -> str:
    with _lock:
        server = _registry.get(server_name)
    if server is None:
        return f"MCP server not found: {server_name}"
    return server.call_tool(tool_name, arguments)


def shutdown() -> None:
    with _lock:
        for name, server in list(_registry.items()):
            for tool in server.tools:
                safe_name = tool["name"].replace("-", "_").replace(".", "_")
                fname = f"mcp_{name}_{safe_name}"
                _remove_function_file(fname)
            server.disconnect()
        _registry.clear()
