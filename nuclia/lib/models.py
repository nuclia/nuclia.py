from typing import TypeVar
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator, create_model
from typing import Generic
from typing import Annotated
from typing import Optional, Any
from collections import defaultdict
from enum import Enum
import re

T = TypeVar("T")


class EventType(str, Enum):
    VISITED = "VISITED"
    MODIFIED = "MODIFIED"
    DELETED = "DELETED"
    NEW = "NEW"
    STARTED = "STARTED"
    STOPPED = "STOPPED"
    SEARCH = "SEARCH"
    PROCESSED = "PROCESSED"
    SUGGEST = "SUGGEST"
    CHAT = "CHAT"


class Pagination(BaseModel):
    limit: Annotated[int, Field(ge=0, le=1000)] = 10
    starting_after: Optional[int] = None
    ending_before: Optional[int] = None


class BaseConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GenericFilter(BaseConfigModel, Generic[T]):
    eq: Optional[T] = None
    gt: Optional[T] = None
    ge: Optional[T] = None
    lt: Optional[T] = None
    le: Optional[T] = None
    ne: Optional[T] = None
    isnull: Optional[bool] = None


class StringFilter(GenericFilter[str]):
    like: Optional[str] = None
    ilike: Optional[str] = None


class AuditMetadata(StringFilter):
    key: str


class UserType(str, Enum):
    USER = "user"
    NUAKEY = "nuakey"


class ClientType(str, Enum):
    API = "api"
    WIDGET = "widget"
    WEB = "web"
    DASHBOARD = "dashboard"
    DESKTOP = "desktop"
    CHROME_EXTENSION = "chrome_extension"


class QueryFiltersCommon(BaseConfigModel):
    id: Optional[BaseConfigModel] = Field(None)
    date: Optional[BaseConfigModel] = Field(None, serialization_alias="event_date")
    user_id: Optional[GenericFilter[str]] = None
    user_type: Optional[GenericFilter[UserType]] = None
    client_type: Optional[GenericFilter[ClientType]] = None
    total_duration: Optional[GenericFilter[float]] = None
    audit_metadata: Optional[list[AuditMetadata]] = Field(
        None, serialization_alias="data.user_request.audit_metadata"
    )


class QueryFiltersSearch(QueryFiltersCommon):
    question: Optional[StringFilter] = Field(
        None, serialization_alias="data.request.body"
    )
    resources_count: Optional[StringFilter] = Field(
        None,
        serialization_alias="data.resources_count",
    )
    filter: Optional[BaseConfigModel] = Field(
        None, serialization_alias="data.request.filter"
    )
    learning_id: Optional[BaseConfigModel] = Field(
        None, serialization_alias="data.request.learning_id"
    )


class QueryFiltersChat(QueryFiltersSearch):
    rephrased_question: Optional[StringFilter] = Field(
        None, serialization_alias="data.request.rephrased_question"
    )
    answer: Optional[StringFilter] = Field(
        None, serialization_alias="data.request.answer"
    )
    retrieved_context: Optional[BaseConfigModel] = Field(
        None, serialization_alias="data.request.context"
    )
    chat_history: Optional[BaseConfigModel] = Field(
        None, serialization_alias="data.request.chat_context"
    )
    feedback_good: Optional[StringFilter] = Field(
        None, serialization_alias="data.feedback.good"
    )
    feedback_comment: Optional[StringFilter] = Field(
        None, serialization_alias="data.feedback.feedback"
    )
    model: Optional[StringFilter] = Field(None, serialization_alias="data.model")
    rag_strategies_names: Optional[BaseConfigModel] = Field(
        None, serialization_alias="data.rag_strategies"
    )
    rag_strategies: Optional[BaseConfigModel] = Field(
        None, serialization_alias="data.user_request.rag_strategies"
    )
    status: Optional[StringFilter] = Field(
        None, serialization_alias="data.request.status"
    )
    time_to_first_char: Optional[BaseConfigModel] = Field(
        None, serialization_alias="data.generative_answer_first_chunk_time"
    )


DEFAULT_SHOW_VALUES = {"id", "date"}
DEFAULT_SHOW_SEARCH_VALUES = DEFAULT_SHOW_VALUES | {"question", "resources_count"}
DEFAULT_SHOW_CHAT_VALUES = DEFAULT_SHOW_SEARCH_VALUES | {
    "rephrased_question",
    "answer",
    "rag_strategies_names",
}

DEFAULT_SHOW_MAP: dict[str, set[str]] = defaultdict(lambda: DEFAULT_SHOW_VALUES)
DEFAULT_SHOW_MAP[EventType.SEARCH.value] = DEFAULT_SHOW_SEARCH_VALUES
DEFAULT_SHOW_MAP[EventType.CHAT.value] = DEFAULT_SHOW_CHAT_VALUES


def create_dynamic_model(name: str, base_model: QueryFiltersChat):
    field_definitions = {}
    field_type_map = {
        "id": int,
        "user_type": Optional[UserType],
        "client_type": Optional[ClientType],
        "total_duration": Optional[float],
        "time_to_first_char": Optional[float],
    }
    for field_name in base_model.model_fields.keys():
        field_type: Any = field_type_map.get(field_name, Optional[str])

        field_definitions[field_name] = (field_type, Field(default=None))

    return create_model(name, **field_definitions)  # type: ignore


ActivityLogsOutput = create_dynamic_model(
    name="ActivityLogsOutput",
    base_model=QueryFiltersChat,  # type: ignore
)


class ActivityLogsQueryResponse(BaseConfigModel):
    data: list[ActivityLogsOutput]  # type: ignore
    has_more: bool


class ActivityLogsQueryCommon(BaseConfigModel):
    year_month: str

    @field_validator("year_month")
    def validate_year_month(cls, value):
        if not re.match(r"^\d{4}-(0[1-9]|1[0-2])$", value):
            raise ValueError("year_month must be in the format YYYY-MM")
        return value

    @staticmethod
    def _validate_show(show: set[str], model: type[QueryFiltersCommon]):
        allowed_fields = list(model.__annotations__.keys())
        for field in show:
            if field.startswith("audit_metadata."):
                continue
            if field not in allowed_fields:
                raise ValueError(
                    f"{field} is not a field. List of fields: {allowed_fields}"
                )
        return show


class ActivityLogsQuery(ActivityLogsQueryCommon):
    show: set[str] = set()
    filters: QueryFiltersCommon
    pagination: Pagination

    @field_validator("show")
    def validate_show(cls, show: set[str]):
        return cls._validate_show(show=show, model=QueryFiltersCommon)


class ActivityLogsChatQuery(ActivityLogsQueryCommon):
    show: set[str] = set()
    filters: QueryFiltersChat
    pagination: Pagination

    @field_validator("show")
    def validate_show(cls, show: set[str]):
        return cls._validate_show(show=show, model=QueryFiltersChat)


class ActivityLogsSearchQuery(ActivityLogsQueryCommon):
    show: set[str] = set()
    filters: QueryFiltersSearch
    pagination: Pagination

    @field_validator("show")
    def validate_show(cls, show: set[str]):
        return cls._validate_show(show=show, model=QueryFiltersSearch)
