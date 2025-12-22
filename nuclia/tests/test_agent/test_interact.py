from typing import Type, Union

import pytest
from nuclia_models.agent.interaction import AnswerOperation, AragAnswer

from nuclia.sdk.agent import AsyncNucliaAgent, NucliaAgent
from nuclia.tests.utils import maybe_async_iterate


@pytest.mark.parametrize(
    "agent_klass",
    [NucliaAgent, AsyncNucliaAgent],
)
async def test_interact(
    testing_config,
    agent_klass: Type[Union[NucliaAgent, AsyncNucliaAgent]],
):
    n_agent = agent_klass()
    responses: list[AragAnswer] = []
    async for message in maybe_async_iterate(
        n_agent.interact(
            session_uuid="ephemeral",
            question="What is Eric known for?",
            headers={"X-Custom-Header": "value"},
        )
    ):
        responses.append(message)
    assert len(responses) > 0
    assert responses[0].operation == AnswerOperation.START

    assert responses[1].operation == AnswerOperation.ANSWER
    assert responses[1].step and responses[1].step.module == "rephrase"

    assert responses[2].operation == AnswerOperation.ANSWER
    assert responses[2].step and responses[2].step.module == "basic_ask"

    assert responses[-3].operation == AnswerOperation.ANSWER
    assert responses[-3].step and responses[-3].step.module == "remi"

    assert responses[-2].operation == AnswerOperation.ANSWER
    assert responses[-2].answer and "humor" in responses[-2].answer.lower()

    assert responses[-1].operation == AnswerOperation.DONE
