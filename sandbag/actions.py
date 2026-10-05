"""Reads tool requests out of a model's text reply (Apollo's Action / Action Input format).

Pure logic: no model and no sandbox here, so every case can be tested directly.
"""
import ast
import json
import re
from dataclasses import dataclass

from sandbag import prompts


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, str]  # parameter name -> its description


@dataclass
class ParsedAction:
    tool: str          # "bash" or "submit"
    arguments: dict    # {"cmd": "..."} or {"answer": "..."}
    extra_actions: int # how many further Action blocks the reply contained (we act on the first only)


def tool_specs() -> dict[str, ToolSpec]:
    """The tools, read from prompts/tool_descriptions.txt so both tool modes use the same wording."""
    specs = {}
    for block in re.split(r"\n\s*\n", prompts.load("tool_descriptions.txt")):
        lines = [line.strip() for line in block.strip().splitlines()]
        name, description = lines[0].split(":", 1)
        parameters = {}
        for line in lines[1:]:
            found = re.fullmatch(r"- (\w+) \(string\): (.+)", line)
            if found:
                parameters[found.group(1)] = found.group(2)
        specs[name.strip()] = ToolSpec(name.strip(), description.strip(), parameters)
    return specs


# "Action: bash" then "Action Input: ..." on the next line. Bold or code marks around them are tolerated.
ACTION = re.compile(r"[*`]*Action[*`]*\s*:[*`\s]*(\w+)[*`]*[ \t]*\n\s*[*`]*Action Inputs?[*`]*\s*:[*`]*", re.I)


def _read_dictionary(text: str):
    """The first {...} in text, as a Python dict; None if there is none or it cannot be read."""
    start = text.find("{")
    if start == -1:
        return None
    try:  # proper JSON: {"cmd": "ls"}
        value, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError:
        # Python-style quotes: {'cmd': 'ls'}. Find the matching closing brace first.
        depth = 0
        for end, char in enumerate(text[start:], start):
            depth += (char == "{") - (char == "}")
            if depth == 0:
                break
        else:
            return None
        try:
            value = ast.literal_eval(text[start:end + 1])
        except (ValueError, SyntaxError):
            return None
    return value if isinstance(value, dict) else None


def parse_action(reply: str) -> ParsedAction | None:
    """The tool request in a reply, or None if the reply does not contain a usable one."""
    found = list(ACTION.finditer(reply))
    if not found:
        return None
    first = found[0]
    tool = first.group(1).lower()
    end = found[1].start() if len(found) > 1 else len(reply)
    arguments = _read_dictionary(reply[first.end():end])
    if arguments is None:
        return None

    if tool == "bash":
        # Apollo's instructions show "command" in an example while the tool itself uses "cmd"; accept both.
        cmd = arguments.get("cmd", arguments.get("command"))
        if not isinstance(cmd, str) or not cmd.strip():
            return None
        return ParsedAction("bash", {"cmd": cmd}, len(found) - 1)
    if tool == "submit":
        if "answer" not in arguments:
            return None
        return ParsedAction("submit", {"answer": str(arguments["answer"])}, len(found) - 1)
    return None  # a tool that does not exist