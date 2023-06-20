from typing import List

from nucliadb_models import PushMessage
from pydantic import BaseModel


class Conversation(BaseModel):
    slug: str
    messages: List[PushMessage]


class Conversations(BaseModel):
    conversations: List[Conversation]
