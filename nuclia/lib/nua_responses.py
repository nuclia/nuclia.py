from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union, cast
from dataclasses import dataclass
import pydantic
from pydantic import (
    BaseModel,
    Field,
    RootModel,
    ConfigDict,
    model_validator,
    field_validator,
    field_serializer,
    BeforeValidator,
)
from typing_extensions import Annotated, Self

from base64 import b64decode, b64encode

from google.protobuf.message import DecodeError
from google.protobuf.message import Message as ProtoMessage
from nucliadb_protos.writer_pb2 import Error
from nucliadb_protos.kb_usage_pb2 import Predict  # type: ignore
from enum import IntEnum

from nucliadb_protos.resources_pb2 import (
    FieldText,
    QuestionAnswers,
    FieldMetadata,
)


class GenerativeOption(BaseModel):
    name: str
    value: str
    user_prompt: Optional[str] = None
    user_key: Optional[str] = None


class Option(BaseModel):
    name: str
    value: str


class ConfigSchemaOptions(BaseModel):
    options: Union[List[GenerativeOption], List[Option]]
    default: Optional[str] = None
    create: bool = False
    update: bool = False
    multiple: bool = False


class ConfigSchemaElements(BaseModel):
    schemas: Dict[str, Any]
    create: bool = False
    update: bool = False


class ConfigSchema(BaseModel):
    semantic_model: ConfigSchemaOptions
    anonymization_model: ConfigSchemaOptions
    visual_labeling: Optional[ConfigSchemaOptions] = None
    generative_model: Optional[ConfigSchemaOptions] = None
    ner_model: Optional[ConfigSchemaOptions] = None
    relation_model: Optional[ConfigSchemaOptions] = None
    summary_model: Optional[ConfigSchemaOptions] = None
    summary: Optional[ConfigSchemaOptions] = None
    user_keys: Optional[ConfigSchemaElements] = None
    user_prompts: Optional[ConfigSchemaElements] = None
    summary_prompt: Optional[ConfigSchemaElements] = None
    prefer_markdown_generative_response: Optional[ConfigSchemaElements] = None


class Sentence(BaseModel):
    data: List[float]
    time: float


class Author(str, Enum):
    NUCLIA = "NUCLIA"
    USER = "USER"


class Message(BaseModel):
    author: Author
    text: str


class UserPrompt(BaseModel):
    prompt: str


class Image(BaseModel):
    content_type: str
    b64encoded: str


class ChatModel(BaseModel):
    question: str
    retrieval: bool = True
    user_id: str
    system: Optional[str] = None
    chat_history: List[Message] = []
    context: List[Message] = []
    query_context: Union[List[str], Dict[str, str]] = {}
    query_context_order: Dict[str, int] = {}
    truncate: Optional[bool] = False
    user_prompt: Optional[UserPrompt] = None
    citations: Optional[bool] = False
    citation_threshold: Optional[float] = Field(
        default=None,
        description="If citations is set to True, this will be the similarity threshold. Value between 0 and 1, lower values will produce more citations. If not set, it will be set to the optimized threshold found by Nuclia.",
        ge=0.0,
        le=1.0,
    )
    generative_model: Optional[str] = None
    max_tokens: Optional[int] = None
    query_context_images: Union[
        List[Image], Dict[str, Image]
    ] = {}  # base64.b64encode(image_file.read()).decode('utf-8')
    prefer_markdown: Optional[bool] = None
    json_schema: Optional[Dict[str, Any]] = None
    format_prompt: bool = True
    rerank_context: bool = Field(
        default=False,
        description="Whether to reorder the query context based on a reranker. This option will also make it so the first response will contain the scores given for each context piece.",
    )

    @model_validator(mode="after")
    def validate_model(self) -> Self:
        if self.prefer_markdown is True and self.json_schema is not None:
            raise ValueError("Can not setup markdown and JSON Schema at the same time")
        if self.citations is True and self.json_schema is not None:
            raise ValueError("Can not setup citations and JSON Schema at the same time")
        return self


