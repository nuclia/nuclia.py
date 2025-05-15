import json

import httpx
import importlib.metadata
import requests
from httpx import Response as HttpxResponse, HTTPStatusError
from tabulate import tabulate
from typing import Optional

from nuclia.exceptions import (
    RateLimitError,
    UserTokenExpired,
    DuplicateError,
    InvalidPayload,
)
from nucliadb_models.resource import ResourceList
from nucliadb_models.search import SyncAskResponse
from nuclia.lib.models import ActivityLogsOutput
from nuclia_models.worker.tasks import TaskDefinition, TaskList
from nucliadb_models.resource import KnowledgeBoxList
from requests import Response as RequestsResponse, HTTPError as RequestsHTTPError


USER_AGENT = f"nuclia.py/{importlib.metadata.version('nuclia')}"


def handle_http_sync_errors(response):
    try:
        content = response.text
    except (httpx.ResponseNotRead, requests.exceptions.RequestException):
        content = "<streaming content not read>"
    except Exception as e:
        content = f"<error decoding content: {e}>"

    _raise_for_status(response.status_code, content, response=response)


async def handle_http_async_errors(response: httpx.Response):
    try:
        if not response.is_closed and not response.is_stream_consumed:
            await response.aread()
    except Exception as e:
        content = f"<failed to read stream: {e}>"
        _raise_for_status(
            response.status_code, content, response=response, request=response.request
        )
        return  # Defensive
    try:
        content = response.text
    except httpx.ResponseNotRead:
        content = "<streaming content not read>"
    except Exception as e:
        content = f"<error decoding content: {e}>"

    _raise_for_status(
        response.status_code, content, response=response, request=response.request
    )


def _raise_for_status(status_code: int, content: str, response=None, request=None):
    if status_code == 403 and "Hydra token is either unexistent or revoked" in content:
        raise UserTokenExpired()
    elif status_code == 429:
        raise RateLimitError(f"Rate limited: {content}")
    elif status_code == 409:
        raise DuplicateError(f"Duplicate resource: {content}")
    elif status_code == 422:
        raise InvalidPayload(f"Invalid payload: {content}")
    elif status_code >= 400:
        if isinstance(response, HttpxResponse):
            raise HTTPStatusError(
                f"Status code {status_code}: {content}",
                request=request,
                response=response,
            )
        elif isinstance(response, RequestsResponse):
            raise RequestsHTTPError(
                f"Status code {status_code}: {content}", response=response
            )
        else:
            raise Exception(f"Status code {status_code}: {content}")


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

    if isinstance(obj, KnowledgeBoxList):
        data = []
        for kb in obj.kbs:
            data.append([kb.uuid, kb.slug])
        return tabulate(
            data,
            headers=["UUID", "Slug"],
        )

    if isinstance(obj, TaskDefinition):
        return json.dumps(obj.validation, indent=2)

    if isinstance(obj, TaskList):
        output = ""
        if obj.tasks:
            output += "# Available tasks\n"
            output += "\n"
            data = []
            for task in obj.tasks:
                data.append([task.name, task.description])

            output += tabulate(
                data,
                headers=["Name", "Description"],
            )
            output += "\n\n"

        if obj.running:
            output += "# Running tasks\n"
            output += "\n"
            data = []
            for running_task in obj.running:
                data.append(
                    [
                        running_task.task.name,
                        running_task.id,
                        running_task.scheduled_at,
                    ]
                )

            output += tabulate(
                data,
                headers=["Task", "ID", "Started"],
            )
            output += "\n\n"

        if obj.configs:
            output += "# Configured tasks\n"
            output += "\n"
            data = []
            for running_task in obj.configs:
                data.append(
                    [
                        running_task.task.name,
                        running_task.id,
                    ]
                )

            output += tabulate(
                data,
                headers=["Task", "ID"],
            )
            output += "\n\n"
        return output

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

    if isinstance(obj, ActivityLogsOutput):
        obj = obj.model_dump(exclude_unset=True)

    return obj


def build_httpx_client(
    headers: dict[str, str] = {}, base_url: Optional[str] = None
) -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT, **headers}, base_url=(base_url or "")
    )


def build_httpx_async_client(
    headers: dict[str, str] = {}, base_url: Optional[str] = None
) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT, **headers}, base_url=(base_url or "")
    )
