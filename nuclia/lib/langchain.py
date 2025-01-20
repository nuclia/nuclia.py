import json

from typing import Optional, Dict, List, Any, Iterator, AsyncIterator
from datetime import datetime, timezone
from base64 import b64decode

try:
    from langchain_core.language_models import BaseChatModel
    from langchain_core.callbacks import (
        CallbackManagerForLLMRun,
        AsyncCallbackManagerForLLMRun,
    )
    from langchain_core.messages import BaseMessage, AIMessage, AIMessageChunk
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_core.outputs import (
        ChatResult,
        ChatGeneration,
        ChatGenerationChunk,
    )

except ImportError:
    raise ImportError(
        "The 'langchain_core' library is required to use this functionality. "
        "Install it with: pip install nuclia[langchain]"
    )

from pydantic import Field

# Nuclia (sync & async)
from nuclia.lib.nua import NuaClient, AsyncNuaClient
from nuclia.sdk.predict import NucliaPredict, AsyncNucliaPredict
from nuclia.lib.nua_responses import ChatModel, UserPrompt
from nuclia_models.predict.generative_responses import (
    GenerativeFullResponse,
    TextGenerativeResponse,
)


class NucliaNuaChat(BaseChatModel):
    """
    A LangChain-compatible ChatModel that uses nua client under the hood
    """

    model_name: str = Field(
        ..., description="Which model to call, e.g. 'chatgpt-azure-4o'"
    )
    token: str = Field(..., description="Nua api Key")
    user_id: str = Field("nuclia-nua-chat", description="User ID for the chat session")
    system_prompt: Optional[str] = Field(
        None, description="Optional system instructions"
    )
    query_context: Optional[Dict[str, str]] = Field(
        None, description="Extra context for the LLM"
    )

    region_base_url: Optional[str] = None
    nc_sync: Optional[NuaClient] = None
    predict_sync: Optional[NucliaPredict] = None
    nc_async: Optional[AsyncNuaClient] = None
    predict_async: Optional[AsyncNucliaPredict] = None

    def __init__(self, **data: Any):
        super().__init__(**data)

        if self.token:
            regional_url, expiration_date = self._parse_token(self.token)
            now = datetime.now(timezone.utc)
            if expiration_date <= now:
                raise ValueError("Expired nua token")
            self.region_base_url = regional_url

        self.nc_sync = NuaClient(
            region=self.region_base_url,
            token=self.token,
            account="",  # Not needed for current implementation, required by the client
        )
        self.predict_sync = NucliaPredict()

        self.nc_async = AsyncNuaClient(
            region=self.region_base_url,
            token=self.token,
            account="",  # Not needed for current implementation, required by the client
        )
        self.predict_async = AsyncNucliaPredict()

    @staticmethod
    def _parse_token(token: str):
        parts = token.split(".")
        if len(parts) < 3:
            raise ValueError("Invalid JWT token, missing segments")

        b64_payload = parts[1]
        payload = json.loads(b64decode(b64_payload + "=="))
        regional_url = payload["iss"]
        expiration_date = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        return regional_url, expiration_date

    @property
    def _llm_type(self) -> str:
        return "nuclia-nua-chat"

    @property
    def _identifying_params(self) -> dict:
        return {"model_name": self.model_name, "region_base_url": self.region_base_url}

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        if not self.predict_sync or not self.nc_sync:
            raise RuntimeError("Sync clients not initialized.")

        question, user_prompt_str = self._combine_messages(messages)

        body = ChatModel(
            question=question,
            retrieval=False,
            user_id=self.user_id,
            system=self.system_prompt,
            user_prompt=UserPrompt(prompt=user_prompt_str),
            query_context=self.query_context or {},
        )
        response: GenerativeFullResponse = self.predict_sync.generate(
            text=body,
            model=self.model_name,
            nc=self.nc_sync,
        )
        ai_message = AIMessage(content=response.answer)

        return ChatResult(generations=[ChatGeneration(message=ai_message)])

    def _combine_messages(self, messages: List[BaseMessage]) -> tuple[str, str]:
        """
        For now this just discards anything that is not an Human message, to be improved
        """
        user_parts = []
        question = ""
        for m in messages:
            if isinstance(m, SystemMessage) and self.system_prompt is None:
                # We could override self.system_prompt from the prompt if we want
                pass
            elif isinstance(m, HumanMessage):
                question = (
                    m.content
                )  # Overwrite each time, so the last human message is the question
            else:
                pass

        user_prompt_str = "\n".join(user_parts)
        return question, user_prompt_str

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        if not self.predict_async or not self.nc_async:
            raise RuntimeError("Async clients not initialized.")

        question, user_prompt_str = self._combine_messages(messages)
        body = ChatModel(
            question=question,
            retrieval=False,
            user_id=self.user_id,
            system=self.system_prompt,
            user_prompt=UserPrompt(prompt=user_prompt_str),
            query_context=self.query_context or {},
        )
        response: GenerativeFullResponse = await self.predict_async.generate(
            text=body,
            model=self.model_name,
            nc=self.nc_async,
        )
        ai_message = AIMessage(content=response.answer)
        return ChatResult(generations=[ChatGeneration(message=ai_message)])

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        if not self.predict_sync or not self.nc_sync:
            raise RuntimeError("Sync clients not initialized.")

        question, user_prompt_str = self._combine_messages(messages)
        body = ChatModel(
            question=question,
            retrieval=False,
            user_id=self.user_id,
            system=self.system_prompt,
            user_prompt=UserPrompt(prompt=user_prompt_str),
            query_context=self.query_context or {},
        )

        # Loop through each partial from the Nuclia synchronous streaming method
        for partial in self.predict_sync.generate_stream(
            text=body,
            model=self.model_name,
            nc=self.nc_sync,
        ):
            # Check if partial is a "generative chunk" containing a TextGenerativeResponse
            if not partial or not partial.chunk:
                continue
            if not isinstance(partial.chunk, TextGenerativeResponse):
                # Skip anything that isn't text
                continue

            text = partial.chunk.text or ""
            msg_chunk = AIMessageChunk(content=text)
            chunk = ChatGenerationChunk(message=msg_chunk)

            if run_manager:
                run_manager.on_llm_new_token(token=text, chunk=chunk)

            yield chunk

    async def _astream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        if not self.predict_async or not self.nc_async:
            raise RuntimeError("Async clients not initialized.")

        question, user_prompt_str = self._combine_messages(messages)
        body = ChatModel(
            question=question,
            retrieval=False,
            user_id=self.user_id,
            system=self.system_prompt,
            user_prompt=UserPrompt(prompt=user_prompt_str),
            query_context=self.query_context or {},
        )

        async for partial in self.predict_async.generate_stream(
            text=body,
            model=self.model_name,
            nc=self.nc_async,
        ):
            if not partial or not partial.chunk:
                continue
            if not isinstance(partial.chunk, TextGenerativeResponse):
                continue

            text = partial.chunk.text or ""
            msg_chunk = AIMessageChunk(content=text)
            chunk = ChatGenerationChunk(message=msg_chunk)

            if run_manager:
                await run_manager.on_llm_new_token(token=text, chunk=chunk)

            yield chunk