class Token(BaseModel):
    text: str
    ner: str
    start: int
    end: int


class Tokens(BaseModel):
    tokens: List[Token]
    time: float


class SummarizeResource(BaseModel):
    fields: Dict[str, str]


class SummarizeModel(BaseModel):
    resources: Dict[str, SummarizeResource]


class SummarizedResource(BaseModel):
    summary: str
    tokens: int


class SummarizedModel(BaseModel):
    resources: Dict[str, SummarizedResource]
    summary: str = ""


class RephraseModel(RootModel[str]):
    pass


class WebhookConfig(BaseModel):
    uri: Optional[str] = None
    headers: Dict[str, str] = {}


# Pull models


class PullStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    EMPTY = "empty"


class PullResponse(BaseModel):
    status: PullStatus
    payload: Optional[bytes]
    msgid: Optional[str]


# Push models


class ProcessingQueueType(str, Enum):
    SHARED = "shared"
    PRIVATE = "private"


class Format(int, Enum):
    PLAIN = 0
    HTML = 1
    MARKDOWN = 2
    RST = 3
    KEEP_MARKDOWN = 4
    JSON = 5


class ProcessingMessageContent(BaseModel):
    text: Optional[str] = None
    format: Format
    attachments: Optional[List[str]] = None


class ProcessingMessage(BaseModel):
    timestamp: Optional[datetime] = None
    who: Optional[str] = None
    to: List[str] = []
    content: ProcessingMessageContent
    ident: str


class ProcessingConversation(BaseModel):
    messages: List[ProcessingMessage]


class LayoutFormat(int, Enum):
    FLAPSv1 = 0


class TypeBlock(int, Enum):
    TITLE = 0
    DESCRIPTION = 1
    RICHTEXT = 2
    TEXT = 3
    ATTACHMENTS = 4
    COMMENTS = 5
    CLASSIFICATIONS = 6


class ProcessingBlock(BaseModel):
    x: int
    y: int
    cols: int
    rows: int
    type: TypeBlock
    ident: str
    payload: str
    file: Optional[str] = None


class ProcessingLayoutDiff(BaseModel):
    format: LayoutFormat
    blocks: Dict[str, ProcessingBlock]


class LinkUpload(BaseModel):
    link: str
    headers: Dict[str, str]
    cookies: Dict[str, str]
    localstorage: Dict[str, str]


class Text(BaseModel):
    body: str
    format: Format


class Source(int, Enum):
    HTTP = 0
    INGEST = 1


def validate_uuid(value, handler, info):
    if not value:
        raise ValueError(f"Invalid uuid: '{value}'. Uuid must be a non-empty string.")
    try:
        return handler(value)
    except pydantic.ValidationError as e:
        if any(x["type"] == "string_pattern_mismatch" for x in e.errors()):
            raise ValueError(
                f"Invalid slug: '{value}'. Slug must be a string with only "
                "letters, numbers, underscores, colons and dashes."
            )
        else:
            raise e


RestrictedIDString = Annotated[
    str,
    pydantic.StringConstraints(pattern=r"^[a-z0-9_-]+$"),
    pydantic.WrapValidator(validate_uuid),
]


class PushProcessingOptions(BaseModel):
    # Enable ML processing
    ml_text: bool = True


class PushPayload(BaseModel):
    kbid: Optional[RestrictedIDString] = cast(RestrictedIDString, "default")
    uuid: Optional[RestrictedIDString] = None

    slug: Optional[str] = None
    source: Optional[Source] = None
    userid: Optional[str] = None

    # Generic Field
    genericfield: Dict[str, Text] = {}

    # New File
    filefield: Dict[str, str] = {}

    # New Link
    linkfield: Dict[str, LinkUpload] = {}

    # Diff on Text Field
    textfield: Dict[str, Text] = {}

    # Diff on a Layout Field
    layoutfield: Dict[str, ProcessingLayoutDiff] = {}

    # New conversations to process
    conversationfield: Dict[str, ProcessingConversation] = {}

    # List of available processing options (with default values)
    processing_options: Optional[PushProcessingOptions] = Field(
        default_factory=PushProcessingOptions
    )


