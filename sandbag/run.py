"""Runs one experiment: one model, one system prompt, both conditions.

    python -m sandbag.run mock_sandbagger
    python -m sandbag.run llama405b_runpod --system goal_hard
    python -m sandbag.run mock_honest --runs 5          # a quick try with fewer runs
"""
import argparse
import re
import subprocess
import sys
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from inspect_ai import eval
from inspect_ai.log import EvalLog

from sandbag import prompts
from sandbag.config import ROOT, load_experiment
from sandbag.registry import build_model, get_spec
from sandbag.task import sandbagging


def code_version() -> str:
    """The git commit the code is at, marked if there are changes that were never committed."""
    def git(*arguments):
        return subprocess.run(["git", *arguments], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    commit = git("rev-parse", "--short", "HEAD") or "unknown"
    return commit + (" + uncommitted changes" if git("status", "--porcelain") else "")


def new_run_folder(parent: Path, name: str | None) -> Path:
    """A folder no other run has: the UTC time it started, plus the name you gave it."""
    label = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    if name:
        label += "_" + re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()
    folder, attempt = parent / label, 1
    while folder.exists():  # two runs started in the same second
        attempt += 1
        folder = parent / f"{label}_{attempt}"
    return folder


def experiment_folder(system: str, scenario: str) -> str:
    """Where an experiment's runs are filed: no_goal for the paper's scenario, no_goal__<scenario> for others."""
    return system if scenario == prompts.DEFAULT_SCENARIO else f"{system}__{scenario}"


def run_experiment(model_key: str, system: str = "no_goal", runs: int | None = None,
                   results: Path | None = None, display: str = "plain",
                   name: str | None = None, note: str = "", scenario: str = prompts.DEFAULT_SCENARIO) -> EvalLog:
    spec = get_spec(model_key)
    settings = load_experiment()
    task = sandbagging(system=system, tool_mode=spec.tool_mode, runs=runs, scenario=scenario)
    log_dir = new_run_folder((results or ROOT / "results") / model_key / experiment_folder(system, scenario), name)
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
            "scenario": scenario,
            "tool_mode": spec.tool_mode,
            "settings": settings,
            "prompt_fingerprints": prompts.fingerprints(),  # also refuses to start if a prompt file is empty
            "inspect_version": version("inspect_ai"),
            "run_id": log_dir.name,                  # the folder this run lives in
            "name": name or "",
            "note": note,                            # why this run was done, in your words
            "code_version": code_version(),
            "command": " ".join(sys.argv),
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
    parser.add_argument("--scenario", default=prompts.DEFAULT_SCENARIO, choices=prompts.scenarios(),
                        help="apollo is the paper's setup; the others do not tell the model it is being tested")
    parser.add_argument("--name", help="a short label added to the run's folder name, e.g. pilot or full")
    parser.add_argument("--note", default="", help="a sentence on why you are doing this run; saved with the results")
    args = parser.parse_args()

    log = run_experiment(args.model_key, args.system, args.runs, name=args.name, note=args.note, scenario=args.scenario)
    if log.status != "success":
        sys.exit(f"\nThe run did not finish: {log.status}. {log.error.message if log.error else ''}\nLog: {log.location}")

    print(f"\n{args.model_key} · {args.system} · scenario {args.scenario} · {get_spec(args.model_key).role}")
    print(f"{'condition':<16}{'runs':>5}{'accuracy':>10}{'submitted':>11}{'read docs':>11}{'sandbag flag':>14}")
    for condition, row in sorted(summarise(log).items(), reverse=True):  # sandbag first
        print(f"{condition:<16}{row['runs']:>5}{row['accuracy']:>10.3f}{row['submitted']:>11}"
              f"{row['read_documentation']:>11}{row['sandbagging_flag']:>14}")
    from sandbag.analyze import analyze, folder_of  # imported here because analyze is not needed to start a run
    folder = folder_of(log)
    analyze(folder)
    print(f"\nEverything for this run is in: {folder}")
    print("  summary.md  runs.csv  and the .eval log")
    print(f"Read the transcripts with: inspect view --log-dir {folder} --port 7575")
