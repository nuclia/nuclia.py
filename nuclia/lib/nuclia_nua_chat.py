import json

from datetime import datetime, timezone
from base64 import b64decode

try:
    from litellm import (
        CustomLLM,
        ModelResponse,
        Choices,
        Message,
    )

except ImportError:
    raise ImportError(
        "The 'litellm' library is required to use this functionality. "
        "Install it with: pip install nuclia[ai]"
    )

# Nuclia (sync & async)
from nuclia.lib.nua import NuaClient, AsyncNuaClient
from nuclia.sdk.predict import NucliaPredict, AsyncNucliaPredict
from nuclia.lib.nua_responses import ChatModel, UserPrompt
from nuclia_models.predict.generative_responses import (
    GenerativeFullResponse,
)


class NucliaNuaChat(CustomLLM):
    """
    A LiteLLM custom Model that uses nua client under the hood
    """

    def __init__(self, token: str):
        self.token = token
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

    def _process_messages(self, messages: list[dict[str, str]]) -> tuple[str, str]:
        system_messages = []
        user_messages = []

        for msg in messages:
            role = msg["role"]
            content = msg["content"].strip()

            if role == "system":
                system_messages.append(content)
            elif role == "user":
                user_messages.append(content)

        formatted_system = (
            "\n--- System Messages ---\n" + "\n".join(system_messages)
            if system_messages
            else ""
        )
        formatted_user = (
            "\n--- User Messages ---\n" + "\n".join(user_messages)
            if user_messages
            else ""
        )

        return formatted_system, formatted_user

    def completion(
        self, *args, model: str, messages: list[dict[str, str]], **kwargs
    ) -> ModelResponse:
        if not self.predict_sync or not self.nc_sync:
            raise RuntimeError("Sync clients not initialized.")

        system_prompt, user_prompt = self._process_messages(messages)
        body = ChatModel(
            question="",
            retrieval=False,
            user_id="nua-chat",
            system=system_prompt,
            user_prompt=UserPrompt(prompt=user_prompt),
            query_context={},
        )
        response: GenerativeFullResponse = self.predict_sync.generate(
            text=body,
            model=model,
            nc=self.nc_sync,
        )

        return ModelResponse(
            choices=[Choices(message=Message(content=response.answer))]
        )
