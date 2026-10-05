
import os
from dataclasses import dataclass, field

import yaml
from dotenv import load_dotenv
from inspect_ai.model import GenerateConfig, Model, get_model

from sandbag.config import ROOT, load_experiment

PROVIDERS = ("mock", "openai-compatible", "anthropic")
TOOL_MODES = ("text", "native")
ROLES = ("testing", "replication", "new_measurement")


@dataclass
class ModelSpec:
    key: str
    model: str
    provider: str
    tool_mode: str
    role: str
    service: str = "vllm"
    base_url: str | None = None
    api_key_env: str | None = None
    generate: dict = field(default_factory=dict)
    serve: str = ""
    notes: str = ""


def load_registry(path=None) -> dict[str, ModelSpec]:
    """Read models.yaml and check every entry."""
    raw = yaml.safe_load((path or ROOT / "models.yaml").read_text())
    registry = {}
    for key, entry in raw.items():
        try:
            spec = ModelSpec(key=key, **entry)
        except TypeError as error:  # a missing or misspelt field
            raise ValueError(f"models.yaml entry '{key}': {error}") from None
        if spec.provider not in PROVIDERS:
            raise ValueError(f"'{key}': provider must be one of {PROVIDERS}, got '{spec.provider}'")
        if spec.tool_mode not in TOOL_MODES:
            raise ValueError(f"'{key}': tool_mode must be one of {TOOL_MODES}, got '{spec.tool_mode}'")
        if spec.role not in ROLES:
            raise ValueError(f"'{key}': role must be one of {ROLES}, got '{spec.role}'")
        if spec.provider == "openai-compatible" and not spec.base_url:
            raise ValueError(f"'{key}': an openai-compatible model needs a base_url")
        unknown = set(spec.generate) - set(GenerateConfig.model_fields)
        if unknown:
            raise ValueError(f"'{key}': unknown generate settings {sorted(unknown)}")
        registry[key] = spec
    return registry


def get_spec(key: str) -> ModelSpec:
    registry = load_registry()
    if key not in registry:
        raise ValueError(f"no model '{key}' in models.yaml; available: {', '.join(registry)}")
    return registry[key]


def build_model(key: str) -> Model:
    """A ready-to-use Inspect model for one registry key."""
    spec = get_spec(key)
    load_dotenv(ROOT / ".env")  # API keys live in .env, which git ignores

    api_key = None
    if spec.api_key_env:
        api_key = os.environ.get(spec.api_key_env)
        if not api_key:
            raise ValueError(f"'{key}' needs {spec.api_key_env}; add a line {spec.api_key_env}=... to .env")

    # Apollo set max tokens to 4096 for every model; an entry's own settings are added on top.
    config = GenerateConfig(**{"max_tokens": load_experiment()["max_tokens"], **spec.generate})

    if spec.provider == "mock":
        return get_model("mockllm/model", config=config)
    if spec.provider == "anthropic":
        return get_model(f"anthropic/{spec.model}", api_key=api_key, config=config)
    # openai-compatible: vLLM on the pod, Together, OpenRouter, ...
    return get_model(f"openai-api/{spec.service}/{spec.model}", base_url=spec.base_url,
                     api_key=api_key or "local", config=config)


if __name__ == "__main__":
    print(f"{'key':<30}{'role':<17}{'tools':<8}{'provider':<19}model")
    for spec in load_registry().values():
        print(f"{spec.key:<30}{spec.role:<17}{spec.tool_mode:<8}{spec.provider:<19}{spec.model}")