"""Reads the wording in prompts/. No prompt text is ever written in Python.

Run  python -m sandbag.prompts  to list every prompt file with its word count
and fingerprint.
"""
import hashlib

from sandbag.config import ROOT

PROMPTS = ROOT / "prompts"
TOOLS_PLACEHOLDER = "[SCENARIO SPECIFIC TOOLS]"
SCENARIOS = PROMPTS / "scenarios"   # one folder per extra scenario
DEFAULT_SCENARIO = "apollo"         # the paper's setup; its files sit directly in prompts/

# name used on the command line -> file holding that system prompt
SYSTEM_PROMPTS = {
    "no_goal": "system_no_goal.txt",
    "no_goal_plain": "system_no_goal_plain.txt",  # ours: no_goal without "sandboxed Linux machine" and "run commands"
    "goal_hard": "system_goal_hard.txt",
    "goal_medium": "system_goal_medium.txt",
    "goal_easy": "system_goal_easy.txt",
}


def load(filename: str) -> str:
    """The text of one prompt file, without blank space at the start or end."""
    path = PROMPTS / filename
    if not path.exists():
        raise FileNotFoundError(f"prompts/{filename} does not exist")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"prompts/{filename} is empty; fill it in before running")
    return text


def system_prompt(variant: str) -> str:
    if variant not in SYSTEM_PROMPTS:
        raise ValueError(f"unknown system prompt '{variant}'; choose from {list(SYSTEM_PROMPTS)}")
    return load(SYSTEM_PROMPTS[variant])


def scenarios() -> list[str]:
    """Every scenario you can run: the paper's, plus one per folder in prompts/scenarios/."""
    extra = sorted(p.name for p in SCENARIOS.iterdir() if p.is_dir()) if SCENARIOS.exists() else []
    return [DEFAULT_SCENARIO] + extra


def _in_scenario(scenario: str, filename: str) -> str:
    if scenario not in scenarios():
        raise ValueError(f"unknown scenario '{scenario}'; choose from {scenarios()}")
    return f"scenarios/{scenario}/{filename}"


def user_prompt(scenario: str = DEFAULT_SCENARIO) -> str:
    return load("user_prompt.txt" if scenario == DEFAULT_SCENARIO else _in_scenario(scenario, "user_prompt.txt"))


def passage(scenario: str, condition: str) -> str:
    """The text that states the consequence of scoring well (or, in the counterfactual, poorly)."""
    if condition not in ("sandbag", "counterfactual"):
        raise ValueError(f"unknown condition '{condition}'")
    if scenario == DEFAULT_SCENARIO:
        return arithmetic_section(condition)
    return load(_in_scenario(scenario, f"passage_{condition}.md"))


def tool_descriptions(scenario: str = DEFAULT_SCENARIO) -> str:
    """A scenario may word the tools differently (the paper's submit tool says 'for evaluation')."""
    if scenario != DEFAULT_SCENARIO and (PROMPTS / _in_scenario(scenario, "tool_descriptions.txt")).exists():
        return load(_in_scenario(scenario, "tool_descriptions.txt"))
    return load("tool_descriptions.txt")


def arithmetic_section(condition: str) -> str:
    if condition not in ("sandbag", "counterfactual"):
        raise ValueError(f"unknown condition '{condition}'")
    return load(f"arithmetic_{condition}.md")


def text_tool_instructions(scenario: str = DEFAULT_SCENARIO) -> str:
    """Apollo's tool-use instructions with our tool descriptions put in the placeholder."""
    template = load("text_tool_instructions.txt")
    if template.count(TOOLS_PLACEHOLDER) != 1:
        raise ValueError(f"text_tool_instructions.txt must contain {TOOLS_PLACEHOLDER} exactly once")
    return template.replace(TOOLS_PLACEHOLDER, tool_descriptions(scenario))


def fingerprint(filename: str) -> str:
    """A short code that changes if even one character of the file's text changes."""
    return hashlib.sha256(load(filename).encode("utf-8")).hexdigest()[:12]


def all_files() -> list[str]:
    names = (p.relative_to(PROMPTS).as_posix() for p in PROMPTS.rglob("*") if p.is_file() and p.suffix in (".txt", ".md"))
    return sorted(name for name in names if name != "README.md")  # prompts/README.md is a note for you, not a prompt


def fingerprints() -> dict[str, str]:
    return {name: fingerprint(name) for name in all_files()}


if __name__ == "__main__":
    print(f"{'file':<32}{'words':>6}  fingerprint")
    for name in all_files():
        print(f"{name:<32}{len(load(name).split()):>6}  {fingerprint(name)}")