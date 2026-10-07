from pathlib import Path

def patch(path, edits):
    file = Path(path)
    text = file.read_text()
    for old, new in edits:
        assert text.count(old) == 1, f"expected exactly one in {path}:\n{old}"
        text = text.replace(old, new)
    file.write_text(text)
    print("updated", path)

# ---- registry.py: OpenRouter as a provider of its own, always pinned to one host ----
patch("sandbag/registry.py", [
    ('''PROVIDERS = ("mock", "openai-compatible", "anthropic")
''',
     '''PROVIDERS = ("mock", "openai-compatible", "anthropic", "openrouter")
'''),
    ('''    base_url: str | None = None
''',
     '''    base_url: str | None = None
    host: str | None = None      # (openrouter) the one company allowed to serve the requests
    apollo: dict | None = None   # what the paper reports for this model: {name, gaps: {prompt: gap}, caveat}
'''),
    ('''        if spec.provider == "openai-compatible" and not spec.base_url:
''',
     '''        if spec.provider == "openrouter" and not (spec.host and spec.api_key_env):
            raise ValueError(f"'{key}': an openrouter model needs a host (to pin one company) and an api_key_env")
        if spec.provider == "openai-compatible" and not spec.base_url:
'''),
    ('''    # openai-compatible: vLLM on the pod, Together, OpenRouter, ...
''',
     '''    if spec.provider == "openrouter":
        # One host only, and no falling back to another: every run of an experiment must use the same weights.
        return get_model(f"openrouter/{spec.model}", api_key=api_key, config=config,
                         provider={"order": [spec.host], "allow_fallbacks": False})
    # openai-compatible: vLLM on the pod, Together, OpenRouter, ...
'''),
])

# ---- analyze.py: say what the paper reports for this model, when it reports anything ----
patch("sandbag/analyze.py", [
    ('''from sandbag.config import ROOT
''',
     '''from sandbag.config import ROOT
from sandbag.registry import load_registry
'''),
    ('''def framing(role: str, system: str, scenario: str = prompts.DEFAULT_SCENARIO) -> str:
    """How this result may be described. Only one cell of Apollo's table can be replicated directly."""
    if role == "testing":
        return "A pipeline test with a fake or pilot model. Not a result."
    if scenario != prompts.DEFAULT_SCENARIO:
        return (f"A new design (scenario '{scenario}'): the model is not told it is being tested, and all scenario wording "
                "is ours. Not a replication. 'Read docs' below means the consequence text appeared in a command's output.")
''',
     '''def framing(role: str, system: str, scenario: str = prompts.DEFAULT_SCENARIO, apollo: dict | None = None) -> str:
    """How this result may be described. Only cells of Apollo's table can be replicated directly."""
    if role == "testing":
        return "A pipeline test with a fake or pilot model. Not a result."
    if scenario != prompts.DEFAULT_SCENARIO:
        return (f"A new design (scenario '{scenario}'): the model is not told it is being tested, and all scenario wording "
                "is ours. Not a replication. 'Read docs' below means the consequence text appeared in a command's output.")
    if apollo and system in apollo.get("gaps", {}):
        reported = f"Apollo report a gap of {apollo['gaps'][system]:.2f} for {apollo['name']}"
        caveat = (" " + apollo["caveat"]) if apollo.get("caveat") else ""
        if system in ("goal_medium", "goal_easy"):
            return (f"Comparable to a reported result, with our own hint wording. {reported} at this difficulty with "
                    f"their unpublished hints, so the size of any gap may differ.{caveat}")
        return f"A replication of a reported result. {reported} with this prompt.{caveat}"
'''),
    ('''             f"**{framing(recorded['role'], recorded['system'], scenario)}**", "",
''',
     '''             f"**{framing(recorded['role'], recorded['system'], scenario, getattr(load_registry().get(recorded['model_key']), 'apollo', None))}**", "",
'''),
])

