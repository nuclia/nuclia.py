from nuclia.data import get_auth
from nuclia.decorators import kb
from nuclia.exceptions import InvalidPayload
from nuclia.lib.kb import NucliaDBClient
from nuclia.lib.utils import handle_http_errors
from nuclia.sdk.auth import NucliaAuth
from nuclia.lib.tasks import (
    ApplyOptions,
    TaskDefinition,
    TaskStart,
    TaskResponse,
    PublicTaskRequest,
    TaskList,
)

LIST_TASKS = "/tasks"
START_TASK = "/task/{task_name}/start"
STOP_TASK = "/task/{task_id}/stop"
DELETE_TASK = "/task/{task_id}"
GET_TASK = "/task/{task_id}/inspect"
RESTART_TASK = "/task/{task_id}/restart"


class NucliaTask:
    @property
    def _auth(self) -> NucliaAuth:
        auth = get_auth()
        return auth

    @kb
    def list(self, **kwargs) -> TaskList:
        ndb: NucliaDBClient = kwargs["ndb"]

        if ndb.reader_session is None:
            raise Exception("KB not configured")
        resp = ndb.reader_session.get(LIST_TASKS)
        handle_http_errors(resp)
        return TaskList.model_validate_json(resp.content)

    @kb
    def schema(self, task_name: str, **kwargs) -> TaskDefinition:
        ndb: NucliaDBClient = kwargs["ndb"]

        if ndb.reader_session is None:
            raise Exception("KB not configured")
        resp = ndb.reader_session.get(LIST_TASKS)
        handle_http_errors(resp)
        tasks = TaskList.model_validate_json(resp.content)
        for task in tasks.tasks:
            if task.name == task_name:
                return task
        raise KeyError("Task not found")

    @kb
    def start(
        self, task_name: str, apply: ApplyOptions = ApplyOptions.ALL, **kwargs
    ) -> TaskResponse:
        ndb: NucliaDBClient = kwargs["ndb"]

        del kwargs["ndb"]
        parameters = TaskStart(parameters=kwargs, apply=apply)
        if ndb.writer_session is None:
            raise Exception("KB not configured")
        resp = ndb.writer_session.post(
            START_TASK.format(task_name=task_name), json=parameters.model_dump()
        )
        handle_http_errors(resp)
        return TaskResponse.model_validate_json(resp.content)

    @kb
    def delete(self, task_id: str, **kwargs):
        ndb: NucliaDBClient = kwargs["ndb"]

        if ndb.writer_session is None:
            raise Exception("KB not configured")
        resp = ndb.writer_session.delete(DELETE_TASK.format(task_id=task_id))
        try:
            handle_http_errors(resp)
        except InvalidPayload:
            pass

    @kb
    def stop(self, task_id: str, **kwargs) -> TaskResponse:
        ndb: NucliaDBClient = kwargs["ndb"]

        if ndb.writer_session is None:
            raise Exception("KB not configured")
        resp = ndb.writer_session.post(STOP_TASK.format(task_id=task_id))
        handle_http_errors(resp)
        return TaskResponse.model_validate_json(resp.content)

    @kb
    def get(self, task_id: str, **kwargs) -> PublicTaskRequest:
        ndb: NucliaDBClient = kwargs["ndb"]

        if ndb.reader_session is None:
            raise Exception("KB not configured")
        resp = ndb.reader_session.get(GET_TASK.format(task_id=task_id))
        handle_http_errors(resp)
        return PublicTaskRequest.model_validate_json(resp.content)

    @kb
    def restart(self, task_id: str, **kwargs):
        ndb: NucliaDBClient = kwargs["ndb"]

        if ndb.writer_session is None:
            raise Exception("KB not configured")
        resp = ndb.writer_session.post(RESTART_TASK.format(task_id=task_id))
        handle_http_errors(resp)
