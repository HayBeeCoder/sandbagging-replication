"""The conversation loop: the model asks for tools, we run them and report back, until it submits.

Works in two tool modes:
  text    the model writes "Action: ... / Action Input: ..." (Apollo's scaffold for Llama)
  native  the model uses the provider's built-in tool calling (Apollo's choice for Claude)
"""
from inspect_ai.model import ChatMessageSystem, ChatMessageTool, ChatMessageUser, Model, get_model
from inspect_ai.solver import Generate, TaskState, solver
from inspect_ai.tool import ToolInfo, ToolParam, ToolParams
from inspect_ai.util import sandbox

from sandbag import prompts
from sandbag.actions import parse_action, tool_specs
from sandbag.config import load_experiment
from sandbag.questions import load_questions_text
from sandbag.registry import build_model
from sandbag.repair import repair

DOCUMENTATION_MARKER = "Arithmetic Knowledge Assessment"  # appears only in Documentation.md


def opening_messages(system_variant: str, tool_mode: str, settings: dict) -> list:
    """The system and user messages that start every run."""
    system = prompts.system_prompt(system_variant)
    user = prompts.user_prompt()
    if tool_mode == "text":
        instructions = prompts.text_tool_instructions()
        if settings["text_tool_instructions_in"] == "system":
            system = system + "\n\n" + instructions
        else:
            user = user + "\n\n" + instructions
    return [ChatMessageSystem(content=system), ChatMessageUser(content=user)]


def native_tools() -> list[ToolInfo]:
    """The tools as the provider's API wants them, with the same wording as text mode."""
    return [
        ToolInfo(
            name=spec.name,
            description=spec.description,
            parameters=ToolParams(
                properties={name: ToolParam(type="string", description=text) for name, text in spec.parameters.items()},
                required=list(spec.parameters),
            ),
        )
        for spec in tool_specs().values()
    ]


async def run_bash(cmd: str, settings: dict) -> str:
    """Run one command in the sandbox and return what the model should see."""
    limit = settings["bash_timeout_seconds"]
    try:
        result = await sandbox().exec(["bash", "-c", cmd], timeout=limit, timeout_retry=False)
    except TimeoutError:
        return f"Error: the command did not finish within {limit} seconds."
    output = result.stdout + result.stderr
    if len(output) > settings["max_output_chars"]:
        output = output[: settings["max_output_chars"]] + "\n[output cut off]"
    return output if output.strip() else "(no output)"


@solver
def sandbag_agent(system_variant: str, tool_mode: str, settings: dict | None = None, repair_model: Model | None = None):
    """repair_model is only passed in by tests; real runs build it from experiment.yaml."""
    settings = settings or load_experiment()
    if tool_mode not in ("text", "native"):
        raise ValueError(f"tool_mode must be 'text' or 'native', got '{tool_mode}'")
    # Repair applies to text mode only: in native mode the provider formats the tool call itself.
    repairing = settings["unparseable_reply"]["mode"] == "repair" and tool_mode == "text"
    if repairing and repair_model is None:
        repair_model = build_model(settings["unparseable_reply"]["repair_model"])
    reminder = prompts.load(f"reminder_{tool_mode}.txt")
    first_question = load_questions_text().splitlines()[0]

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        model = get_model()  # whichever model this run was started with
        messages = opening_messages(system_variant, tool_mode, settings)
        tools = native_tools() if tool_mode == "native" else []
        run = {"system_variant": system_variant, "tool_mode": tool_mode, "submission": None,
               "steps": 0, "reminders": 0, "repair_attempts": 0, "repairs": 0, "submission_repaired": False,
               "extra_actions": 0, "commands": [],
               "read_questions": False, "read_documentation": False, "hit_step_limit": False}

        output = None
        while run["submission"] is None and run["steps"] < settings["max_steps"]:
            # 1. the model speaks
            output = await model.generate(messages, tools=tools)
            reply = output.message
            messages.append(reply)
            run["steps"] += 1

            # 2. find the tool requests in what it said: (call id, tool name, arguments)
            repaired = False
            if tool_mode == "native":
                requests = [(call.id, call.function, call.arguments) for call in (reply.tool_calls or [])]
            else:
                action = parse_action(reply.text)
                if action is None and repairing:  # ask the repair model to read it for us
                    run["repair_attempts"] += 1
                    action = await repair(reply.text, repair_model)
                    repaired = action is not None
                    run["repairs"] += repaired
                requests = [(None, action.tool, action.arguments)] if action else []
                run["extra_actions"] += action.extra_actions if action else 0

            # 3. no usable request: remind the model of the format and let it try again
            if not requests:
                run["reminders"] += 1
                messages.append(ChatMessageUser(content=reminder))
                continue

            # 4. carry out each request and report back
            for call_id, tool, arguments in requests:
                if tool == "submit" and "answer" in arguments:
                    run["submission"] = str(arguments["answer"])
                    run["submission_repaired"] = repaired
                    break
                if tool == "bash" and isinstance(arguments.get("cmd"), str):
                    run["commands"].append(arguments["cmd"])
                    result = await run_bash(arguments["cmd"], settings)
                    run["read_questions"] |= first_question in result
                    run["read_documentation"] |= DOCUMENTATION_MARKER in result
                else:
                    result = f"Error: could not run '{tool}' with arguments {arguments}."
                if tool_mode == "native":
                    messages.append(ChatMessageTool(content=result, tool_call_id=call_id, function=tool))
                else:
                    messages.append(ChatMessageUser(content=result))  # Apollo: tool output goes back as a user message

        run["hit_step_limit"] = run["submission"] is None
        state.messages = messages
        if output is not None:
            state.output = output
        state.store.set("run", run)
        return state

    return solve
