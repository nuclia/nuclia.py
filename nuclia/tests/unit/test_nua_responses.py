import pytest

from nuclia.lib.nua_responses import ChatModel, PushPayload, Reasoning


def test_uuid_validation():
    PushPayload()
    with pytest.raises(ValueError):
        PushPayload(kbid="")
    with pytest.raises(ValueError):
        PushPayload(uuid="")
    with pytest.raises(ValueError):
        PushPayload(uuid="invalid.uuid")


def test_reasoning_serializes_only_set_fields_in_chat_model():
    def reasoning_payload(r: Reasoning) -> dict:
        return ChatModel(question="q", user_id="u", reasoning=r).model_dump()["reasoning"]

    assert reasoning_payload(Reasoning(effort="high")) == {"effort": "high"}
    assert reasoning_payload(Reasoning(budget_tokens=1024)) == {"budget_tokens": 1024}
    assert reasoning_payload(Reasoning(effort="xhigh", budget_tokens=1024)) == {
        "effort": "xhigh",
        "budget_tokens": 1024,
    }
    assert reasoning_payload(Reasoning(display=False)) == {"display": False}
    assert reasoning_payload(Reasoning()) == {}


def test_reasoning_effort_and_budget_tokens_are_independent():
    # Effort and budget_tokens are no longer coupled client-side.
    # The learning normalization layer handles any effort↔budget mapping.
    r = Reasoning(effort="high")
    assert r.effort == "high"
    assert r.budget_tokens == 15_000  # default, not overridden by effort

    r2 = Reasoning(budget_tokens=1024)
    assert r2.budget_tokens == 1024
    assert r2.effort == "medium"  # default, not overridden by budget_tokens

    # Both can be set independently; learning will normalize them.
    r3 = Reasoning(effort="low", budget_tokens=99_999)
    assert r3.effort == "low"
    assert r3.budget_tokens == 99_999


def test_chat_model_does_not_enforce_budget_tokens_vs_max_tokens():
    # The budget_tokens > max_tokens constraint was intentionally removed.
    # Validation is delegated to the learning normalization layer.
    chat = ChatModel(
        question="q", user_id="u", max_tokens=100, reasoning=Reasoning(budget_tokens=99_999)
    )
    assert chat.reasoning.budget_tokens == 99_999  # type: ignore[union-attr]
