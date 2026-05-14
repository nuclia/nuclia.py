import pytest

from nuclia import (
    _regional_template,
    _root_domain,
    get_global_base,
    get_oauth_base,
    get_regional_base,
)


@pytest.mark.parametrize(
    "base_domain, expected_root",
    [
        # Root form (no prefix) — unchanged
        ("progress.cloud", "progress.cloud"),
        ("stashify.cloud", "stashify.cloud"),
        ("gcp-global-dev-1.nuclia.io", "gcp-global-dev-1.nuclia.io"),
        # Legacy rag. prefix — stripped
        ("rag.progress.cloud", "progress.cloud"),
        ("rag.stashify.cloud", "stashify.cloud"),
        ("rag.gcp-global-dev-1.nuclia.io", "gcp-global-dev-1.nuclia.io"),
    ],
)
def test_root_domain(base_domain, expected_root):
    assert _root_domain(base_domain) == expected_root


@pytest.mark.parametrize(
    "base_domain, expected",
    [
        ("progress.cloud", "https://accounts.progress.cloud"),
        ("stashify.cloud", "https://accounts.stashify.cloud"),
        ("gcp-global-dev-1.nuclia.io", "https://accounts.gcp-global-dev-1.nuclia.io"),
        ("rag.progress.cloud", "https://accounts.progress.cloud"),
        ("rag.stashify.cloud", "https://accounts.stashify.cloud"),
        (
            "rag.gcp-global-dev-1.nuclia.io",
            "https://accounts.gcp-global-dev-1.nuclia.io",
        ),
    ],
)
def test_get_global_base(base_domain, expected):
    assert get_global_base(base_domain) == expected


@pytest.mark.parametrize(
    "base_domain, expected",
    [
        ("progress.cloud", "https://oauth.progress.cloud"),
        ("stashify.cloud", "https://oauth.stashify.cloud"),
        ("gcp-global-dev-1.nuclia.io", "https://oauth.gcp-global-dev-1.nuclia.io"),
        ("rag.progress.cloud", "https://oauth.progress.cloud"),
        ("rag.stashify.cloud", "https://oauth.stashify.cloud"),
        ("rag.gcp-global-dev-1.nuclia.io", "https://oauth.gcp-global-dev-1.nuclia.io"),
    ],
)
def test_get_oauth_base(base_domain, expected):
    assert get_oauth_base(base_domain) == expected


@pytest.mark.parametrize(
    "base_domain, region, expected",
    [
        # Both forms always produce dp. regional URLs
        ("progress.cloud", "europe-1", "https://europe-1.dp.progress.cloud"),
        ("stashify.cloud", "europe-1", "https://europe-1.dp.stashify.cloud"),
        (
            "gcp-global-dev-1.nuclia.io",
            "us-east-1",
            "https://us-east-1.dp.gcp-global-dev-1.nuclia.io",
        ),
        ("rag.progress.cloud", "europe-1", "https://europe-1.dp.progress.cloud"),
        ("rag.stashify.cloud", "europe-1", "https://europe-1.dp.stashify.cloud"),
        (
            "rag.gcp-global-dev-1.nuclia.io",
            "us-east-1",
            "https://us-east-1.dp.gcp-global-dev-1.nuclia.io",
        ),
    ],
)
def test_get_regional_base(base_domain, region, expected):
    assert get_regional_base(region, base_domain) == expected


@pytest.mark.parametrize(
    "base_domain, expected_template",
    [
        ("progress.cloud", "https://{region}.dp.progress.cloud"),
        ("stashify.cloud", "https://{region}.dp.stashify.cloud"),
        (
            "gcp-global-dev-1.nuclia.io",
            "https://{region}.dp.gcp-global-dev-1.nuclia.io",
        ),
        ("rag.progress.cloud", "https://{region}.dp.progress.cloud"),
        ("rag.stashify.cloud", "https://{region}.dp.stashify.cloud"),
        (
            "rag.gcp-global-dev-1.nuclia.io",
            "https://{region}.dp.gcp-global-dev-1.nuclia.io",
        ),
    ],
)
def test_regional_template(base_domain, expected_template):
    assert _regional_template(base_domain) == expected_template
