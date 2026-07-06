import json, subprocess, os, time
from typing import Dict, List, Any, Optional


class MCPServer:
    def __init__(self, server_id: str, name: str, description: str = ""):
        self.server_id = server_id
        self.name = name
        self.description = description
        self.tools: List[Dict] = []
        self._process: Optional[subprocess.Popen] = None

    def add_tool(self, name: str, description: str, parameters: Optional[Dict] = None):
        self.tools.append({
            "name": name, "description": description,
            "inputSchema": parameters or {"type": "object", "properties": {}},
        })

    def to_openai_tools(self) -> List[Dict]:
        result = []
        for t in self.tools:
            schema = t.get("inputSchema", {"type": "object", "properties": {}})
            result.append({
                "type": "function",
                "function": {
                    "name": f"{self.server_id}__{t['name']}",
                    "description": t.get("description", ""),
                    "parameters": schema,
                },
            })
        return result

    def start(self, command: str, args: List[str], env: Dict[str, str] = None):
        if self._process:
            return
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        self._process = subprocess.Popen(
            [command] + args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env=merged_env, text=True, bufsize=1,
        )

    def stop(self):
        if self._process:
            self._process.terminate()
            self._process.wait(timeout=5)
            self._process = None

    def _send_jsonrpc(self, method: str, params: Any = None, req_id: int = 1) -> Dict:
        if not self._process:
            raise RuntimeError(f"Server {self.server_id} not started")
        payload = {"jsonrpc": "2.0", "method": method, "id": req_id}
        if params is not None:
            payload["params"] = params
        self._process.stdin.write(json.dumps(payload) + "\n")
        self._process.stdin.flush()
        line = self._process.stdout.readline()
        if not line:
            raise RuntimeError(f"Server {self.server_id} closed connection")
        resp = json.loads(line.strip())
        if "error" in resp:
            raise RuntimeError(f"MCP error: {resp['error']}")
        return resp.get("result", {})


class MCPBridge:
    def __init__(self):
        self.servers: Dict[str, MCPServer] = {}

    def register_server(self, server: MCPServer):
        self.servers[server.server_id] = server

    def get_all_tools(self) -> List[Dict]:
        tools = []
        for server in self.servers.values():
            tools.extend(server.to_openai_tools())
        return tools

    def call_tool(self, server_id: str, tool_name: str, arguments: Dict = None) -> Any:
        server = self.servers.get(server_id)
        if not server:
            raise ValueError(f"Server '{server_id}' not found")
        req_id = int(time.time() * 1000) % 100000
        result = server._send_jsonrpc(
            "tools/call",
            {"name": tool_name, "arguments": arguments or {}},
            req_id,
        )
        content = result.get("content", [])
        text_parts = [c.get("text", "") for c in content if c.get("type") == "text"]
        return "\n".join(text_parts)

    def discover_local_mcp(self):
        config_path = os.path.expanduser("~/.mcp/servers.json")
        if not os.path.exists(config_path):
            return []
        try:
            with open(config_path, "r", encoding="utf-8-sig") as f:
                config = json.load(f)
        except Exception:
            return []
        discovered = []
        for s in config.get("servers", []):
            server_id = s.get("id", "")
            server = MCPServer(server_id, s.get("name", server_id))
            cmd = s.get("command", "")
            args = s.get("args", [])
            env = s.get("env", {})
            try:
                server.start(cmd, args, env)
                server._send_jsonrpc("initialize", {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "m365-copilot", "version": "0.5.0"},
                }, req_id=1)
                tools_result = server._send_jsonrpc("tools/list", req_id=2)
                for t in tools_result.get("tools", []):
                    server.add_tool(t["name"], t.get("description", ""), t.get("inputSchema"))
                self.register_server(server)
                discovered.append(server)
            except Exception:
                server.stop()
        return discovered