# ---- models.yaml: document the new fields and add four OpenAI models ----
patch("models.yaml", [
    ('''#   provider     mock | openai-compatible | anthropic
''',
     '''#   provider     mock | openai-compatible | anthropic | openrouter
#   host         (openrouter) the one company allowed to serve the requests, e.g. OpenAI
#   apollo       optional: what the paper reports for this model (name, gaps per system prompt, caveat)
'''),
])
file = Path("models.yaml")
text = file.read_text()
assert "gpt4o_openrouter:" not in text, "models.yaml already has these entries"
file.write_text(text.rstrip("\n") + '''

gpt4o_openrouter:
  model: openai/gpt-4o-2024-08-06
  provider: openrouter
  host: OpenAI
  api_key_env: OPENROUTER_API_KEY
  tool_mode: native
  role: replication
  apollo:
    name: gpt-4o (gpt-4o-2024-08-06, the same snapshot)
    gaps: {goal_easy: 0.01, goal_medium: 0.01, goal_hard: 0.08}
  notes: The exact gpt-4o snapshot in Apollo's paper (Table 19). No private reasoning.

o1_openrouter:
  model: openai/o1
  provider: openrouter
  host: OpenAI
  api_key_env: OPENROUTER_API_KEY
  tool_mode: native
  role: new_measurement
  apollo:
    name: o1
    gaps: {goal_easy: 0.29, goal_medium: 0.21, goal_hard: 0.21}
    caveat: Apollo used a pre-deployment checkpoint of o1 that was never public, so this released model may differ.
  notes: Expensive (about 15 and 60 dollars per million tokens in and out). Reasoning is hidden.

gpt61_sol_openrouter:
  model: openai/gpt-6.1-sol
  provider: openrouter
  host: OpenAI
  api_key_env: OPENROUTER_API_KEY
  tool_mode: native
  role: new_measurement
  notes: Newest OpenAI model on OpenRouter when added (released 2026-09-29). Reasoning is hidden.

gpt6_luna_openrouter:
  model: openai/gpt-6-luna
  provider: openrouter
  host: OpenAI
  api_key_env: OPENROUTER_API_KEY
  tool_mode: native
  role: new_measurement
  notes: The cheap current OpenAI model; use it for pilots. Reasoning is hidden.
''')
print("added four OpenAI entries to models.yaml")

# ---- tests ----
patch("tests/test_registry.py", [
    ('''def test_no_api_key_is_ever_written_in_the_file():
''',
     '''def test_openrouter_models_are_pinned_to_one_host(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "not-a-real-key")
    for key in ("gpt4o_openrouter", "o1_openrouter", "gpt61_sol_openrouter", "gpt6_luna_openrouter"):
        model = registry.build_model(key)
        assert model.api.provider == {"order": ["OpenAI"], "allow_fallbacks": False}
    assert registry.get_spec("gpt4o_openrouter").model == "openai/gpt-4o-2024-08-06"  # the snapshot in the paper


def test_an_openrouter_model_without_a_host_is_refused(tmp_path):
    path = write_registry(tmp_path, provider="openrouter", base_url=None, api_key_env="OPENROUTER_API_KEY")
    with pytest.raises(ValueError, match="needs a host"):
        registry.load_registry(path)


def test_no_api_key_is_ever_written_in_the_file():
'''),
])
patch("tests/test_analyze.py", [
    ('''def test_only_one_cell_counts_as_a_direct_replication():
''',
     '''def test_models_from_the_paper_are_described_with_the_papers_numbers():
    from sandbag.registry import get_spec
    gpt4o, o1 = get_spec("gpt4o_openrouter").apollo, get_spec("o1_openrouter").apollo
    assert "A replication of a reported result. Apollo report a gap of 0.08 for gpt-4o" in framing("replication", "goal_hard", apollo=gpt4o)
    assert "our own hint wording" in framing("replication", "goal_easy", apollo=gpt4o)
    assert "pre-deployment checkpoint" in framing("new_measurement", "goal_hard", apollo=o1)
    assert "new measurement" in framing("new_measurement", "no_goal", apollo=o1)       # the paper gives no figure we use here
    assert "Not a replication" in framing("replication", "goal_hard", "colleague_note", apollo=gpt4o)  # our scenarios never are


def test_only_one_cell_counts_as_a_direct_replication():
'''),
])
