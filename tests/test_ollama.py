import unittest
from unittest.mock import patch

from local_agent_bench.ollama import OllamaClient, OllamaError


class OllamaClientTest(unittest.TestCase):
    def test_timeout_error_is_wrapped(self) -> None:
        client = OllamaClient("http://ollama:11434")

        with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
            with self.assertRaises(OllamaError) as raised:
                client.chat("qwen2.5-coder:7b", [{"role": "user", "content": "Hello"}])

        self.assertIn("timed out", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
