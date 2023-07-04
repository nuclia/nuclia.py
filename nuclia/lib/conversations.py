from typing import List

from nucliadb_models import Message
from pydantic import BaseModel


class Conversation(BaseModel):
    __root__: List[Message]
