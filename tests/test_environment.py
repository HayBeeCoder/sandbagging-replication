import re

import pytest

from sandbag import environment, prompts
from sandbag.questions import load_answer_key

SANDBAG = environment.documentation("sandbag")
COUNTERFACTUAL = environment.documentation("counterfactual")


def test_each_version_contains_its_arithmetic_section_word_for_word():
    assert prompts.arithmetic_section("sandbag") in SANDBAG
    assert prompts.arithmetic_section("counterfactual") in COUNTERFACTUAL


def test_the_two_documents_differ_in_exactly_two_words():
    a, b = SANDBAG.split(), COUNTERFACTUAL.split()
    assert len(a) == len(b)
    assert [(x, y) for x, y in zip(a, b) if x != y] == [("well", "poorly"), ("higher", "lower")]


def test_the_two_documents_have_identical_layout():
    """Same line breaks and spacing everywhere, not just the same words."""
    blank = lambda text: re.sub(r"\S", "x", text.replace("poorly", "well").replace("lower", "higher"))
    assert blank(SANDBAG) == blank(COUNTERFACTUAL)


def test_no_placeholder_is_left_behind():
    for doc in (SANDBAG, COUNTERFACTUAL):
        assert "[" not in doc and "]" not in doc


def test_the_format_example_is_valid_but_not_the_answer_key():
    key = load_answer_key()
    examples = re.findall(r"^[ABCD](?:,[ABCD]){9}$", SANDBAG, flags=re.M)
    assert len(examples) == 1
    matches = sum(x == y for x, y in zip(examples[0].replace(",", ""), key))
    assert matches == 0  # copying the example must not score well


def test_sandbox_holds_exactly_two_files_and_no_answer_key():
    for condition in ("sandbag", "counterfactual"):
        files = environment.sandbox_files(condition)
        assert sorted(files) == ["Documentation.md", "questions.txt"]
        assert load_answer_key() not in "".join(files.values())


def test_questions_are_identical_in_both_conditions():
    assert environment.sandbox_files("sandbag")["questions.txt"] == environment.sandbox_files("counterfactual")["questions.txt"]


def test_unknown_condition_is_refused():
    with pytest.raises(ValueError):
        environment.documentation("control")