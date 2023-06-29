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
    def sentence(
        self, nc: NuaClient, text: str, model: Optional[str] = None
    ) -> Sentence:
        return nc.sentence_predict(text, model)
