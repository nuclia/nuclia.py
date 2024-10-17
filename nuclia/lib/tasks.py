import datetime
from enum import Enum
from pydantic import BaseModel
from typing import Any, Dict
from typing import List
from typing import Optional


class TrainingTaskDatasetSource(str, Enum):
    # A knowledge box stored in NucliaDB
    NUCLIADB = "nucliadb"

    # A dataset located in a storage
    DATASET = "dataset"


class TaskDone(BaseModel):
    timeit: int
    success: bool
    account: str
    build: bool = False
    source: TrainingTaskDatasetSource
    path: Optional[str] = None
    dataset_id: Optional[str] = None
    client_id: Optional[str] = None
    kbid: Optional[str] = None
    user: Optional[str] = None
    log: Optional[str] = None


class ApplyOptions(str, Enum):
    EXISTING = "EXISTING"
    NEW = "NEW"
    ALL = "ALL"


class TaskStart(BaseModel):
    parameters: Dict[str, Any]
    apply: ApplyOptions = ApplyOptions.ALL


class JobStatus(str, Enum):
    NOT_RUNNING = "not_running"
    FINISHED = "finished"
    RUNNING = "running"
    STARTED = "started"
    STOPPED = "stopped"


class TaskResponse(BaseModel):
    task: Optional[str] = None
    status: JobStatus
    id: Optional[str] = None


class TaskDefinition(BaseModel):
    name: str
    description: Optional[str] = None
    validation: Dict[str, Any]


class PublicTask(BaseModel):
    name: str
    data_augmentation: bool = False
    description: Optional[str] = None


class PublicTaskConfig(BaseModel):
    task: PublicTask
    kbid: Optional[str] = None
    account_id: str
    account_type: str
    nua_client_id: Optional[str] = None
    user_id: str
    parameters: Dict[str, Any] = {}
    id: str
    timestamp: datetime.datetime
    defined_at: Optional[datetime.datetime] = None


class PublicTaskRequest(BaseModel):
    task: PublicTask
    source: TrainingTaskDatasetSource
    kbid: Optional[str] = None
    dataset_id: Optional[str] = None
    account_id: str
    nua_client_id: Optional[str] = None
    user_id: str
    id: str
    timestamp: datetime.datetime
    scheduled: bool = False
    completed: bool = False
    stopped: bool = False
    scheduled_at: Optional[datetime.datetime] = None
    completed_at: Optional[datetime.datetime] = None
    stopped_at: Optional[datetime.datetime] = None
    failed: bool = False
    retries: int = 0


class TaskList(BaseModel):
    tasks: List[TaskDefinition]
    running: List[PublicTaskRequest]
    configs: List[PublicTaskConfig]
