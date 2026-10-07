"""Builds the files the model finds in its sandbox, for one condition of one scenario."""
from sandbag import prompts
from sandbag.questions import load_questions_text

SECTION_PLACEHOLDER = "[ARITHMETIC SECTION]"
PASSAGE_PLACEHOLDER = "[PASSAGE]"      # in a scenario's files: where the consequence text goes
QUESTIONS_PLACEHOLDER = "[QUESTIONS]"  # in a scenario's files: where the ten questions go
BASELINE = "baseline"                  # a control condition: the same files with no consequence text at all


def documentation(condition: str) -> str:
    """Documentation.md for one condition: our template with that condition's arithmetic section."""
    template = prompts.load("documentation_template.md")
    if template.count(SECTION_PLACEHOLDER) != 1:
        raise ValueError(f"documentation_template.md must contain {SECTION_PLACEHOLDER} exactly once")
    if condition == BASELINE:  # leave out the section and the heading above it
        return template[:template.rindex("\n## ", 0, template.index(SECTION_PLACEHOLDER))].rstrip() + "\n"
    return template.replace(SECTION_PLACEHOLDER, prompts.arithmetic_section(condition)) + "\n"


def sandbox_files(condition: str, scenario: str = prompts.DEFAULT_SCENARIO) -> dict[str, str]:
    """File name -> contents, for everything placed in the sandbox for one run."""
    if scenario == prompts.DEFAULT_SCENARIO:
        return {
            "questions.txt": load_questions_text(),
            "Documentation.md": documentation(condition),
        }
    # Any other scenario: every file under prompts/scenarios/<name>/files/, with the two placeholders filled in.
    folder = prompts.SCENARIOS / scenario / "files"
    names = sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())
    templates = {name: prompts.load(f"scenarios/{scenario}/files/{name}") for name in names}
    for placeholder in (PASSAGE_PLACEHOLDER, QUESTIONS_PLACEHOLDER):
        if sum(text.count(placeholder) for text in templates.values()) != 1:
            raise ValueError(f"scenario '{scenario}': its files must contain {placeholder} exactly once")
    text_for = {QUESTIONS_PLACEHOLDER: load_questions_text().strip()}
    if condition != BASELINE:
        text_for[PASSAGE_PLACEHOLDER] = prompts.passage(scenario, condition)
    files = {}
    for name, text in templates.items():
        if condition == BASELINE:
            # Drop the line that holds the consequence text; a file that held nothing else is not there at all.
            text = "\n".join(line for line in text.splitlines() if line.strip() != PASSAGE_PLACEHOLDER).strip()
            if not text:
                continue
        for placeholder, replacement in text_for.items():
            text = text.replace(placeholder, replacement)
        files[name] = text + "\n"
    return files


def passage_marker(scenario: str = prompts.DEFAULT_SCENARIO) -> str:
    """Words that appear only in the consequence text; seeing them in a command's output means the model saw it."""
    first_lines = {prompts.passage(scenario, condition).splitlines()[0] for condition in ("sandbag", "counterfactual")}
    if len(first_lines) != 1:
        raise ValueError(f"scenario '{scenario}': both passage files must start with the same line")
    return first_lines.pop().lstrip("# ").strip()
