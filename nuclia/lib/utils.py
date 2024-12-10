import json
from typing import Union

import httpx
import requests
from tabulate import tabulate

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


def handle_http_errors(response: Union[httpx.Response, requests.models.Response]):
    if (
        response.status_code == 403
        and "Hydra token is either unexistent or revoked" in response.text
    ):
        raise UserTokenExpired()
    elif response.status_code == 429:
        raise RateLimitError(f"Rate limited: {response.text}")
    elif response.status_code == 409:
        raise DuplicateError(f"Duplicate resource: {response.text}")
    elif response.status_code == 422:
        raise InvalidPayload(f"Invalid payload: {response.text}")
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
