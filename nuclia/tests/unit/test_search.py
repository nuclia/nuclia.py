import pytest
from nucliadb_models.search import Filter

from nuclia.sdk.search import _parse_filters


def test_parse_filters():
    assert _parse_filters(None, "all") == []
    assert _parse_filters([], "all") == []
    assert _parse_filters(["foo", "bar"], "all") == ["foo", "bar"]
    assert _parse_filters(["foo", "bar"], "ALL") == ["foo", "bar"]
    assert _parse_filters(["foo", "bar"], "any") == [Filter(any=["foo", "bar"])]
    assert _parse_filters(["foo", "bar"], "none") == [Filter(none=["foo", "bar"])]
    with pytest.raises(ValueError):
        _parse_filters(["foo", "bar"], "invalid")
