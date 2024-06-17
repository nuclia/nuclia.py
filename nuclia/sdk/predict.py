from typing import AsyncIterator, Dict, Iterator, List, Optional, Union

from nuclia.data import get_auth
from nuclia.decorators import nua
from nuclia.lib.nua import AsyncNuaClient, NuaClient
from nuclia.lib.nua_responses import (
    ChatModel,
    ChatResponse,
    ConfigSchema,
    GenerativeChunk,
    GenerativeFullResponse,
    LearningConfigurationCreation,
    QueryInfo,
    Sentence,
    StoredLearningConfiguration,
    SummarizedModel,
    Tokens,
    UserPrompt,
)
from nuclia.sdk.auth import NucliaAuth


class NucliaPredict:
    @property
    def _auth(self) -> NucliaAuth:
        auth = get_auth()
        return auth

    @nua
    def schema(self, kbid: Optional[str] = None, **kwargs) -> ConfigSchema:
        nc: NuaClient = kwargs["nc"]
        return nc.schema_predict(kbid)

    @nua
    def config(self, kbid: str, **kwargs) -> StoredLearningConfiguration:
        nc: NuaClient = kwargs["nc"]
        return nc.config_predict(kbid)

    @nua
    def set_config(self, kbid: str, config: LearningConfigurationCreation, **kwargs):
        nc: NuaClient = kwargs["nc"]
        nc.add_config_predict(kbid, config)

    @nua
    def del_config(self, kbid: str, **kwargs):
        nc: NuaClient = kwargs["nc"]
        nc.del_config_predict(kbid)

    @nua
    def sentence(self, text: str, model: Optional[str] = None, **kwargs) -> Sentence:
        nc: NuaClient = kwargs["nc"]
        return nc.sentence_predict(text, model)

    @nua
    def query(
        self,
        text: str,
        semantic_model: Optional[str] = None,
        token_model: Optional[str] = None,
        generative_model: Optional[str] = None,
        **kwargs,
    ) -> QueryInfo:
        nc: NuaClient = kwargs["nc"]
        return nc.query_predict(
            text,
            semantic_model=semantic_model,
            token_model=token_model,
            generative_model=generative_model,
        )

    @nua
    def generate(
        self, text: Union[str, ChatModel], model: Optional[str] = None, **kwargs
    ) -> GenerativeFullResponse:
        nc: NuaClient = kwargs["nc"]
        if isinstance(text, str):
            body = ChatModel(
                question="",
                retrieval=False,
                user_id="Nuclia PY CLI",
                user_prompt=UserPrompt(prompt=text),
            )
        else:
            body = text

        return nc.generate(body, model)

    @nua
    def generate_stream(
        self, text: Union[str, ChatModel], model: Optional[str] = None, **kwargs
    ) -> Iterator[GenerativeChunk]:
        nc: NuaClient = kwargs["nc"]
        if isinstance(text, str):
            body = ChatModel(
                question="",
                retrieval=False,
                user_id="Nuclia PY CLI",
                user_prompt=UserPrompt(prompt=text),
            )
        else:
            body = text

        for chunk in nc.generate_stream(body, model):
            yield chunk

    @nua
    def tokens(self, text: str, model: Optional[str] = None, **kwargs) -> Tokens:
        nc: NuaClient = kwargs["nc"]
        return nc.tokens_predict(text, model)

    @nua
    def summarize(
        self, texts: Dict[str, str], model: Optional[str] = None, **kwargs
    ) -> SummarizedModel:
        nc: NuaClient = kwargs["nc"]
        return nc.summarize(texts, model)

    @nua
    def rag(
        self, question: str, context: List[str], model: Optional[str] = None, **kwargs
    ) -> GenerativeFullResponse:
        nc: NuaClient = kwargs["nc"]
        body = ChatModel(
            question=question,
            retrieval=True,
            user_id="Nuclia PY CLI",
            query_context=context,
        )

        return nc.generate(body, model)


class AsyncNucliaPredict:
    @property
    def _auth(self) -> NucliaAuth:
        auth = get_auth()
        return auth

    @nua
    async def schema(self, kbid: Optional[str] = None, **kwargs) -> ConfigSchema:
        nc: AsyncNuaClient = kwargs["nc"]
        return await nc.schema_predict(kbid)

    @nua
    async def config(
        self, kbid: Optional[str] = None, **kwargs
    ) -> StoredLearningConfiguration:
        nc: AsyncNuaClient = kwargs["nc"]
        return await nc.config_predict(kbid)

    @nua
    async def set_config(
        self, kbid: str, config: LearningConfigurationCreation, **kwargs
    ):
        nc: AsyncNuaClient = kwargs["nc"]
        await nc.add_config_predict(kbid, config)

    @nua
    async def sentence(
        self, text: str, model: Optional[str] = None, **kwargs
    ) -> Sentence:
        nc: AsyncNuaClient = kwargs["nc"]
        return await nc.sentence_predict(text, model)

    @nua
    async def generate(
        self, text: Union[str, ChatModel], model: Optional[str] = None, **kwargs
    ) -> GenerativeFullResponse:
        nc: AsyncNuaClient = kwargs["nc"]
        if isinstance(text, str):
            body = ChatModel(
                question="",
                retrieval=False,
                user_id="Nuclia PY CLI",
                user_prompt=UserPrompt(prompt=text),
            )
        else:
            body = text
        return await nc.generate(body, model)

    @nua
    async def generate_stream(
        self, text: Union[str, ChatModel], model: Optional[str] = None, **kwargs
    ) -> AsyncIterator[GenerativeChunk]:
        nc: AsyncNuaClient = kwargs["nc"]
        if isinstance(text, str):
            body = ChatModel(
                question="",
                retrieval=False,
                user_id="Nuclia PY CLI",
                user_prompt=UserPrompt(prompt=text),
            )
        else:
            body = text

        async for chunk in nc.generate_stream(body, model):
            yield chunk

    @nua
    async def tokens(self, text: str, model: Optional[str] = None, **kwargs) -> Tokens:
        nc: AsyncNuaClient = kwargs["nc"]
        return await nc.tokens_predict(text, model)

    @nua
    async def query(
        self,
        text: str,
        semantic_model: Optional[str] = None,
        token_model: Optional[str] = None,
        generative_model: Optional[str] = None,
        **kwargs,
    ) -> QueryInfo:
        nc: AsyncNuaClient = kwargs["nc"]
        return await nc.query_predict(
            text,
            semantic_model=semantic_model,
            token_model=token_model,
            generative_model=generative_model,
        )

    @nua
    async def summarize(
        self, texts: Dict[str, str], model: Optional[str] = None, **kwargs
    ) -> SummarizedModel:
        nc: AsyncNuaClient = kwargs["nc"]
        return await nc.summarize(texts, model)

    @nua
    async def rag(
        self, question: str, context: List[str], model: Optional[str] = None, **kwargs
    ) -> ChatResponse:
        nc: AsyncNuaClient = kwargs["nc"]
        return await nc.generate_retrieval(question, context, model)
