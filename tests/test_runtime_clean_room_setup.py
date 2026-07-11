import importlib.util
import unittest
from pathlib import Path


def _load_setup_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "setup_runtime_clean_room.py"
    spec = importlib.util.spec_from_file_location("setup_runtime_clean_room", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class RuntimeCleanRoomSetupTest(unittest.TestCase):
    def test_openclaw_patch_declares_local_ollama_models(self) -> None:
        module = _load_setup_module()
        patch = module.build_openclaw_patch(["qwen2.5-coder:7b"], "http://ollama:11434", 131072, 2048, "secret")

        provider = patch["models"]["providers"]["ollama"]
        self.assertEqual(provider["baseUrl"], "http://ollama:11434")
        self.assertEqual(provider["api"], "ollama")
        self.assertEqual(provider["apiKey"], "secret")
        self.assertEqual(provider["models"][0]["id"], "qwen2.5-coder:7b")
        self.assertEqual(provider["models"][0]["contextWindow"], 131072)

    def test_openclaw_model_ids_include_manifest_judge_model(self) -> None:
        module = _load_setup_module()
        ids = module._openclaw_model_ids(
            {"judge_model": "ollama/glm-5.2:cloud"},
            ["qwen2.5-coder:7b"],
        )

        self.assertEqual(ids, ["qwen2.5-coder:7b", "glm-5.2:cloud"])

    def test_pi_models_config_uses_openai_compatible_ollama_url(self) -> None:
        module = _load_setup_module()
        config = module.build_pi_models_config(["ornith:9b"], "http://ollama:11434/v1")

        provider = config["providers"]["ollama"]
        self.assertEqual(provider["baseUrl"], "http://ollama:11434/v1")
        self.assertEqual(provider["api"], "openai-completions")
        self.assertEqual(provider["models"], [{"id": "ornith:9b"}])


if __name__ == "__main__":
    unittest.main()
