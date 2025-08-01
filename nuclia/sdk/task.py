from nuclia.data import get_auth, get_async_auth
from nuclia.decorators import kb
from nuclia.exceptions import InvalidPayload
from nuclia.lib.kb import NucliaDBClient, AsyncNucliaDBClient
from nuclia.sdk.auth import NucliaAuth, AsyncNucliaAuth
from nuclia_models.worker.tasks import (
    ApplyOptions,
    TaskStartKB,
    TaskList,
    TaskName,
    TaskResponse,
    PARAMETERS_TYPING,
    PublicTaskSet,
    TASKS,
)
from typing import Union


class NucliaTask:
    @property
    def _auth(self) -> NucliaAuth:
        auth = get_auth()
        return auth

    @kb
    def list(self, *args, **kwargs) -> TaskList:
        """
        List tasks
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        response = ndb.list_tasks()
        return TaskList.model_validate(response.json())

    @kb
    def start(
        self,
        *args,
        task_name: Union[TaskName, str],
        apply: Union[ApplyOptions, str],
        parameters: Union[PARAMETERS_TYPING, dict],
        **kwargs,
    ) -> TaskResponse:
        """
        Start task

        :param task_name: TaskName enum
        :param apply: EXISTING, NEW, ALL
        :param parameters: Specific parameters depending on the task choosen
        """
        if isinstance(task_name, str):
            task_name = TaskName(task_name.lower())
        if isinstance(apply, str):
            apply = ApplyOptions(apply.upper())
        if isinstance(parameters, dict):
            parameters_model = TASKS[task_name].validation
            if parameters_model is None:
                raise InvalidPayload(f"Invalid parameters for task {task_name.value}")
            parameters = parameters_model.model_validate(parameters)

        ndb: NucliaDBClient = kwargs["ndb"]
        response = ndb.start_task(
            body=TaskStartKB(name=task_name, parameters=parameters, apply=apply)
        )
        return TaskResponse.model_validate(response.json())

    @kb
    def delete(self, *args, task_id: str, cleanup: bool = False, **kwargs):
        """
        Delete task

        :param task_id: ID of the task to delete
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        try:
            _ = ndb.delete_task(task_id=task_id, cleanup=cleanup)
        except InvalidPayload:
            pass

    @kb
    def stop(self, *args, task_id: str, **kwargs) -> TaskResponse:
        """
        Stop task

        :param task_id: ID of the task to stop
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        response = ndb.stop_task(task_id=task_id)
        return TaskResponse.model_validate(response.json())

    @kb
    def get(self, *args, task_id: str, **kwargs) -> PublicTaskSet:
        """
        Get task

        :param task_id: ID of the task to show
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        response = ndb.get_task(task_id=task_id)
        return PublicTaskSet.model_validate(response.json())

    @kb
    def restart(self, *args, task_id: str, **kwargs) -> TaskResponse:
        """
        Restart task

        :param task_id: ID of the task to restart
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        response = ndb.restart_task(task_id=task_id)
        return TaskResponse.model_validate(response.json())


class AsyncNucliaTask:
    @property
    def _auth(self) -> AsyncNucliaAuth:
        auth = get_async_auth()
        return auth

    @kb
    async def list(self, *args, **kwargs) -> TaskList:
        """
        List tasks
        """
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        response = await ndb.list_tasks()
        return TaskList.model_validate(response.json())

    @kb
    async def start(
        self,
        *args,
        task_name: Union[TaskName, str],
        apply: Union[ApplyOptions, str],
        parameters: Union[PARAMETERS_TYPING, dict],
        **kwargs,
    ) -> TaskResponse:
        """
        Start task

        :param task_name: TaskName enum
        :param apply: EXISTING, NEW, ALL
        :param parameters: Specific parameters depending on the task choosen
        """
        if isinstance(task_name, str):
            task_name = TaskName(task_name.lower())
        if isinstance(apply, str):
            apply = ApplyOptions(apply.upper())
        if isinstance(parameters, dict):
            parameters_model = TASKS[task_name].validation
            if parameters_model is None:
                raise InvalidPayload(f"Invalid parameters for task {task_name.value}")
            parameters = parameters_model.model_validate(parameters)

        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        response = await ndb.start_task(
            body=TaskStartKB(name=task_name, parameters=parameters, apply=apply)
        )
        return TaskResponse.model_validate(response.json())

    @kb
    async def delete(self, *args, task_id: str, cleanup: bool = False, **kwargs):
        """
        Delete task

        :param task_id: ID of the task to delete
        """
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        try:
            _ = await ndb.delete_task(task_id=task_id, cleanup=cleanup)
        except InvalidPayload:
            pass

    @kb
    async def stop(self, *args, task_id: str, **kwargs) -> TaskResponse:
        """
        Stop task

        :param task_id: ID of the task to stop
        """
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        response = await ndb.stop_task(task_id=task_id)
        return TaskResponse.model_validate(response.json())

    @kb
    async def get(self, *args, task_id: str, **kwargs) -> PublicTaskSet:
        """
        Get task

        :param task_id: ID of the task to show
        """
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        response = await ndb.get_task(task_id=task_id)
        return PublicTaskSet.model_validate(response.json())

    @kb
    async def restart(self, *args, task_id: str, **kwargs) -> TaskResponse:
        """
        Restart task

        :param task_id: ID of the task to restart
        """
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        response = await ndb.restart_task(task_id=task_id)
        return TaskResponse.model_validate(response.json())
