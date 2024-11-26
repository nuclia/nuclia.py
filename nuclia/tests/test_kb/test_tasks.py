from nuclia.sdk.kb import NucliaKB
from nuclia.tests.fixtures import IS_PROD
from nuclia_models.worker.tasks import (
    TaskList,
    TaskName,
    ApplyOptions,
    TaskResponse,
    JobStatus,
)
from nuclia_models.worker.proto import (
    DataAugmentation,
    ApplyTo,
    Filter,
    Operation,
    LLMConfig,
)


def test_worker_manager_tasks(testing_config):
    if not IS_PROD:
        assert True
        return

    nkb = NucliaKB()

    output = nkb.task.list()
    assert isinstance(output, TaskList)

    output = nkb.task.start(
        task_name=TaskName.LABELER,
        apply=ApplyOptions.EXISTING,
        parameters=DataAugmentation(
            name="test",
            on=ApplyTo.FIELD,
            filter=Filter(),
            operations=[Operation()],
            llm=LLMConfig(),
        ),
    )
    assert isinstance(output, TaskResponse)
    task_id = output.id

    output = nkb.task.get(task_id=task_id)
    assert output.request.id == task_id

    output = nkb.task.stop(task_id=task_id)
    assert output.id == task_id
    assert output.status == JobStatus.NOT_RUNNING

    output = nkb.task.restart(task_id=task_id)
    assert output.id == task_id
    assert output.status == JobStatus.NOT_RUNNING

    output = nkb.task.stop(task_id=task_id)
    assert output.id == task_id
    assert output.status == JobStatus.NOT_RUNNING

    output = nkb.task.delete(task_id=task_id)
    assert output is None

    output = nkb.task.get(task_id=task_id)
    assert output.request is None
    assert output.config is None
