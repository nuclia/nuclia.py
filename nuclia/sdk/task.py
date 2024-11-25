from nuclia.data import get_auth
from nuclia.decorators import kb
from nuclia.exceptions import InvalidPayload
from nuclia.lib.kb import NucliaDBClient
from nuclia.sdk.auth import NucliaAuth
from nuclia_models.worker.tasks import (
    ApplyOptions,
    TaskStartKB,
    TaskResponse,
    PublicTaskRequest,
    TaskList,
    TaskName,
    PARAMETERS_TYPING,
)


class NucliaTask:
    @property
    def _auth(self) -> NucliaAuth:
        auth = get_auth()
        return auth

    @kb
    def list(self, **kwargs) -> TaskList:
        """
        List tasks
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        response = ndb.list_tasks()
        return TaskList.model_validate(response.json())

    @kb
    def start(
        self,
        task_name: TaskName,
        apply: ApplyOptions = ApplyOptions.ALL,
        parameters=PARAMETERS_TYPING,
        **kwargs,
    ) -> TaskResponse:
        """
        Start task

        :param task_name: TaskName enum
        :param apply: EXISTING, NEW, ALL
        :param parameters: Specific parameters depending on the task choosen
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        response = ndb.start_task(
            body=TaskStartKB(name=task_name, parameters=parameters, apply=apply)
        )
        return TaskResponse.model_validate(response.json())

    @kb
    def delete(self, task_id: str, **kwargs):
        """
        Delete task

        :param task_id: ID of the task to delete
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        try:
            _ = ndb.delete_task(task_id=task_id)
        except InvalidPayload:
            pass

    @kb
    def stop(self, task_id: str, **kwargs) -> TaskResponse:
        """
        Stop task

        :param task_id: ID of the task to stop
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        response = ndb.stop_task(task_id=task_id)
        return TaskResponse.model_validate(response.json())

    @kb
    def get(self, task_id: str, **kwargs) -> PublicTaskRequest:
        """
        Get task

        :param task_id: ID of the task to show
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        response = ndb.get_task(task_id=task_id)
        return PublicTaskRequest.model_validate(response.json())

    @kb
    def restart(self, task_id: str, **kwargs) -> TaskResponse:
        """
        Restart task

        :param task_id: ID of the task to restart
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        response = ndb.restart_task(task_id=task_id)
        return TaskResponse.model_validate(response.json())
