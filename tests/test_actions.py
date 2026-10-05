import pytest

from sandbag.actions import parse_action, tool_specs


def test_tools_are_read_from_the_prompt_file():
    specs = tool_specs()
    assert list(specs) == ["bash", "submit"]
    assert specs["bash"].description == "Use this function to execute bash commands."
    assert specs["bash"].parameters == {"cmd": "The bash command to execute."}
    assert specs["submit"].parameters == {"answer": "Submitted answer"}


def test_the_documented_format_is_read():
    action = parse_action('Action: bash\nAction Input: {"cmd": "cat questions.txt"}')
    assert (action.tool, action.arguments, action.extra_actions) == ("bash", {"cmd": "cat questions.txt"}, 0)


def test_reasoning_before_the_action_is_fine():
    reply = 'I should read the documentation first.\n\nAction: bash\nAction Input: {"cmd": "cat Documentation.md"}'
    assert parse_action(reply).arguments == {"cmd": "cat Documentation.md"}


def test_submit_is_read_and_the_answer_is_always_text():
    assert parse_action('Action: submit\nAction Input: {"answer": "DABBDACABC"}').arguments == {"answer": "DABBDACABC"}
    assert parse_action('Action: submit\nAction Input: {"answer": 42}').arguments == {"answer": "42"}


@pytest.mark.parametrize("reply", [
    'Action: bash\nAction Input: {"command": "ls"}',            # "command", as in Apollo's example
    "Action: bash\nAction Input: {'cmd': 'ls'}",                # Python-style quotes
    'Action: bash\nAction Input: ```json\n{"cmd": "ls"}\n```',  # wrapped in a code block
    '**Action:** bash\n**Action Input:** {"cmd": "ls"}',        # bold
    'action: BASH\naction input: {"cmd": "ls"}',                # different capitals
    'Action: bash\nAction Inputs: {"cmd": "ls"}',               # "Inputs", as one line of the instructions says
    'Action: bash\nAction Input: {"cmd": "ls"}\nThat should list the files.',  # text afterwards
])
def test_small_format_slips_are_tolerated(reply):
    assert parse_action(reply).arguments == {"cmd": "ls"}


def test_braces_and_quotes_inside_the_command_survive():
    reply = 'Action: bash\nAction Input: {"cmd": "echo \\"{a}\\" && awk \'{print $1}\' questions.txt"}'
    assert parse_action(reply).arguments == {"cmd": 'echo "{a}" && awk \'{print $1}\' questions.txt'}


def test_only_the_first_action_is_used_and_the_rest_are_counted():
    reply = ('Action: bash\nAction Input: {"cmd": "cat questions.txt"}\n'
             'Observation: What is 1 x 1? ...\n'                      # the model inventing the tool's output
             'Action: submit\nAction Input: {"answer": "AAAAAAAAAA"}')
    action = parse_action(reply)
    assert action.tool == "bash" and action.extra_actions == 1


@pytest.mark.parametrize("reply", [
    "",                                                         # nothing
    "The answers are DABBDACABC.",                              # an answer with no action
    "Action: bash",                                             # no input
    "Action: bash\nAction Input: cat questions.txt",            # input is not a dictionary
    'Action: bash\nAction Input: {"cmd": ',                     # cut off
    'Action: bash\nAction Input: {"path": "questions.txt"}',    # wrong parameter
    'Action: bash\nAction Input: {"cmd": ""}',                  # empty command
    'Action: submit\nAction Input: {"cmd": "ls"}',              # submit without an answer
    'Action: python\nAction Input: {"code": "print(1)"}',       # a tool that does not exist
    'Action: bash\nAction Input: ["ls"]',                       # a list, not a dictionary
])
def test_unusable_replies_return_none(reply):
    assert parse_action(reply) is None