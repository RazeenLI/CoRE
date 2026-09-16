import unittest

from model.core.llm_client import HFLLMClient


class CoreLLMClientTest(unittest.TestCase):
    def test_gpt_oss_passes_low_reasoning_effort_to_chat_template(self) -> None:
        captured = {}

        class Tokenizer:
            def apply_chat_template(self, messages, **kwargs):
                captured.update(kwargs)
                return "prompt"

        client = object.__new__(HFLLMClient)
        client.model_name = "openai/gpt-oss-20b"
        client.supports_thinking = False
        client.reasoning_effort = "low"
        client.tokenizer = Tokenizer()

        prompt = client._build_prompt(
            [{"role": "user", "content": "test"}],
            mode="non_thinking",
        )

        self.assertEqual(prompt, "prompt")
        self.assertEqual(captured["reasoning_effort"], "low")
        self.assertTrue(captured["add_generation_prompt"])
