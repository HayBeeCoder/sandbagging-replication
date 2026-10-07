"""Make the tests match the request wording you chose, and tidy that wording (straight quotes, one ending)."""
from pathlib import Path

ENDING = "Don't write code to help you."
SCENARIOS = Path("prompts/scenarios")
TEST_EDITS = [
    ('''    assert "calculations.txt" in prompts.user_prompt("colleague_file")  # the earlier scenario does name them
''',
     '''    # Since 7 Oct 2026 these two use the same request, so they differ from colleague_folder only in where the note sits.
    assert prompts.user_prompt("colleague_file") == prompts.user_prompt("colleague_subfolder") == request


@pytest.mark.parametrize("scenario", OURS)
def test_every_request_of_ours_ends_by_asking_for_no_code(scenario):
    request = prompts.user_prompt(scenario)
    assert request.endswith("Don't write code to help you.") and request.count("code") == 1
    assert "rather than" not in request and "Thanks" not in request
'''),
]

tests = Path("tests/test_scenarios.py")
text = tests.read_text()
for old, new in TEST_EDITS:
    assert text.count(old) == 1, f"expected exactly one in tests/test_scenarios.py:\n{old}"

def tidy(request: str) -> str:
    for curly, straight in (("\u2019", "'"), ("\u2018", "'"), ("\u201c", '"'), ("\u201d", '"')):
        request = request.replace(curly, straight)
    for phrase in (" rather than writing code", " rather than with a script"):
        request = request.replace(phrase, "")
    request = request.strip().removesuffix("Thanks!").strip()
    return request if request.endswith(ENDING) else f"{request} {ENDING}"

def write(scenario: str, request: str) -> None:
    file = SCENARIOS / scenario / "user_prompt.txt"
    if file.read_text().strip() != request:
        file.write_text(request + "\n")
        print("changed", file)

for folder in sorted(p for p in SCENARIOS.iterdir() if p.is_dir()):
    write(folder.name, tidy((folder / "user_prompt.txt").read_text()))
# The scenarios you said share one request: copy it, so they cannot drift apart.
shared = (SCENARIOS / "colleague_folder" / "user_prompt.txt").read_text().strip()
for scenario in ("colleague_file", "colleague_subfolder"):
    write(scenario, shared)
if (SCENARIOS / "colleague_memo_reason").is_dir():
    write("colleague_memo_reason", (SCENARIOS / "colleague_memo" / "user_prompt.txt").read_text().strip())

for old, new in TEST_EDITS:
    text = text.replace(old, new)
tests.write_text(text)
print("updated tests/test_scenarios.py\n")
for folder in sorted(p for p in SCENARIOS.iterdir() if p.is_dir()):
    print(f"== {folder.name}\n{(folder / 'user_prompt.txt').read_text()}")
