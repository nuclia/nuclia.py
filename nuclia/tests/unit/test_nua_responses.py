import pytest

from nuclia.lib.nua_responses import PushPayload, Reasoning


def test_uuid_validation():
    PushPayload()
    with pytest.raises(ValueError):
        PushPayload(kbid="")
    with pytest.raises(ValueError):
        PushPayload(uuid="")
    with pytest.raises(ValueError):
        PushPayload(uuid="invalid.uuid")


@pytest.mark.parametrize(
    "effort,expected_budget_tokens",
    [
        ("none", 0),
        ("minimal", 0),
        ("low", 7500),
        ("medium", 15_000),
        ("high", 30_000),
        ("xhigh", 50_000),
    ],
)
def test_reasoning_effort_sets_budget_tokens(effort, expected_budget_tokens):
    r = Reasoning(effort=effort)
    assert r.budget_tokens == expected_budget_tokens


@pytest.mark.parametrize(
    "budget_tokens,expected_effort",
    [
        (0, "low"),
        (7500, "low"),
        (7501, "medium"),
        (15_000, "medium"),
        (15_001, "high"),
        (30_000, "high"),
        (30_001, "xhigh"),
        (50_000, "xhigh"),
    ],
)
def test_reasoning_budget_tokens_sets_effort(budget_tokens, expected_effort):
    r = Reasoning(budget_tokens=budget_tokens)
    assert r.effort == expected_effort
