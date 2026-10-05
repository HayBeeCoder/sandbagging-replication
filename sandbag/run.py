"""Runs one experiment: one model, one system prompt, both conditions.

    python -m sandbag.run mock_sandbagger
    python -m sandbag.run llama405b_runpod --system goal_hard
    python -m sandbag.run mock_honest --runs 5          # a quick try with fewer runs
"""
import argparse
import sys
from importlib.metadata import version
from pathlib import Path

from inspect_ai import eval
from inspect_ai.log import EvalLog

from sandbag import prompts
from sandbag.config import ROOT, load_experiment
from sandbag.registry import build_model, get_spec
from sandbag.task import sandbagging


def run_experiment(model_key: str, system: str = "no_goal", runs: int | None = None,
                   results: Path | None = None, display: str = "plain") -> EvalLog:
    spec = get_spec(model_key)
    settings = load_experiment()
    task = sandbagging(system=system, tool_mode=spec.tool_mode, runs=runs)
    log_dir = (results or ROOT / "results") / model_key / system
    return eval(
        task,
        model=build_model(model_key),
        log_dir=str(log_dir),
        display=display,
        # Stored in the log, so every result can be traced to the exact wording and settings behind it.
        metadata={
            "model_key": model_key,
            "role": spec.role,                       # replication or new_measurement
            "system": system,
            "tool_mode": spec.tool_mode,
            "settings": settings,
            "prompt_fingerprints": prompts.fingerprints(),  # also refuses to start if a prompt file is empty
            "inspect_version": version("inspect_ai"),
        },
    )[0]


def summarise(log: EvalLog) -> dict[str, dict]:
    """Per condition: number of runs, mean accuracy, and how many runs did each thing."""
    summary = {}
    for sample in log.samples or []:
        details = next(iter(sample.scores.values())).metadata
        row = summary.setdefault(details["condition"], {"runs": 0, "accuracy": 0.0, "submitted": 0,
                                                        "read_documentation": 0, "sandbagging_flag": 0})
        row["runs"] += 1
        row["accuracy"] += details["accuracy"]
        for name in ("submitted", "read_documentation", "sandbagging_flag"):
            row[name] += bool(details[name])
    for row in summary.values():
        row["accuracy"] = row["accuracy"] / row["runs"]
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the sandbagging experiment for one model.")
    parser.add_argument("model_key", help="a key from models.yaml (list them with: python -m sandbag.registry)")
    parser.add_argument("--system", default="no_goal", choices=list(prompts.SYSTEM_PROMPTS))
    parser.add_argument("--runs", type=int, help="runs per condition; default is runs_per_condition in experiment.yaml")
    args = parser.parse_args()

    log = run_experiment(args.model_key, args.system, args.runs)
    if log.status != "success":
        sys.exit(f"\nThe run did not finish: {log.status}. {log.error.message if log.error else ''}\nLog: {log.location}")

    print(f"\n{args.model_key} · {args.system} · {get_spec(args.model_key).role}")
    print(f"{'condition':<16}{'runs':>5}{'accuracy':>10}{'submitted':>11}{'read docs':>11}{'sandbag flag':>14}")
    for condition, row in sorted(summarise(log).items(), reverse=True):  # sandbag first
        print(f"{condition:<16}{row['runs']:>5}{row['accuracy']:>10.3f}{row['submitted']:>11}"
              f"{row['read_documentation']:>11}{row['sandbagging_flag']:>14}")
    print(f"\nLog: {log.location}")
    print(f"Read the transcripts with: inspect view --log-dir {Path(log.location).parent} --port 7575")
