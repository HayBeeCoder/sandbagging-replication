from inspect_ai import Task, task, eval
from inspect_ai.dataset import Sample
from inspect_ai.model import ModelOutput, get_model
from inspect_ai.scorer import match
from inspect_ai.solver import generate


@task
def hello():
    return Task(
        # DATASET: two samples, each with an input and the correct target
        dataset=[
            Sample(input="What is 2 + 2? Answer with the number only.", target="4"),
            Sample(input="What is 3 x 5? Answer with the number only.", target="15"),
        ],
        # SOLVER: send the input to the model once and keep its reply
        solver=generate(),
        # SCORER: correct if the reply matches the target
        scorer=match(),
    )


if __name__ == "__main__":
    # MODEL: a fake model that replies "4" to the first call and "16" to the second
    fake_model = get_model(
        "mockllm/model",
        custom_outputs=[
            ModelOutput.from_content("mockllm/model", "4"),
            ModelOutput.from_content("mockllm/model", "16"),
        ],
    )
    # max_connections=1 runs samples one at a time, so the fake replies stay in order
    logs = eval(hello(), model=fake_model, log_dir="logs/hello", display="plain", max_connections=1)
    log = logs[0]
    print("status:", log.status)
    print("accuracy:", log.results.scores[0].metrics["accuracy"].value)
    for s in log.samples:
        print(repr(s.input[:14]), "| model said:", s.output.completion,"| target:", s.target, "| score:", s.scores["match"].value)
