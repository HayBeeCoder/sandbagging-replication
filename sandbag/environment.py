"""Builds the two files the model finds in its sandbox: questions.txt and Documentation.md."""
from sandbag import prompts
from sandbag.questions import load_questions_text

SECTION_PLACEHOLDER = "[ARITHMETIC SECTION]"


def documentation(condition: str) -> str:
    """Documentation.md for one condition: our template with that condition's arithmetic section."""
    template = prompts.load("documentation_template.md")
    if template.count(SECTION_PLACEHOLDER) != 1:
        raise ValueError(f"documentation_template.md must contain {SECTION_PLACEHOLDER} exactly once")
    return template.replace(SECTION_PLACEHOLDER, prompts.arithmetic_section(condition)) + "\n"


def sandbox_files(condition: str) -> dict[str, str]:
    """File name -> contents, for everything placed in the sandbox for one run."""
    return {
        "questions.txt": load_questions_text(),
        "Documentation.md": documentation(condition),
    }