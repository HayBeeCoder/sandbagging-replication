"""Repair mode: a second model rewrites a reply we could not read into a proper tool request.

Apollo did this with gpt-4o-mini (Appendix D.1). The two prompts are theirs, word for word,
and so is the answer structure below. The repair model here is any key from models.yaml.
"""
import json

import pydantic
from inspect_ai.model import ChatMessageSystem, ChatMessageUser, GenerateConfig, Model, ResponseSchema
from inspect_ai.util import json_schema

from sandbag import prompts
from sandbag.actions import ParsedAction, parse_action

SLOT = "<model-response>...</model-response>"  # where the unreadable reply goes in Apollo's user prompt


# The structure Apollo asked gpt-4o-mini to fill in (copied from the paper).
class ActionRequest(pydantic.BaseModel):
    name: str
    value: str


class ActionRequestWrapper(pydantic.BaseModel):
    function_name: str
    arguments: list[ActionRequest]


class MaybeActionRequest(pydantic.BaseModel):
    # allow the model to indicate that it couldn't find or parse anything valid
    action_request: ActionRequestWrapper | None


def repair_messages(reply: str) -> list:
    """The two messages sent to the repair model."""
    template = prompts.load("repair_user.txt")
    if template.count(SLOT) != 1:
        raise ValueError(f"prompts/repair_user.txt must contain {SLOT} exactly once")
    user = template.replace(SLOT, f"<model-response>{reply}</model-response>")
    return [ChatMessageSystem(content=prompts.load("repair_system.txt")), ChatMessageUser(content=user)]


def read_repair(text: str) -> ParsedAction | None:
    """Turn the repair model's answer into a tool request; None if it found nothing usable."""
    try:
        start, end = text.index("{"), text.rindex("}") + 1
        request = MaybeActionRequest.model_validate_json(text[start:end]).action_request
    except (ValueError, pydantic.ValidationError):
        return None
    if request is None:  # the repair model says the reply contained no action
        return None
    arguments = {argument.name: argument.value for argument in request.arguments}
    # Write it out in Apollo's text format and let the usual parser apply the usual rules.
    return parse_action(f"Action: {request.function_name}\nAction Input: {json.dumps(arguments)}")


async def repair(reply: str, model: Model) -> ParsedAction | None:
    """Ask the repair model to extract the tool request from an unreadable reply."""
    schema = ResponseSchema(name="MaybeActionRequest", json_schema=json_schema(MaybeActionRequest))
    output = await model.generate(repair_messages(reply), config=GenerateConfig(response_schema=schema))
    return read_repair(output.completion)
