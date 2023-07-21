from typing import Union

import httpx
import requests

from nuclia.exceptions import UserTokenExpired


def handle_http_errors(response: Union[httpx.Response, requests.models.Response]):
    if (
        response.status_code == 403
        and "Hydra token is either unexistent or revoked" in response.text
    ):
        raise UserTokenExpired()
    elif response.status_code >= 400:
        raise httpx.HTTPError(f"Status code {response.status_code}: {response.text}")
