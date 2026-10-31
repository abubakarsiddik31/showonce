"""The Ask step: turn disagreement between the two readings of a demo into a question."""

from __future__ import annotations

from showonce.api.schemas import OptionOut, QuestionOut, StepModel
from showonce.chat import how_it_will_do
from showonce.program import Step


def step_model(step: Step) -> StepModel:
    return StepModel(
        object=step.object,
        action=step.action,
        target=step.target,
        relation=step.relation,
        text=str(step),
        how=how_it_will_do(step),
    )


def build_questions(
    geometry: list[Step], semantic: list[Step] | None, source: str
) -> list[QuestionOut]:
    """Ask only when SAM's tracked motion and Muse Spark's reading of the video differ.

    When they agree there is nothing to clarify, so the list is empty. If geometry could not
    explain a move at all, Muse Spark's plan was already used and there is no choice to offer.
    """
    if semantic is None or source != "geometry" or geometry == semantic:
        return []
    return [
        QuestionOut(
            id="plan",
            prompt="Two readings of your demo disagree. Which one matches what you showed?",
            options=[
                OptionOut(
                    id="geometry",
                    label="Tracked motion",
                    steps=[step_model(s) for s in geometry],
                ),
                OptionOut(
                    id="muse_spark",
                    label="Video understanding",
                    steps=[step_model(s) for s in semantic],
                ),
            ],
        )
    ]
