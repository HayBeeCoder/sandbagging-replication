"""Reads the wording in prompts/. No prompt text is ever written in Python.

Run  python -m sandbag.prompts  to list every prompt file with its word count
and fingerprint.
"""
import hashlib

from sandbag.config import ROOT

PROMPTS = ROOT / "prompts"
TOOLS_PLACEHOLDER = "[SCENARIO SPECIFIC TOOLS]"

# name used on the command line -> file holding that system prompt
SYSTEM_PROMPTS = {
    "no_goal": "system_no_goal.txt",
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


def user_prompt() -> str:
    return load("user_prompt.txt")


def arithmetic_section(condition: str) -> str:
    if condition not in ("sandbag", "counterfactual"):
        raise ValueError(f"unknown condition '{condition}'")
    return load(f"arithmetic_{condition}.md")


def text_tool_instructions() -> str:
    """Apollo's tool-use instructions with our tool descriptions put in the placeholder."""
    template = load("text_tool_instructions.txt")
    if template.count(TOOLS_PLACEHOLDER) != 1:
        raise ValueError(f"text_tool_instructions.txt must contain {TOOLS_PLACEHOLDER} exactly once")
    return template.replace(TOOLS_PLACEHOLDER, load("tool_descriptions.txt"))


def fingerprint(filename: str) -> str:
    """A short code that changes if even one character of the file's text changes."""
    return hashlib.sha256(load(filename).encode("utf-8")).hexdigest()[:12]


def all_files() -> list[str]:
    return sorted(p.name for p in PROMPTS.iterdir() if p.suffix in (".txt", ".md") and p.name != "README.md")


def fingerprints() -> dict[str, str]:
    return {name: fingerprint(name) for name in all_files()}


if __name__ == "__main__":
    print(f"{'file':<32}{'words':>6}  fingerprint")
    for name in all_files():
        print(f"{name:<32}{len(load(name).split()):>6}  {fingerprint(name)}")