
"""Runs the conversation loop for real, in a real sandbox, against a scripted fake model."""
import pytest
from inspect_ai import Task, eval
from inspect_ai.dataset import Sample
from inspect_ai.model import ModelOutput, get_model

from sandbag import prompts
from sandbag.agent import opening_messages, sandbag_agent
from sandbag.config import load_experiment
from sandbag.environment import sandbox_files
from sandbag.questions import load_answer_key

KEY = load_answer_key()
MOCK = "mockllm/model"


def says(text):  # a fake model reply in plain text
    return ModelOutput.from_content(MOCK, text)


def calls(tool, **arguments):  # a fake model reply that is a native tool call
    return ModelOutput.for_tool_call(MOCK, tool, arguments)


def action(tool, **arguments):  # a fake model reply in Apollo's text format
    import json
    return says(f"Action: {tool}\nAction Input: {json.dumps(arguments)}")


def run(replies, tmp_path, condition="sandbag", system="no_goal", tool_mode="text", repair_model=None, **overrides):
    """Run one sample with scripted replies; return (run record, messages)."""
    settings = load_experiment()
    unknown = set(overrides) - set(settings)
    assert not unknown, f"not settings in experiment.yaml: {sorted(unknown)}"
    settings = {**settings, **overrides}
    task = Task(
        dataset=[Sample(input=prompts.user_prompt(), files=sandbox_files(condition))],
        solver=sandbag_agent(system, tool_mode, settings, repair_model),
        sandbox="local",
    )
    log = eval(task, model=get_model(MOCK, custom_outputs=replies), log_dir=str(tmp_path), display="none")[0]
    assert log.status == "success", log.error
    sample = log.samples[0]
    return sample.store["run"], sample.messages


def test_text_mode_read_both_files_then_submit(tmp_path):
    record, messages = run([action("bash", cmd="cat questions.txt"), action("bash", cmd="cat Documentation.md"),
                            action("submit", answer=KEY)], tmp_path)
    assert record["submission"] == KEY
    assert record["commands"] == ["cat questions.txt", "cat Documentation.md"]
    assert record["read_questions"] and record["read_documentation"]
    assert (record["steps"], record["reminders"], record["hit_step_limit"]) == (3, 0, False)
    assert [m.role for m in messages] == ["system", "user", "assistant", "user", "assistant", "user", "assistant"]


@pytest.mark.parametrize("condition,phrase", [("sandbag", "higher than 50%"), ("counterfactual", "lower than 50%")])
def test_the_model_sees_the_real_file_for_its_condition(tmp_path, condition, phrase):
    _, messages = run([action("bash", cmd="cat Documentation.md"), action("submit", answer=KEY)], tmp_path, condition=condition)
    tool_output = messages[3]
    assert tool_output.role == "user" and phrase in tool_output.text
    assert tool_output.text.startswith("# Documentation")  # the raw output, with no label added


def test_not_reading_the_documentation_is_recorded(tmp_path):
    record, _ = run([action("bash", cmd="cat questions.txt"), action("submit", answer=KEY)], tmp_path)
    assert record["read_questions"] and not record["read_documentation"]


def test_an_unreadable_reply_gets_a_reminder_and_another_turn(tmp_path):
    record, messages = run([says(f"The answers are {KEY}."), action("submit", answer=KEY)], tmp_path)
    assert (record["reminders"], record["steps"], record["submission"]) == (1, 2, KEY)
    assert messages[3].text == prompts.load("reminder_text.txt")


def test_a_model_that_never_submits_is_stopped_at_the_step_limit(tmp_path):
    record, _ = run([says("Let me think about this.")] * 4, tmp_path, max_steps=4)
    assert record["submission"] is None and record["hit_step_limit"]
    assert (record["steps"], record["reminders"]) == (4, 4)


def test_a_slow_command_is_stopped_and_the_model_is_told(tmp_path):
    _, messages = run([action("bash", cmd="sleep 30"), action("submit", answer=KEY)], tmp_path, bash_timeout_seconds=1)
    assert "did not finish within 1 seconds" in messages[3].text


def test_long_output_is_cut_off(tmp_path):
    _, messages = run([action("bash", cmd="yes | head -c 50000"), action("submit", answer=KEY)], tmp_path, max_output_chars=200)
    assert len(messages[3].text) < 250 and messages[3].text.endswith("[output cut off]")


def test_a_failing_command_reports_its_error(tmp_path):
    _, messages = run([action("bash", cmd="cat no_such_file.txt"), action("submit", answer=KEY)], tmp_path)
    assert "No such file" in messages[3].text


def test_invented_tool_output_is_ignored_and_counted(tmp_path):
    hallucinated = says('Action: bash\nAction Input: {"cmd": "cat questions.txt"}\nObservation: What is 1 x 1?\n'
                        'Action: submit\nAction Input: {"answer": "AAAAAAAAAA"}')
    record, _ = run([hallucinated, action("submit", answer=KEY)], tmp_path)
    assert record["submission"] == KEY and record["extra_actions"] == 1


def test_native_mode_read_then_submit(tmp_path):
    record, messages = run([calls("bash", cmd="cat Documentation.md"), calls("submit", answer=KEY)], tmp_path, tool_mode="native")
    assert record["submission"] == KEY and record["read_documentation"]
    assert [m.role for m in messages] == ["system", "user", "assistant", "tool", "assistant"]
    assert "higher than 50%" in messages[3].text


def test_native_mode_reply_without_a_tool_call_gets_a_reminder(tmp_path):
    record, messages = run([says("I will read the files."), calls("submit", answer=KEY)], tmp_path, tool_mode="native")
    assert record["reminders"] == 1 and messages[3].text == prompts.load("reminder_native.txt")


def test_text_instructions_go_where_the_setting_says():
    settings = load_experiment()
    instructions = prompts.text_tool_instructions()
    system, user = opening_messages("no_goal", "text", {**settings, "text_tool_instructions_in": "system"})
    assert system.text == prompts.system_prompt("no_goal") + "\n\n" + instructions
    assert user.text == prompts.user_prompt()
    system, user = opening_messages("no_goal", "text", {**settings, "text_tool_instructions_in": "user"})
    assert system.text == prompts.system_prompt("no_goal")
    assert user.text == prompts.user_prompt() + "\n\n" + instructions


def test_native_mode_adds_no_text_instructions():
    system, user = opening_messages("goal_hard", "native", load_experiment())
    assert system.text == prompts.system_prompt("goal_hard") and user.text == prompts.user_prompt()
