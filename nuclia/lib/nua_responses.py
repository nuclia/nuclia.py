from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union, cast

import pydantic
from pydantic import BaseModel, Field, RootModel, model_validator
from typing_extensions import Annotated, Self


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
    JSON = 4


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
