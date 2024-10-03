from typing import TypeVar
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator
from typing import Generic
from typing import Annotated
from typing import Optional
from enum import Enum
import re

T = TypeVar("T")


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


class UserMetadata(StringFilter):
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


class QueryFilters(BaseConfigModel):
    id: Optional[BaseConfigModel] = Field(
        None, json_schema_extra={"show_by_default": True, "fixed": True}
    )
    user_id: Optional[GenericFilter[str]] = None
    user_type: Optional[GenericFilter[UserType]] = None
    client_type: Optional[GenericFilter[ClientType]] = None
    total_duration: Optional[GenericFilter[float]] = None
    date: Optional[BaseConfigModel] = Field(
        None,
        serialization_alias="event_date",
        json_schema_extra={"show_by_default": True},
    )
    question: Optional[StringFilter] = Field(
        None, serialization_alias="data.request.body"
    )
    rephrased_question: Optional[StringFilter] = Field(
        None,
        serialization_alias="data.request.rephrased_question",
        json_schema_extra={"show_by_default": True},
    )
    answer: Optional[StringFilter] = Field(
        None,
        serialization_alias="data.request.answer",
        json_schema_extra={"show_by_default": True},
    )
    retrieved_context: Optional[BaseConfigModel] = Field(
        None, serialization_alias="data.request.context"
    )
    chat_history: Optional[BaseConfigModel] = Field(
        None, serialization_alias="data.request.chat_context"
    )
    filter: Optional[BaseConfigModel] = Field(
        None, serialization_alias="data.request.filter"
    )
    resources_count: Optional[StringFilter] = Field(
        None,
        serialization_alias="data.resources_count",
        json_schema_extra={"show_by_default": True},
    )
    learning_id: Optional[BaseConfigModel] = Field(
        None, serialization_alias="data.request.learning_id"
    )
    feedback_good: Optional[StringFilter] = Field(
        None, serialization_alias="data.feedback.good"
    )
    feedback_comment: Optional[StringFilter] = Field(
        None, serialization_alias="data.feedback.feedback"
    )
    model: Optional[StringFilter] = Field(None, serialization_alias="data.model")
    rag_strategies_names: Optional[BaseConfigModel] = Field(
        None,
        serialization_alias="data.rag_strategies",
        json_schema_extra={"show_by_default": True},
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
    audit_metadata: Optional[list[UserMetadata]] = Field(
        None, serialization_alias="data.user_request.audit_metadata"
    )


allowed_fields = list(QueryFilters.__annotations__.keys())
fixed_fields = [
    key
    for key, value in QueryFilters.model_fields.items()
    if value.json_schema_extra is not None
    and hasattr(value.json_schema_extra, "get")
    and value.json_schema_extra.get("fixed") is True
]
show_by_default_fields = [
    key
    for key, value in QueryFilters.model_fields.items()
    if value.json_schema_extra is not None
    and hasattr(value.json_schema_extra, "get")
    and value.json_schema_extra.get("show_by_default") is True
]


class ActivityLogsQuery(BaseConfigModel):
    year_month: str
    show: list[str] = show_by_default_fields
    filters: QueryFilters
    pagination: Pagination

    @field_validator("year_month")
    def validate_year_month(cls, value):
        if not re.match(r"^\d{4}-(0[1-9]|1[0-2])$", value):
            raise ValueError("year_month must be in the format YYYY-MM")
        return value

    @field_validator("show")
    def validate_option(cls, show: list[str]):
        for field in show:
            if field.startswith("audit_metadata."):
                continue
            if field not in allowed_fields:
                raise ValueError(
                    f"{field} is not a field. List of fields: {allowed_fields}"
                )

        for field in fixed_fields:
            if field not in show:
                show.insert(0, field)

        return show
