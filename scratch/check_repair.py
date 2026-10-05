"""Sends a few unreadable replies through the real repair code and shows what comes back.

    python -m scratch.check_repair                      # uses gpt4o_mini_openrouter
    python -m scratch.check_repair some_other_model_key
"""
import asyncio
import sys

from sandbag.questions import load_answer_key
from sandbag.registry import build_model
from sandbag.repair import repair

KEY = load_answer_key()

# (an unreadable reply, what a good repair model should make of it)
CASES = [
    ("I'll run this command now: cat Documentation.md", "bash {'cmd': 'cat Documentation.md'}"),
    ("Let me look at the questions.\n\n```bash\ncat questions.txt\n```", "bash {'cmd': 'cat questions.txt'}"),
    (f"My final answer.\nsubmit(answer=\"{KEY}\")", f"submit {{'answer': '{KEY}'}}"),
    ("Let me think about how to approach this task before doing anything.", "nothing"),
    (f"I think the answers are {KEY}, but let me double-check question 3 first.", "nothing"),
]


async def main(model_key: str) -> None:
    model = build_model(model_key)
    print(f"Repair model: {model_key}\n")
    agreed = 0
    for reply, expected in CASES:
        action = await repair(reply, model)
        got = f"{action.tool} {action.arguments}" if action else "nothing"
        agreed += got == expected
        print(f"reply:    {reply!r}\nexpected: {expected}\ngot:      {got}   {'ok' if got == expected else '<-- differs'}\n")
    print(f"{agreed} of {len(CASES)} as expected")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "gpt4o_mini_openrouter"))
