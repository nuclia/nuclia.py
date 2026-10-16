from unittest.mock import AsyncMock, Mock

import pytest
from nuclia_models.predict.decisions import DecisionRequest, OpenAIDecisionRequest

from nuclia.sdk.predict import AsyncNucliaPredict, NucliaPredict


def openai_request() -> OpenAIDecisionRequest:
    return OpenAIDecisionRequest.model_validate(
        {
            "input": "Checkout is unavailable",
            "model": "decision-model",
            "questions": [{"type": "predicate", "instructions": "Is there an outage?"}],
        }
    )


def system_one_request() -> DecisionRequest:
    return DecisionRequest.model_validate(
        {
            "state": "Checkout is unavailable",
            "model": "jev-1.13.0",
            "questions": {
                "outage": {
                    "type": "noul",
                    "instructions": "Is there an outage?",
                }
            },
        }
    )


def test_predict_decision_methods_forward_routing_consumption_and_timeout():
    client = Mock()
    openai_response = Mock()
    system_one_response = Mock()
    client.decision.return_value = openai_response
    client.decision_system_one.return_value = system_one_response
    predict = NucliaPredict()
    openai = openai_request()
    system_one = system_one_request()

    assert (
        predict.decision(
            openai,
            kbid="case-1",
            show_consumption=True,
            timeout=15,
            nc=client,
        )
        is openai_response
    )
    assert (
        predict.decision_system_one(
            system_one,
            kbid="case-2",
            show_consumption=True,
            timeout=16,
            nc=client,
        )
        is system_one_response
    )

    client.decision.assert_called_once_with(
        openai,
        kbid="case-1",
        extra_headers={"X-Show-Consumption": "true"},
        timeout=15,
    )
    client.decision_system_one.assert_called_once_with(
        system_one,
        kbid="case-2",
        extra_headers={"X-Show-Consumption": "true"},
        timeout=16,
    )


@pytest.mark.asyncio
async def test_async_predict_decision_methods_forward_routing_consumption_and_timeout():
    client = Mock()
    openai_response = Mock()
    system_one_response = Mock()
    client.decision = AsyncMock(return_value=openai_response)
    client.decision_system_one = AsyncMock(return_value=system_one_response)
    predict = AsyncNucliaPredict()
    openai = openai_request()
    system_one = system_one_request()

    assert (
        await predict.decision(
            openai,
            kbid="case-1",
            show_consumption=True,
            timeout=15,
            nc=client,
        )
        is openai_response
    )
    assert (
        await predict.decision_system_one(
            system_one,
            kbid="case-2",
            show_consumption=True,
            timeout=16,
            nc=client,
        )
        is system_one_response
    )

    client.decision.assert_awaited_once_with(
        openai,
        kbid="case-1",
        extra_headers={"X-Show-Consumption": "true"},
        timeout=15,
    )
    client.decision_system_one.assert_awaited_once_with(
        system_one,
        kbid="case-2",
        extra_headers={"X-Show-Consumption": "true"},
        timeout=16,
    )