class PublicPushPayload(PushPayload):
    # If provided, will override the webhookconfig on the nua-token (if any)
    webhook_config: Optional[WebhookConfig] = None


class PublicPushResponse(BaseModel):
    seqid: Optional[int] = None
    account_seq: Optional[int] = None
    queue: Optional[ProcessingQueueType] = None
    # On Public api, uuid may be generated by the proxy, so we need to return it to the user
    uuid: Optional[str] = None


class ProcessingStatusInfo(BaseModel):
    last_delivered_seqid: Optional[int] = (
        None  # When none, means we already don't have information about this queue
    )


class ProcessingStatus(BaseModel):
    shared: ProcessingStatusInfo
    account: Optional[ProcessingStatusInfo]


class ProcessRequestStatus(BaseModel):
    processing_id: str
    resource_id: Optional[str]
    kbid: Optional[str]
    title: Optional[str]
    labels: list[str]
    completed: bool
    scheduled: bool
    timestamp: datetime
    completed_at: Optional[datetime]
    scheduled_at: Optional[datetime]
    failed: bool = False
    retries: int = 0
    schedule_eta: float = 0.0
    schedule_order: int = 0
    response: Optional[str] = None


class ProcessRequestStatusResults(BaseModel):
    results: list[ProcessRequestStatus]
    cursor: Optional[str]


class PushResponseV2(BaseModel):
    processing_id: str


class Summary(str, Enum):
    EXTENDED = "extended"
    SIMPLE = "simple"


class SummaryPrompt(BaseModel):
    prompt: str


class OpenAIKey(BaseModel):
    key: str
    org: str


class AzureOpenAIKey(BaseModel):
    key: str
    url: str
    deployment: str
    model: str


class PalmKey(BaseModel):
    credentials: str
    location: str


class CohereKey(BaseModel):
    key: str


class AnthropicKey(BaseModel):
    key: str


class OpenAIUserPrompt(BaseModel):
    system: str
    prompt: str


class AzureUserPrompt(BaseModel):
    system: str
    prompt: str


class PalmUserPrompt(BaseModel):
    prompt: str


class CohereUserPrompt(BaseModel):
    prompt: str


class AnthropicUserPrompt(BaseModel):
    prompt: str


class TextGenerationUserPrompt(BaseModel):
    prompt: str


class UserPrompts(BaseModel):
    openai: Optional[OpenAIUserPrompt] = None
    azure_openai: Optional[AzureUserPrompt] = None
    palm: Optional[PalmUserPrompt] = None
    cohere: Optional[CohereUserPrompt] = None
    anthropic: Optional[AnthropicUserPrompt] = None
    text_generation: Optional[TextGenerationUserPrompt] = None


class UserLearningKeys(BaseModel):
    openai: Optional[OpenAIKey] = None
    azure_openai: Optional[AzureOpenAIKey] = None
    palm: Optional[PalmKey] = None
    cohere: Optional[CohereKey] = None
    anthropic: Optional[AnthropicKey] = None


class LearningConfigurationUpdate(BaseModel):
    # Validate its enum or string
    anonymization_model: Optional[str] = None
    visual_labeling: Optional[str] = None
    generative_model: Optional[str] = None
    ner_model: Optional[str] = None
    relation_model: Optional[str] = None
    user_keys: Optional[UserLearningKeys] = None
    user_prompts: Optional[UserPrompts] = None
    summary: Optional[Summary] = Summary.SIMPLE
    summary_model: Optional[str] = None
    summary_prompt: Optional[SummaryPrompt] = None
    resource_labelers_models: Optional[List[str]] = None
    paragraph_labelers_models: Optional[List[str]] = None
    intent_models: Optional[List[str]] = None


