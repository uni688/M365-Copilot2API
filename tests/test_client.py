"""Unit tests for M365Client and payload utilities."""
import json, os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ["M365_TENANT_ID"] = "test-tenant"
os.environ["M365_USER_OID"] = "test-oid"

from m365_copilot.client import clean_text, extract_tool_call
from m365_copilot.payload import build_conversation_payload


class TestCleanText(unittest.TestCase):
    def test_clean_normal(self):
        self.assertEqual(clean_text("hello"), "hello")

    def test_clean_empty(self):
        self.assertEqual(clean_text(""), "")

    def test_clean_none(self):
        self.assertEqual(clean_text(None), "")

    def test_clean_bytes(self):
        self.assertEqual(clean_text(b"hello"), "hello")

    def test_clean_nonprintable(self):
        result = clean_text("hello\x00world")
        self.assertEqual(result, "helloworld")  # \x00 stripped, no space added


class TestExtractToolCall(unittest.TestCase):
    def test_search_message(self):
        msg = {"messageType": "InternalSearchQuery", "text": "search: weather", "messageId": "m1"}
        result = extract_tool_call(msg)
        self.assertIsNotNone(result)
        self.assertEqual(result["function"]["name"], "search")

    def test_code_interpreter(self):
        msg = {"messageType": "GeneratedCode", "text": "print('hello')"}
        result = extract_tool_call(msg)
        self.assertIsNotNone(result)
        self.assertEqual(result["function"]["name"], "code_interpreter")

    def test_image_gen(self):
        msg = {"messageType": "GenerateGraphicArt", "text": "a cat"}
        result = extract_tool_call(msg)
        self.assertIsNotNone(result)
        self.assertEqual(result["function"]["name"], "generate_image")

    def test_unknown_type(self):
        msg = {"messageType": "UnknownType", "text": "hello"}
        result = extract_tool_call(msg)
        self.assertIsNone(result)

    def test_no_message_type(self):
        msg = {"text": "hello"}
        result = extract_tool_call(msg)
        self.assertIsNone(result)

    def test_empty_text(self):
        msg = {"messageType": "InternalSearchQuery", "text": ""}
        result = extract_tool_call(msg)
        self.assertIsNone(result)


class TestBuildPayload(unittest.TestCase):
    def test_build_conversation_basic(self):
        messages = [{"role": "user", "content": "hello"}]
        payloads = list(build_conversation_payload("hex123", "uuid-456", messages, "Magic", None, False, False))
        self.assertGreater(len(payloads), 0)

    def test_build_conversation_role_tool(self):
        messages = [
            {"role": "assistant", "content": "Let me check", "tool_calls": [{"id": "call_1", "function": {"name": "search", "arguments": "{}"}}]},
            {"role": "tool", "content": '{"result": "data"}', "tool_call_id": "call_1"},
            {"role": "user", "content": "thanks"},
        ]
        payloads = list(build_conversation_payload("hex", "uuid", messages, "Magic", None, False, False))
        self.assertGreater(len(payloads), 0)

    def test_build_conversation_empty_messages(self):
        payloads = list(build_conversation_payload("hex", "uuid", [], "Magic", None, False, False))
        full = "".join(payloads)
        self.assertIn("Magic", full)

    def test_build_conversation_image_gen(self):
        messages = [{"role": "user", "content": "draw a cat"}]
        payloads = list(build_conversation_payload("hex", "uuid", messages, "Magic", None, True, False))
        self.assertGreater(len(payloads), 0)

    def test_build_conversation_file_upload(self):
        messages = [{"role": "user", "content": "analyze this"}]
        payloads = list(build_conversation_payload("hex", "uuid", messages, "Magic", None, False, True))
        self.assertGreater(len(payloads), 0)

    def test_build_conversation_override(self):
        messages = [{"role": "user", "content": "hello"}]
        payloads = list(build_conversation_payload("hex", "uuid", messages, "Magic", "Gpt_5_5_Chat", False, False))
        self.assertGreater(len(payloads), 0)

    def test_build_conversation_user_tool_msg(self):
        messages = [
            {"role": "user", "content": "check weather"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "tc1", "type": "function", "function": {"name": "get_weather", "arguments": "{}"}}]},
            {"role": "tool", "content": "sunny", "tool_call_id": "tc1"},
        ]
        payloads = list(build_conversation_payload("hex", "uuid", messages, "Magic", None, False, False))
        self.assertGreater(len(payloads), 0)


if __name__ == "__main__":
    unittest.main()
