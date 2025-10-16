from nuclia.config import extract_region


def test_extract_region(monkeypatch):
    assert extract_region("https://europe-1.rag.progress.cloud/api/v1") == "europe-1"
    assert extract_region("https://europe-1.nuclia.cloud/api/v1") == "europe-1"
    assert extract_region("https://europe-1.stashify.cloud/api/v1") == "europe-1"
    assert (
        extract_region("https://europe-1.gcp-global-dev-1.nuclia.io/api/v1")
        == "europe-1"
    )
    assert extract_region("https://rag.progress.cloud/api/v1") == ""
    assert extract_region("https://nuclia.cloud/api/v1") == ""
    assert extract_region("https://stashify.cloud/api/v1") == ""
    assert extract_region("https://gcp-global-dev-1.nuclia.io/api/v1") == ""

    assert extract_region("https://europe-1.example.com/api/v1") == "europe-1"
    assert extract_region("https://example.com/api/v1") == "example"

    # Custom base domain
    monkeypatch.setattr("nuclia.config.CLOUD_ID", "example.com")
    assert extract_region("https://europe-1.example.com/api/v1") == "europe-1"
    assert extract_region("https://example.com/api/v1") == ""
