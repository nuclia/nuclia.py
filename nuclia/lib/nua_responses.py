from datetime import datetime
from enum import Enum, IntEnum
from typing import Any, Dict, List, Literal, Optional, Union, cast

import pydantic
from nuclia_models.common.consumption import Consumption
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
    consumption: Optional[Consumption] = None


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


class Tool(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Schema of the tool"
    )


class Reasoning(BaseModel):
    display: bool = Field(
        default=True,
        description="Whether to display the reasoning steps in the response.",
    )
    effort: Literal["low", "medium", "high"] = Field(
        default="medium",
        description=(
            "Level of reasoning effort. Used by OpenAI models to control the depth of reasoning. "
            "This parameter will be automatically mapped to budget_tokens "
            "if the chosen model does not support effort."
        ),
    )
    budget_tokens: int = Field(
        default=15_000,
        description=(
            "Token budget for reasoning. Used by Anthropic or Google models to limit the number of "
            "tokens used for reasoning. This parameter will be automatically mapped to effort "
            "if the chosen model does not support budget_tokens."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def set_budget_tokens_or_effort(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "budget_tokens" not in data and "effort" not in data:
                return data

            effort_map = {"low": 7500, "medium": 15_000, "high": 30_000}
            if "budget_tokens" not in data:
                if data["effort"] in effort_map:
                    data["budget_tokens"] = effort_map[data["effort"]]
                else:
                    raise ValueError(
                        f"Invalid effort value: {data['effort']}. "
                        f"Valid values are: {', '.join(effort_map.keys())}."
                    )
            if "effort" not in data:
                budget_tokens = data["budget_tokens"]
                if not isinstance(budget_tokens, int):
                    raise ValueError(
                        f"Invalid budget_tokens value: {budget_tokens}. "
                        "It must be an integer."
                    )
                if budget_tokens <= effort_map["low"]:
                    data["effort"] = "low"
                elif budget_tokens <= effort_map["medium"]:
                    data["effort"] = "medium"
                else:
                    data["effort"] = "high"

        return data


class CitationsType(str, Enum):
    NONE = "none"
    DEFAULT = "default"
    LLM_FOOTNOTES = "llm_footnotes"


class ToolChoiceAuto(BaseModel):
    type: Literal["auto"] = "auto"


class ToolChoiceNone(BaseModel):
    type: Literal["none"] = "none"


class ToolChoiceRequired(BaseModel):
    type: Literal["required"] = "required"


class ToolChoiceForced(BaseModel):
    type: Literal["forced"] = "forced"
    name: str


class ChatModel(BaseModel):
    question: str
    retrieval: bool = True
    user_id: str
    system: Optional[str] = None
    chat_history: List[Message] = []
    context: List[Message] = []
    query_context: Union[List[str], Dict[str, str]] = {}
    query_context_order: Dict[str, int] = {}
    truncate: Optional[bool] = True
    user_prompt: Optional[UserPrompt] = None
    citations: Union[bool, None, CitationsType] = Field(
        default=None,
        description="Whether to include citations in the response. "
        "If set to None or False, no citations will be computed. "
        "If set to True or 'default', citations will be computed after answer generation and send as a separate `CitationsGenerativeResponse` chunk"
        "If set to 'llm_footnotes', citations will be included in the LLM's response as markdown-styled footnotes. A `FootnoteCitationsGenerativeResponse` chunk will also be sent to map footnote ids to context keys in the `query_context`.",
    )
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
    tools: List[Tool] = Field(
        default_factory=list, description="List of tools to choose"
    )
    tool_choice: Union[
        ToolChoiceAuto, ToolChoiceNone, ToolChoiceRequired, ToolChoiceForced
    ] = Field(
        default=ToolChoiceRequired(),
        discriminator="type",
        description=(
            "Tool choice strategy. "
            "`auto`: The model decides whether to use a tool or not based on the prompt and available tools. "
            "`required` (default): A tool must be used."
            "`none`: Disables tool usage even if tools are provided."
            "`forced`: Forces the use of a specific tool provided in `name`."
            "Important: Not all model providers support all tool choice strategies, its a best effort feature."
        ),
    )
    reasoning: Union[Reasoning, bool] = Field(
        default=False,
        description=(
            "Reasoning options for the generative model. "
            "Set to True to enable default reasoning, False to disable, or provide a Reasoning object for custom options."
        ),
    )
    image_generation: bool = Field(
        default=False,
        description="Whether to enable image generation in the response.",
    )

    @model_validator(mode="after")
    def validate_model(self) -> Self:
        if self.prefer_markdown is True and self.json_schema is not None:
            raise ValueError("Can not setup markdown and JSON Schema at the same time")
        if self.citations is True and self.json_schema is not None:
            raise ValueError("Can not setup citations and JSON Schema at the same time")
        if self.citations is True and len(self.tools) > 0:
            raise ValueError("Can not setup citations and Tools at the same time")
        if len(self.tools) > 0 and self.json_schema is not None:
            raise ValueError("Can not setup Tools and JSON Schema at the same time")
        return self

    @model_validator(mode="after")
    def check_reasoning_budget_vs_max_tokens(self) -> "ChatModel":
        if isinstance(self.reasoning, Reasoning) and self.max_tokens is not None:
            if self.reasoning.budget_tokens >= self.max_tokens:
                raise ValueError(
                    f"`budget_tokens` ({self.reasoning.budget_tokens}) cannot be greater or equal than `max_tokens` ({self.max_tokens})."
                )
        return self


class Token(BaseModel):
    text: str
    ner: str
    start: int
    end: int


class Tokens(BaseModel):
    tokens: List[Token]
    time: float
    consumption: Optional[Consumption] = None


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
    consumption: Optional[Consumption] = None


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


class SimilarityFunction(IntEnum):
    # Keep this in sync with SimilarityFunction in config.proto
    # It's an IntEnum to match the protobuf definition
    DOT = 0
    COSINE = 1


class SemanticConfig(BaseModel):
    # Keep this in sync with SemanticConfig in config.proto
    similarity: SimilarityFunction
    size: int
    threshold: float
    max_tokens: Optional[int] = None
    matryoshka_dims: list[int] = []
    external: bool = False


class StoredLearningConfiguration(BaseModel):
    resource_labelers_models: Optional[List[str]] = None
    paragraph_labelers_models: Optional[List[str]] = None
    intent_models: Optional[List[str]] = None

    default_semantic_model: Optional[str] = None
    semantic_models: Optional[list[str]] = Field(default_factory=list[str])
    semantic_model_configs: dict[str, SemanticConfig] = {}
    semantic_model: str
    anonymization_model: str
    generative_model: str
    ner_model: str
    relation_model: str
    visual_labeling: Optional[str] = None

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
    consumption: Optional[Consumption] = None


class Ner(BaseModel):
    text: str
    ner: str
    start: int
    end: int


class TokenSearch(BaseModel):
    tokens: List[Ner] = []
    time: float
    consumption: Optional[Consumption] = None


class QueryInfo(BaseModel):
    language: str
    stop_words: List[str]
    semantic_threshold: float
    visual_llm: bool
    max_context: int
    entities: Optional[TokenSearch]
    sentence: Optional[SentenceSearch]


class RerankModel(BaseModel):
    question: str
    user_id: str
    context: dict[str, str] = {}


class RerankResponse(BaseModel):
    context_scores: dict[str, float] = Field(
        description="Scores for each context given by the reranker"
    )
    consumption: Optional[Consumption] = None
