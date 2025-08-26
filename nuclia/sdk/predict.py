from typing import AsyncIterator, Iterator, Optional, Union

from nuclia_models.predict.generative_responses import (
    GenerativeChunk,
    GenerativeFullResponse,
)
from nuclia_models.predict.remi import RemiRequest, RemiResponse

from nuclia.data import get_auth
from nuclia.decorators import nua
from nuclia.lib.nua import AsyncNuaClient, ContextItem, NuaClient
from nuclia.lib.nua_responses import (
    ChatModel,
    ChatResponse,
    ConfigSchema,
    LearningConfigurationCreation,
    QueryInfo,
    RerankModel,
    RerankResponse,
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
    def sentence(
        self,
        text: str,
        model: Optional[str] = None,
        show_consumption: bool = False,
        **kwargs,
    ) -> Sentence:
        nc: NuaClient = kwargs["nc"]
        return nc.sentence_predict(
            text,
            model,
            extra_headers={"X-Show-Consumption": str(show_consumption).lower()},
        )

    @nua
    def query(
        self,
        text: str,
        semantic_model: Optional[str] = None,
        token_model: Optional[str] = None,
        generative_model: Optional[str] = None,
        show_consumption: bool = False,
        **kwargs,
    ) -> QueryInfo:
        nc: NuaClient = kwargs["nc"]
        return nc.query_predict(
            text=text,
            semantic_model=semantic_model,
            token_model=token_model,
            generative_model=generative_model,
            extra_headers={"X-Show-Consumption": str(show_consumption).lower()},
        )

    @nua
    def generate(
        self,
        text: Union[str, ChatModel],
        model: Optional[str] = None,
        show_consumption: bool = False,
        **kwargs,
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

        return nc.generate(
            body=body,
            model=model,
            extra_headers={"X-Show-Consumption": str(show_consumption).lower()},
        )

    @nua
    def generate_stream(
        self,
        text: Union[str, ChatModel],
        model: Optional[str] = None,
        show_consumption: bool = False,
        **kwargs,
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

        for chunk in nc.generate_stream(
            body=body,
            model=model,
            extra_headers={"X-Show-Consumption": str(show_consumption).lower()},
        ):
            yield chunk

    @nua
    def tokens(
        self,
        text: str,
        model: Optional[str] = None,
        show_consumption: bool = False,
        **kwargs,
    ) -> Tokens:
        nc: NuaClient = kwargs["nc"]
        return nc.tokens_predict(
            text,
            model,
            extra_headers={"X-Show-Consumption": str(show_consumption).lower()},
        )

    @nua
    def summarize(
        self,
        texts: dict[str, str],
        model: Optional[str] = None,
        show_consumption: bool = False,
        **kwargs,
    ) -> SummarizedModel:
        nc: NuaClient = kwargs["nc"]
        return nc.summarize(
            documents=texts,
            model=model,
            extra_headers={"X-Show-Consumption": str(show_consumption).lower()},
        )

    @nua
    def rephrase(
        self,
        question: str,
        user_context: Optional[list[str]] = None,
        context: Optional[list[Union[dict, ContextItem]]] = None,
        model: Optional[str] = None,
        prompt: Optional[str] = None,
        **kwargs,
    ) -> str:
        nc: NuaClient = kwargs["nc"]
        return nc.rephrase(question, user_context, context, model, prompt).root

    @nua
    def rag(
        self,
        question: str,
        context: list[str],
        model: Optional[str] = None,
        show_consumption: bool = False,
        **kwargs,
    ) -> GenerativeFullResponse:
        nc: NuaClient = kwargs["nc"]
        body = ChatModel(
            question=question,
            retrieval=True,
            user_id="Nuclia PY CLI",
            query_context=context,
        )

        return nc.generate(
            body,
            model,
            extra_headers={"X-Show-Consumption": str(show_consumption).lower()},
        )

    @nua
    def remi(
        self,
        request: Optional[RemiRequest] = None,
        show_consumption: bool = False,
        **kwargs,
    ) -> RemiResponse:
        """
        Perform a REMi evaluation over a RAG experience

        **SDK Usage:**
        nuclia nua predict remi --user_id="user" --question="question" --answer="answer" --contexts='["context1", "contex2"]'

        :param request: RemiRequest
        :return: RemiResponse
        """
        # If we didn't get a request model, we'll build it from the kwargs for SDK compatibility
        if request is None:
            request = RemiRequest(**kwargs)
        nc: NuaClient = kwargs["nc"]
        return nc.remi(
            request=request,
            extra_headers={"X-Show-Consumption": str(show_consumption).lower()},
        )

    @nua
    def rerank(
        self, request: RerankModel, show_consumption: bool = False, **kwargs
    ) -> RerankResponse:
        """
        Perform a reranking of the results based on the question and context provided.

        :param request: RerankModel
        :return: RerankResponse
        """
        nc: NuaClient = kwargs["nc"]
        return nc.rerank(
            request,
            extra_headers={"X-Show-Consumption": str(show_consumption).lower()},
        )


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
    async def del_config(self, kbid: str, **kwargs):
        nc: AsyncNuaClient = kwargs["nc"]
        await nc.del_config_predict(kbid)

    @nua
    async def sentence(
        self,
        text: str,
        model: Optional[str] = None,
        show_consumption: bool = False,
        **kwargs,
    ) -> Sentence:
        nc: AsyncNuaClient = kwargs["nc"]
        return await nc.sentence_predict(
            text,
            model,
            extra_headers={"X-Show-Consumption": str(show_consumption).lower()},
        )

    @nua
    async def generate(
        self,
        text: Union[str, ChatModel],
        model: Optional[str] = None,
        show_consumption: bool = False,
        **kwargs,
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
        return await nc.generate(
            body=body,
            model=model,
            extra_headers={"X-Show-Consumption": str(show_consumption).lower()},
        )

    @nua
    async def generate_stream(
        self,
        text: Union[str, ChatModel],
        model: Optional[str] = None,
        show_consumption: bool = False,
        **kwargs,
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

        async for chunk in nc.generate_stream(
            body=body,
            model=model,
            extra_headers={"X-Show-Consumption": str(show_consumption).lower()},
        ):
            yield chunk

    @nua
    async def tokens(
        self,
        text: str,
        model: Optional[str] = None,
        show_consumption: bool = False,
        **kwargs,
    ) -> Tokens:
        nc: AsyncNuaClient = kwargs["nc"]
        return await nc.tokens_predict(
            text,
            model,
            extra_headers={"X-Show-Consumption": str(show_consumption).lower()},
        )

    @nua
    async def query(
        self,
        text: str,
        semantic_model: Optional[str] = None,
        token_model: Optional[str] = None,
        generative_model: Optional[str] = None,
        show_consumption: bool = False,
        **kwargs,
    ) -> QueryInfo:
        nc: AsyncNuaClient = kwargs["nc"]
        return await nc.query_predict(
            text=text,
            semantic_model=semantic_model,
            token_model=token_model,
            generative_model=generative_model,
            extra_headers={"X-Show-Consumption": str(show_consumption).lower()},
        )

    @nua
    async def summarize(
        self,
        texts: dict[str, str],
        model: Optional[str] = None,
        show_consumption: bool = False,
        **kwargs,
    ) -> SummarizedModel:
        nc: AsyncNuaClient = kwargs["nc"]
        return await nc.summarize(
            documents=texts,
            model=model,
            extra_headers={"X-Show-Consumption": str(show_consumption).lower()},
        )

    @nua
    async def rephrase(
        self,
        question: str,
        user_context: Optional[list[str]] = None,
        context: Optional[list[Union[dict, ContextItem]]] = None,
        model: Optional[str] = None,
        prompt: Optional[str] = None,
        **kwargs,
    ) -> str:
        nc: AsyncNuaClient = kwargs["nc"]
        return (await nc.rephrase(question, user_context, context, model, prompt)).root

    @nua
    async def rag(
        self, question: str, context: list[str], model: Optional[str] = None, **kwargs
    ) -> ChatResponse:
        nc: AsyncNuaClient = kwargs["nc"]
        return await nc.generate_retrieval(question, context, model)

    @nua
    async def remi(
        self,
        request: Optional[RemiRequest] = None,
        show_consumption: bool = False,
        **kwargs,
    ) -> RemiResponse:
        """
        Perform a REMi evaluation over a RAG experience

        :param request: RemiRequest
        :return: RemiResponse
        """
        # If we didn't get a request model, we'll build it from the kwargs for SDK compatibility
        if request is None:
            request = RemiRequest(**kwargs)

        nc: AsyncNuaClient = kwargs["nc"]
        return await nc.remi(
            request=request,
            extra_headers={"X-Show-Consumption": str(show_consumption).lower()},
        )

    @nua
    async def rerank(
        self, request: RerankModel, show_consumption: bool = False, **kwargs
    ) -> RerankResponse:
        """
        Perform a reranking of the results based on the question and context provided.

        :param request: RerankModel
        :return: RerankResponse
        """
        nc: AsyncNuaClient = kwargs["nc"]
        return await nc.rerank(
            request,
            extra_headers={"X-Show-Consumption": str(show_consumption).lower()},
        )
