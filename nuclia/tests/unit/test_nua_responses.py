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


def test_reasoning_serializes_only_set_fields():
    assert Reasoning(effort="high").model_dump() == {"effort": "high"}
    assert Reasoning(budget_tokens=1024).model_dump() == {"budget_tokens": 1024}
    assert Reasoning(effort="xhigh", budget_tokens=1024).model_dump() == {"effort": "xhigh", "budget_tokens": 1024}
    assert Reasoning(display=False).model_dump() == {"display": False}
    assert Reasoning().model_dump() == {}
