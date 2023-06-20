from nucliadb_models import PushMessage
from typing import List
from pydantic import BaseModel


class Conversation(BaseModel):
    slug: str
    messages: List[PushMessage]


class Conversations(BaseModel):
    conversations: List[Conversation]
