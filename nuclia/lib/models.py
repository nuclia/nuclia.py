from nuclia_models.events.activity_logs import (
    ActivityLogsQueryResponse,
    BaseConfigModel,
    DownloadRequest,
)
from pydantic import BaseModel


class ActivityLogsOutput(BaseConfigModel):
    data: list[ActivityLogsQueryResponse]  # type: ignore
    has_more: bool


DownloadRequestOutput = type(
    "DownloadRequestOutput",
    (BaseModel,),
    {
        "__annotations__": {
            name: field.annotation
            for name, field in DownloadRequest.model_fields.items()
            if name not in {"id", "query", "user_id"}
        }
    },
)
