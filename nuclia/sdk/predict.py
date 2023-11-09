from typing import Optional

from nuclia.data import get_auth
from nuclia.decorators import nua
from nuclia.lib.nua import NuaClient
from nuclia.lib.nua_responses import Sentence
from nuclia.sdk.auth import NucliaAuth


class NucliaPredict:
    @property
    def _auth(self) -> NucliaAuth:
        auth = get_auth()
        return auth

    @nua
    def sentence(self, text: str, model: Optional[str] = None, **kwargs) -> Sentence:
        nc: NuaClient = kwargs["nc"]
        return nc.sentence_predict(text, model)

    @nua
    def generate(self, text: str, model: Optional[str] = None, **kwargs) -> bytes:
        nc: NuaClient = kwargs["nc"]
        return nc.generate_predict(text, model)

    @nua
    def generate_prompt(self, text: str, model: Optional[str] = None, **kwargs) -> str:
        nc: NuaClient = kwargs["nc"]
        user_prompt = (
            nc.generate_predict(text, model).decode().replace("Prompt: ", "")[:-1]
        )
        return (
            user_prompt
            + " \nAnswer the following question based on the provided context: \n[START OF CONTEXT]\n{context}\n[END OF CONTEXT] Question: {question}"  # noqa
        )