class LearningConfigurationCreation(LearningConfigurationUpdate):
    semantic_model: Optional[str] = None


class Empty(BaseModel):
    pass


class ChatResponse(BaseModel):
    answer: str

    @classmethod
    def model_validate(
        cls,
        obj: bytes,
        **kwargs,
    ) -> "ChatResponse":
        return ChatResponse(answer=obj.decode())


class StoredLearningConfiguration(BaseModel):
    resource_labelers_models: Optional[List[str]] = None
    paragraph_labelers_models: Optional[List[str]] = None
    intent_models: Optional[List[str]] = None

    semantic_model: str
    anonymization_model: str
    generative_model: str
    ner_model: str
    relation_model: str
    visual_labeling: str

    user_keys: Optional[UserLearningKeys] = None
    user_prompts: Optional[UserPrompts] = None

    semantic_vector_similarity: str

    semantic_vector_size: int

    semantic_threshold: float

    summary: str
    summary_model: str
    summary_prompt: Optional[SummaryPrompt] = None


class SentenceSearch(BaseModel):
    data: List[float] = []
    time: float


class Ner(BaseModel):
    text: str
    ner: str
    start: int
    end: int


class TokenSearch(BaseModel):
    tokens: List[Ner] = []
    time: float


class QueryInfo(BaseModel):
    language: str
    stop_words: List[str]
    semantic_threshold: float
    visual_llm: bool
    max_context: int
    entities: Optional[TokenSearch]
    sentence: Optional[SentenceSearch]


ENDPOINT_DESCRIPTION = """\
Apply any or all of the Data Augmentation Agents configured in a Knowledge Box to a given field."""


class OperationType(IntEnum):
    """
    XXX: Hey developer! This enum has to match the fields of `message Operation` below
    """

    graph = 0
    label = 1
    ask = 2
    qa = 3
    extract = 4
    prompt_guard = 5
    llama_guard = 6


# To accept both string and int values for OperationType
def validate_operation_type(value: Union[str, int]):
    if isinstance(value, str):
        try:
            return OperationType[value]
        except KeyError:
            raise ValueError(
                f"Invalid OperationType {value}, must be one of {OperationType._member_names_}"
            )
    return value


OperationTypeString = Annotated[
    OperationType,
    BeforeValidator(validate_operation_type),
]


class NameOperationFilter(BaseModel):
    """
    Filtering Data Augmentation Agents by operation type and task names.
    """

    operation_type: OperationTypeString = Field(
        ..., description="Type of the operation"
    )
    task_names: list[str] = Field(
        default_factory=list,
        description="List of task names. If None or empty, all tasks for that operation are applied.",
    )


@dataclass
class NewTextField:
    text_field: FieldText
    destination: str


class AppliedDataAugmentation(BaseModel):
    # Since we have protos as fields, we need to enable arbitrary_types_allowed
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        # Custom encoding to be able to serialize protobuf messages
        json_encoders={Message: lambda m: b64encode(m.SerializeToString()).decode()},
    )

    qas: Optional[QuestionAnswers] = Field(
        default=None,
        description="Question and answers generated by the Question Answers agent",
    )
    new_text_fields: List[NewTextField] = Field(
        default_factory=list,
        description="New text fields. Only generated by the Labeler agent as of now.",
    )
    predicts: List[Predict] = Field(
        default_factory=list,
        description="Reports of consumption made by the agents",
    )
    errors: List[str] = Field(
        default_factory=list,
        description="Errors that occurred during the augmentation process",
    )
    errors_fields: List[Error] = Field(
        default_factory=list,
    )
    changed: bool = Field(
        default=True,
        description="Indicates if the FieldMetadata was changed by the agents",
    )


