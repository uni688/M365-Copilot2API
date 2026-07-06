"""Unit tests for OpenAI-compatible API server."""
import json, os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ["M365_TENANT_ID"] = "test-tenant"
os.environ["M365_USER_OID"] = "test-oid"

from m365_copilot.servers.openai import (
    sse_msg, sse_done, inject_json_mode, fim_to_chat,
    _resolve_anthropic_model, ANTHROPIC_MODEL_MAP,
)
from m365_copilot.models import MODELS, lookup_model
from m365_copilot.payload import build_url


class TestSSEFormat(unittest.TestCase):
    def test_sse_msg_basic(self):
        result = sse_msg({"content": "hello"}, "cmpl-123", "gpt-4")
        self.assertIn("data: ", result)
        self.assertIn("hello", result)
        self.assertIn("cmpl-123", result)

    def test_sse_msg_defaults(self):
        result = sse_msg({"content": "hi"})
        self.assertIn("chatcmpl-", result)
        self.assertIn("gpt-4", result)

    def test_sse_done_usage(self):
        result = sse_done("cmpl-1", "gpt-4", {"prompt_tokens": 10, "completion_tokens": 5})
        self.assertIn("[DONE]", result)
        self.assertIn("prompt_tokens", result)

    def test_sse_done_no_usage(self):
        result = sse_done("cmpl-1", "gpt-4")
        self.assertIn("[DONE]", result)
        self.assertNotIn("prompt_tokens", result)


class TestAnthropicModelMap(unittest.TestCase):
    def test_no_claude_entries(self):
        for key in ANTHROPIC_MODEL_MAP:
            self.assertNotIn("claude", key.lower())

    def test_resolve_direct(self):
        self.assertEqual(_resolve_anthropic_model("gpt-5.5"), "gpt5.5")

    def test_resolve_prefix(self):
        self.assertEqual(_resolve_anthropic_model("gpt-4o-mini"), "auto")

    def test_resolve_unknown(self):
        self.assertEqual(_resolve_anthropic_model("nonexistent-model"), "auto")


class TestJSONMode(unittest.TestCase):
    def test_inject_with_system(self):
        msgs = [{"role": "system", "content": "Be helpful"}]
        inject_json_mode(msgs)
        self.assertIn("JSON", msgs[0]["content"])

    def test_inject_without_system(self):
        msgs = [{"role": "user", "content": "hi"}]
        inject_json_mode(msgs)
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["role"], "system")

    def test_inject_empty(self):
        msgs = []
        inject_json_mode(msgs)
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["role"], "system")


class TestFIM(unittest.TestCase):
    def test_fim_basic(self):
        msgs = fim_to_chat("hello")
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["role"], "user")
        self.assertIn("hello", msgs[0]["content"])

    def test_fim_with_suffix(self):
        msgs = fim_to_chat("start", "end")
        self.assertIn("start", msgs[0]["content"])
        self.assertIn("end", msgs[0]["content"])
        self.assertIn("MIDDLE", msgs[0]["content"])


class TestModels(unittest.TestCase):
    def test_model_keys(self):
        for key in MODELS:
            cfg = MODELS[key]
            self.assertIn("tone", cfg)
            self.assertIn("openai_id", cfg)
            self.assertNotIn("claude", key.lower())

    def test_lookup_existing(self):
        cfg = lookup_model("auto")
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg["tone"], "Magic")

    def test_lookup_unknown(self):
        cfg = lookup_model("fake-model")
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg["tone"], "Magic")  # falls back to auto

    def test_no_claude_in_models(self):
        for key in MODELS:
            self.assertNotIn("claude", key.lower())


class TestPayload(unittest.TestCase):
    def test_build_url(self):
        url, hex_sid, uuid_sid = build_url("test-token")
        self.assertIn("wss://", url)
        self.assertIn("test-token", url)
        self.assertEqual(len(hex_sid), 32)
        self.assertNotIn("ConversationId", url)

    def test_build_url_no_conv_id(self):
        url, _, _ = build_url("token")
        self.assertNotIn("ConversationId", url)

    def test_build_url_with_conv_id(self):
        url, _, _ = build_url("token", conversation_id="abc123")
        self.assertIn("ConversationId=abc123", url)


if __name__ == "__main__":
    unittest.main()
