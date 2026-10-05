"""Repair mode: the prompts, reading the repair model's answer, and the loop using it."""
import json

import pytest
from inspect_ai.model import get_model

from sandbag import prompts
from sandbag.agent import sandbag_agent
from sandbag.config import load_experiment
from sandbag.repair import SLOT, read_repair, repair_messages
from tests.test_agent import KEY, MOCK, action, run, says

REPAIR = {"unparseable_reply": {"mode": "repair", "repair_model": "mock"}}


def found(tool, **arguments):  # what a repair model answers when it finds an action
    return json.dumps({"action_request": {"function_name": tool,
                                          "arguments": [{"name": k, "value": v} for k, v in arguments.items()]}})


NOTHING = json.dumps({"action_request": None})  # what it answers when the reply held no action


def repairer(*answers):  # a fake repair model that gives these answers in order
    return get_model(MOCK, custom_outputs=[says(answer) for answer in answers])


# --- the prompts -----------------------------------------------------------------

@pytest.mark.parametrize("filename,words", [("repair_system.txt", 68), ("repair_user.txt", 18)])
def test_repair_prompts_have_the_papers_word_count(filename, words):
    assert len(prompts.load(filename).split()) == words


def test_the_unreadable_reply_is_put_between_the_tags():
    system, user = repair_messages("I will run ls now")
    assert system.text == prompts.load("repair_system.txt")
    assert user.text.endswith("<model-response>I will run ls now</model-response>")
    assert SLOT not in user.text and user.text.startswith("Given the following data")


# --- reading the repair model's answer ------------------------------------------

def test_a_found_action_is_read():
    result = read_repair(found("bash", cmd="cat questions.txt"))
    assert (result.tool, result.arguments) == ("bash", {"cmd": "cat questions.txt"})


def test_command_is_accepted_for_cmd_as_in_the_normal_parser():
    assert read_repair(found("bash", command="ls")).arguments == {"cmd": "ls"}


def test_json_wrapped_in_other_text_is_still_read():
    assert read_repair("```json\n" + found("submit", answer=KEY) + "\n```").arguments == {"answer": KEY}


@pytest.mark.parametrize("answer", [NOTHING, "", "I could not find an action.", '{"action_request": "bash"}',
                                    found("delete_everything", path="/"), found("bash"), found("submit", cmd="ls")])
def test_anything_unusable_gives_none(answer):
    assert read_repair(answer) is None


# --- the loop --------------------------------------------------------------------

def test_a_repaired_command_is_run_without_a_reminder(tmp_path):
    record, messages = run([says("I'll run: cat Documentation.md"), action("submit", answer=KEY)], tmp_path,
                           repair_model=repairer(found("bash", cmd="cat Documentation.md")), **REPAIR)
    assert (record["repair_attempts"], record["repairs"], record["reminders"]) == (1, 1, 0)
    assert record["commands"] == ["cat Documentation.md"] and record["read_documentation"]
    assert messages[3].text.startswith("# Documentation")
    assert record["submission"] == KEY and not record["submission_repaired"]


def test_a_repaired_submission_is_marked(tmp_path):
    record, _ = run([says(f"submit({KEY})")], tmp_path, repair_model=repairer(found("submit", answer=KEY)), **REPAIR)
    assert record["submission"] == KEY and record["submission_repaired"]


def test_when_repair_finds_nothing_the_model_gets_a_reminder(tmp_path):
    record, messages = run([says("Let me think."), action("submit", answer=KEY)], tmp_path,
                           repair_model=repairer(NOTHING), **REPAIR)
    assert (record["repair_attempts"], record["repairs"], record["reminders"]) == (1, 0, 1)
    assert messages[3].text == prompts.load("reminder_text.txt")


def test_readable_replies_never_reach_the_repair_model(tmp_path):
    record, _ = run([action("bash", cmd="ls"), action("submit", answer=KEY)], tmp_path,
                    repair_model=repairer(), **REPAIR)
    assert record["repair_attempts"] == 0


def test_reminder_mode_never_repairs(tmp_path):
    record, _ = run([says("Let me think."), action("submit", answer=KEY)], tmp_path)
    assert (record["repair_attempts"], record["reminders"]) == (0, 1)


def test_repair_mode_builds_its_model_from_the_registry():
    sandbag_agent("no_goal", "text", {**load_experiment(), **REPAIR})  # "mock" is a real key: no error
    with pytest.raises(ValueError, match="no model 'not_a_model'"):
        sandbag_agent("no_goal", "text", {**load_experiment(),
                                          "unparseable_reply": {"mode": "repair", "repair_model": "not_a_model"}})