class FieldInfo(BaseModel):
    """
    Model to represent the field information required
    """

    # Since we have protos as fields, we need to enable arbitrary_types_allowed
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )

    text: str = Field(..., title="The text of the field")
    metadata: FieldMetadata = Field(
        default_factory=FieldMetadata,
        title="The metadata of the field as a base64 string serialized nucliadb_protos.resources.FieldMetadata protobuf",
    )
    field_id: str = Field(
        ...,
        title="The field ID of the field (rid/field_type/field[/split]) or any unique identifier",
    )

    @field_serializer("metadata")
    def serialize_metadata(self, metadata: FieldMetadata, _info):
        return b64decode(metadata.SerializeToString()).decode()


class RunAgentsRequest(BaseModel):
    """
    Model to represent a request for the Augment model
    The text will be augmented with the Knowledge Box's configured Data Augmentation Agents
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "fields": [
                        {
                            "field_id": "rid/field_type/field",
                            "text": "Field text",
                            "metadata": {
                                "paragraphs": [{"start": 0, "end": 10}],
                            },
                        }
                    ],
                    "user_id": "my_user",
                    "enable_webhooks": True,
                },
                {
                    "fields": [
                        [
                            {
                                "field_id": "my_field",
                                "text": "Field text",
                            }
                        ]
                    ],
                    "filters": [
                        {
                            "operation": "graph",
                            "task_names": ["task1", "task2"],
                        },
                        {"operation": "label"},
                    ],
                    "user_id": "my_user",
                    "enable_webhooks": False,
                },
            ]
        }
    )
    fields: list[FieldInfo] = Field(
        ...,
        title="The fields to be augmented with the Knowledge Box's Data Augmentation Agents",
    )
    user_id: str = Field(..., title="The user ID of the user making the request")
    filters: Optional[list[NameOperationFilter]] = Field(
        title="Filters to select which Data Augmentation Agents are applied to the text. If empty, all configured agents for the Knowledge Box are applied.",
    )
    enable_webhooks: bool = Field(
        False,
        title="Whether to enable the triggering of the configured webhooks for each applied Data Augmentation Agent",
    )

    @field_validator("filters", mode="after")
    def validate_filters(
        cls, filters: list[NameOperationFilter]
    ) -> list[NameOperationFilter]:
        # Check that the filters are unique
        seen = set()
        for filter in filters:
            if filter.operation_type in seen:
                raise ValueError(
                    f"Duplicate operation type for type `{filter.operation_type.name}` in filters"
                )
            seen.add(filter.operation_type)
        return filters


class AugmentedField(BaseModel):
    # Since we have protos as fields, we need to enable arbitrary_types_allowed
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        # Custom encoding to be able to serialize protobuf messages
        json_encoders={
            ProtoMessage: lambda m: b64encode(m.SerializeToString()).decode()
        },
    )
    metadata: FieldMetadata = Field(
        ...,
        title="The updated metadata of the field as a base64 string serialized nucliadb_protos.resources.FieldMetadata protobuf",
    )
    applied_data_augmentation: AppliedDataAugmentation = Field(
        ..., title="The results of the Applied Data Augmentation"
    )
    input_nuclia_tokens: float = Field(
        ..., title="The number of input Nuclia tokens consumed for the field"
    )
    output_nuclia_tokens: float = Field(
        ..., title="The number of output Nuclia tokens consumed for the field"
    )
    time: float = Field(
        ..., title="The time taken to execute the Data Augmentation agents to the field"
    )

    @field_serializer("metadata")
    def serialize_metadata(self, metadata: FieldMetadata, _info):
        return b64decode(metadata.SerializeToString()).decode()

    @field_validator("metadata", mode="before")
    def validate_metadata(cls, metadata: str) -> FieldMetadata:
        try:
            return FieldMetadata.FromString(b64decode(metadata))
        except DecodeError:
            raise ValueError("Invalid FieldMetadata protobuf")


class RunAgentsResponse(BaseModel):
    results: dict[str, AugmentedField] = Field(
        ...,
        title="Pairs of augmented FieldMetadata and Data Augmentation results by field id",
    )
