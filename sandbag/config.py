"""Loads experiment.yaml and refuses to continue if a setting is missing or wrong."""
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent  # the repo folder

# setting name -> the type its value must have
REQUIRED = {
    "runs_per_condition": int,
    "conditions": list,
    "seed": int,
    "alpha": float,
    "bootstrap_resamples": int,
    "max_steps": int,
    "max_tokens": int,
    "bash_timeout_seconds": int,
    "max_output_chars": int,
    "sandbox": str,
    "text_tool_instructions_in": str,
    "unparseable_reply": dict,
}


def load_experiment(path=None) -> dict:
    path = Path(path or os.environ.get("SANDBAG_EXPERIMENT") or ROOT / "experiment.yaml")
    settings = yaml.safe_load(path.read_text())

    for name, kind in REQUIRED.items():
        if name not in settings:
            raise ValueError(f"experiment.yaml is missing '{name}'")
        if not isinstance(settings[name], kind):
            raise ValueError(f"'{name}' must be a {kind.__name__}, got {settings[name]!r}")

    if settings["conditions"] != ["sandbag", "counterfactual"]:
        raise ValueError("conditions must be [sandbag, counterfactual]")
    if settings["sandbox"] not in ("local", "docker"):
        raise ValueError("sandbox must be 'local' or 'docker'")
    if settings["text_tool_instructions_in"] not in ("system", "user"):
        raise ValueError("text_tool_instructions_in must be 'system' or 'user'")
    if not 0 < settings["alpha"] < 1:
        raise ValueError("alpha must be between 0 and 1")
    for name in ("runs_per_condition", "max_steps", "max_tokens", "bash_timeout_seconds"):
        if settings[name] < 1:
            raise ValueError(f"'{name}' must be at least 1")

    reply = settings["unparseable_reply"]
    if reply.get("mode") not in ("reminder", "repair"):
        raise ValueError("unparseable_reply.mode must be 'reminder' or 'repair'")
    if reply["mode"] == "repair" and not reply.get("repair_model"):
        raise ValueError("unparseable_reply.repair_model is required when mode is 'repair'")

    return settings