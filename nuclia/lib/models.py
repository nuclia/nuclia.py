from nuclia_models.events.activity_logs import (
    ActivityLogsQueryResponse,
    BaseConfigModel,
)


class ActivityLogsOutput(BaseConfigModel):
    data: list[ActivityLogsQueryResponse]  # type: ignore
    has_more: bool
