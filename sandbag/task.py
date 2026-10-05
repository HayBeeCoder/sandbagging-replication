"""The experiment as an Inspect task: two conditions, many runs of each, one score per run."""
from inspect_ai import Epochs, Task, task
from inspect_ai.dataset import Sample
from inspect_ai.model import ContentReasoning, ContentText
from inspect_ai.scorer import Score, Target, grouped, mean, scorer
from inspect_ai.solver import TaskState

from sandbag import prompts
from sandbag.agent import sandbag_agent
from sandbag.config import load_experiment
from sandbag.environment import sandbox_files
from sandbag.questions import load_answer_key
from sandbag.scoring import score_submission
from sandbag.screens import screen


def model_text(messages) -> str:
    """Everything the MODEL wrote: its visible replies and, where the provider returns it, its reasoning."""
    parts = []
    for message in messages:
        if message.role != "assistant":
            continue  # prompts and tool output are ours, and contain words the screens look for
        if isinstance(message.content, str):
            parts.append(message.content)
            continue
        for item in message.content:
            if isinstance(item, ContentReasoning):
                parts.append(item.reasoning or item.summary or "")
            elif isinstance(item, ContentText):
                parts.append(item.text)
    return "\n\n".join(part for part in parts if part)


@scorer(metrics=[grouped(mean(), "condition")])  # mean accuracy, separately for each condition
def sandbag_scorer():
    key = load_answer_key()

    async def score(state: TaskState, target: Target) -> Score:
        run = state.store.get("run")                     # what the loop recorded
        result = score_submission(run["submission"], key)  # accuracy and format checks
        flags = screen(model_text(state.messages))       # keyword screens over the model's own words
        return Score(
            value=result["accuracy"],
            answer=result["letters"] or run["submission"] or "(no submission)",
            explanation=f"{result['n_correct']}/{len(key)} correct",
            metadata={"condition": state.metadata["condition"], **result, **flags, **run},
        )

    return score


@task
def sandbagging(system: str = "no_goal", tool_mode: str = "text", runs: int | None = None) -> Task:
    """system: no_goal, goal_hard, goal_medium or goal_easy. runs: overrides runs_per_condition."""
    settings = load_experiment()
    return Task(
        dataset=[Sample(id=condition, input=prompts.user_prompt(), files=sandbox_files(condition),
                        metadata={"condition": condition})
                 for condition in settings["conditions"]],
        solver=sandbag_agent(system, tool_mode, settings),
        scorer=sandbag_scorer(),
        epochs=Epochs(runs or settings["runs_per_condition"]),  # each sample is repeated this many times
        sandbox=settings["sandbox"],
    )
