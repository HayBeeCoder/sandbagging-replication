import pytest
import yaml

from sandbag import registry
from sandbag.config import ROOT


def write_registry(tmp_path, **changes):
    """A one-entry models.yaml in a temp folder, with some fields changed."""
    entry = {"model": "some/model", "provider": "openai-compatible", "base_url": "http://localhost:8000/v1",
             "tool_mode": "text", "role": "testing"}
    entry.update(changes)
    entry = {k: v for k, v in entry.items() if v is not None}
    path = tmp_path / "models.yaml"
    path.write_text(yaml.safe_dump({"example": entry}))
    return path


def test_every_entry_in_the_real_file_is_valid():
    models = registry.load_registry()
    assert {"mock", "llama31_8b_runpod", "llama405b_runpod", "claude_sonnet55"} <= set(models)
    assert models["llama405b_runpod"].role == "replication"
    assert models["llama405b_runpod"].tool_mode == "text"      # Apollo's scaffold for Llama
    assert models["claude_sonnet55"].tool_mode == "native"     # Apollo's choice for Claude


def test_no_api_key_is_ever_written_in_the_file():
    text = (ROOT / "models.yaml").read_text()
    assert "sk-ant-" not in text and "hf_" not in text


def test_unknown_key_is_refused_and_lists_the_choices():
    with pytest.raises(ValueError, match="available: mock"):
        registry.get_spec("llama_9000")


@pytest.mark.parametrize("changes,message", [
    ({"provider": "magic"}, "provider"),
    ({"tool_mode": "telepathy"}, "tool_mode"),
    ({"role": "favourite"}, "role"),
    ({"base_url": None}, "base_url"),
    ({"generate": {"temprature": 0.5}}, "unknown generate settings"),
    ({"colour": "blue"}, "example"),
])
def test_bad_entries_are_refused(tmp_path, changes, message):
    with pytest.raises(ValueError, match=message):
        registry.load_registry(write_registry(tmp_path, **changes))


def test_the_mock_model_builds():
    assert registry.build_model("mock").name == "model"


def test_a_local_model_builds_without_contacting_the_server():
    model = registry.build_model("llama405b_runpod")
    assert "Llama-3.1-405B-Instruct-FP8" in model.name
    assert model.config.max_tokens == 4096  # Apollo's setting, taken from experiment.yaml


def test_a_claude_model_needs_its_key(monkeypatch):
    monkeypatch.setattr(registry, "load_dotenv", lambda *a, **k: None)  # ignore any real .env
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        registry.build_model("claude_sonnet55")


def test_a_claude_model_builds_once_the_key_is_set(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
    assert registry.build_model("claude_sonnet55").name == "claude-sonnet-5-5"