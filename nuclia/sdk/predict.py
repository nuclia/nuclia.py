from typing import Dict, List, Optional

from nuclia.data import get_auth
from nuclia.decorators import nua
from nuclia.lib.nua import NuaClient
from nuclia.lib.nua_responses import Sentence, SummarizedModel, Tokens
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
    ) -> bytes:
        nc: NuaClient = kwargs["nc"]
        return nc.generate_retrieval(question, context, model)
