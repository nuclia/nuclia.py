"""
URL resolution helpers for Nuclia service endpoints.

BASE_DOMAIN can be supplied in two forms:

  Root (canonical):      progress.cloud / stashify.cloud / gcp-global-dev-1.nuclia.io
  Legacy rag. prefix:    rag.progress.cloud / rag.stashify.cloud / ...

Derived service URLs (always based on the root, rag. stripped if present):
  Global API:  https://accounts.{root}
  OAuth:       https://oauth.{root}
  Regional:    https://{region}.dp.{root}
"""


def _root_domain(base_domain: str) -> str:
    """Strip the 'rag.' frontend prefix if present, returning the root domain."""
    if base_domain.startswith("rag."):
        return base_domain[4:]
    return base_domain


def get_global_base(base_domain: str) -> str:
    return f"https://accounts.{_root_domain(base_domain)}"


def get_oauth_base(base_domain: str) -> str:
    return f"https://oauth.{_root_domain(base_domain)}"


def _regional_template(base_domain: str) -> str:
    return f"https://{{region}}.dp.{_root_domain(base_domain)}"


def get_regional_base(region: str, base_domain: str) -> str:
    return _regional_template(base_domain).format(region=region)
