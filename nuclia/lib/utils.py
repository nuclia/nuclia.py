import json
from typing import Union

import httpx
import requests
from tabulate import tabulate

from nuclia.exceptions import RateLimitError, UserTokenExpired, DuplicateError
from nucliadb_models.resource import ResourceList
from nucliadb_models.search import SyncAskResponse


def handle_http_errors(response: Union[httpx.Response, requests.models.Response]):
    if (
        response.status_code == 403
        and "Hydra token is either unexistent or revoked" in response.text
    ):
        raise UserTokenExpired()
    elif response.status_code == 429:
        raise RateLimitError(f"Rate limited: {response.text}")
    elif response.status_code == 409:
        raise DuplicateError("Duplicate resource")
    elif response.status_code >= 400:
        raise httpx.HTTPError(f"Status code {response.status_code}: {response.text}")


def serialize(obj):
    if isinstance(obj, ResourceList):
        data = []
        for resource in obj.resources:
            status = resource.metadata.status if resource.metadata is not None else ""
            data.append(
                [resource.id, resource.icon, resource.title, status, resource.slug]
            )
        return tabulate(
            data,
            headers=["UUID", "Icon", "Title", "Status", "Slug"],
        )
    if isinstance(obj, SyncAskResponse):
        if obj.status != "success":
            response = f"ERROR: {obj.error_details}"
        elif obj.answer_json is not None:
            response = f"JSON: {json.dumps(obj.answer_json, indent=2)} \n"
        else:
            response = f"Answer: {obj.answer} \n"

        if obj.metadata:
            response += f"Metadata: {obj.metadata.model_dump_json(indent=2)}\n"

        response += "Resources: \n"
        data = []
        for resource in obj.retrieval_results.resources.values():
            data.append([resource.id, resource.icon, resource.title])
        response += tabulate(
            data,
            headers=["UUID", "Icon", "Title"],
        )
        return response
    return obj
