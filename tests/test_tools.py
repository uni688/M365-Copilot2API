"""Unit tests for tool-related components."""
import json, os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from m365_copilot.tools.mcp_bridge import MCPServer, MCPBridge
from m365_copilot.tools.detector import ToolCallDetector, detect_tool_intent, extract_tool_args


class TestMCPServer(unittest.TestCase):
    def test_to_openai_tools_empty(self):
        s = MCPServer("test", "Test Server")
        self.assertEqual(s.to_openai_tools(), [])

    def test_to_openai_tools_with_tools(self):
        s = MCPServer("calc", "Calculator", "Does math")
        s.add_tool("add", "Add two numbers", {
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
        })
        tools = s.to_openai_tools()
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]["type"], "function")
        self.assertEqual(tools[0]["function"]["name"], "calc__add")

    def test_to_openai_tools_no_params(self):
        s = MCPServer("util", "Utility")
        s.add_tool("ping", "Ping test")
        tools = s.to_openai_tools()
        self.assertIn("parameters", str(tools))  # converted from inputSchema


class TestMCPBridge(unittest.TestCase):
    def test_register_and_get_tools(self):
        bridge = MCPBridge()
        s = MCPServer("s1", "Server 1")
        s.add_tool("t1", "Tool 1")
        bridge.register_server(s)
        tools = bridge.get_all_tools()
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]["function"]["name"], "s1__t1")

    def test_get_tools_empty(self):
        bridge = MCPBridge()
        self.assertEqual(bridge.get_all_tools(), [])


class TestToolCallDetector(unittest.TestCase):
    def test_detect_none(self):
        result = ToolCallDetector.detect("Hello, how are you?")
        self.assertIsNone(result)

    def test_detect_simple_json(self):
        result = ToolCallDetector.detect(
            'Here is the result: {"name": "get_weather", "arguments": {"city": "Beijing"}}'
        )
        self.assertIsNotNone(result)
        name, args = result
        self.assertEqual(name, "get_weather")

    def test_detect_markdown_json(self):
        result = ToolCallDetector.detect(
            '```json\n{"name": "calculate", "arguments": {"expression": "2+2"}}\n```'
        )
        self.assertIsNotNone(result)
        name, args = result
        self.assertEqual(name, "calculate")
        self.assertEqual(args["expression"], "2+2")

    def test_detect_empty(self):
        self.assertIsNone(ToolCallDetector.detect(""))


class TestDetectToolIntent(unittest.TestCase):
    def test_time_intent(self):
        self.assertEqual(detect_tool_intent("what time is it"), "get_current_time")

    def test_date_intent(self):
        self.assertEqual(detect_tool_intent("current date"), "get_current_time")

    def test_math_intent(self):
        self.assertEqual(detect_tool_intent("calculate 2+2"), "calculate")

    def test_dice_intent(self):
        self.assertEqual(detect_tool_intent("roll a dice"), "roll_dice")

    def test_no_intent(self):
        self.assertIsNone(detect_tool_intent("hello world"))


class TestExtractToolArgs(unittest.TestCase):
    def test_calculate(self):
        args = extract_tool_args("calculate 2+2", "calculate")
        self.assertEqual(args["expression"], "2+2")

    def test_roll_dice_default(self):
        args = extract_tool_args("roll a dice", "roll_dice")
        self.assertEqual(args.get("sides"), 6)

    def test_get_current_time(self):
        args = extract_tool_args("what time", "get_current_time")
        self.assertEqual(args, {})


if __name__ == "__main__":
    unittest.main()
