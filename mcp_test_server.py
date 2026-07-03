"""Minimal MCP test server for validating the MCP Bridge.
Implements JSON-RPC 2.0 over stdio per MCP spec.
Tools: calculator, echo, time"""
import json, sys, datetime

TOOLS = [
    {
        "name": "calculator",
        "description": "Evaluate a math expression",
        "inputSchema": {
            "type": "object",
            "properties": {"expression": {"type": "string", "description": "Math expression e.g. 2+2"}},
            "required": ["expression"],
        },
    },
    {
        "name": "get_time",
        "description": "Get current date and time",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "echo",
        "description": "Echo back the input text",
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
]


def handle_request(req):
    method = req.get("method", "")
    params = req.get("params", {}) or {}
    req_id = req.get("id")

    if method == "initialize":
        return {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                "serverInfo": {"name": "m365-test-mcp", "version": "1.0.0"}}

    if method == "tools/list":
        return {"tools": TOOLS}

    if method == "tools/call":
        name = params.get("name", "")
        args = params.get("arguments", {}) or {}
        if name == "calculator":
            expr = args.get("expression", "")
            try:
                result = str(eval(expr, {"__builtins__": {}}, {}))
            except Exception as e:
                result = f"error: {e}"
            return {"content": [{"type": "text", "text": result}]}
        elif name == "get_time":
            return {"content": [{"type": "text", "text": datetime.datetime.now().isoformat()}]}
        elif name == "echo":
            return {"content": [{"type": "text", "text": args.get("text", "")}]}
        return {"content": [{"type": "text", "text": f"unknown tool: {name}"}]}

    return {"error": {"code": -32601, "message": f"Method not found: {method}"}}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            result = handle_request(req)
            response = {"jsonrpc": "2.0", "id": req.get("id"), "result": result}
        except Exception as e:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(e)}}
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
