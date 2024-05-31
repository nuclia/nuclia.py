import pytest

from nuclia.lib.nua_responses import PushPayload


def test_uuid_validation():
    PushPayload()
    with pytest.raises(ValueError):
        PushPayload(kbid="")
    with pytest.raises(ValueError):
        PushPayload(uuid="")
    with pytest.raises(ValueError):
        PushPayload(uuid="invalid.uuid")
