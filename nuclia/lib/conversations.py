from typing import List

from nucliadb_models import Message
from pydantic import BaseModel


class ConversationWrapper(BaseModel):
    slug: str
    messages: List[Message]


class Conversations(BaseModel):
    conversations: List[ConversationWrapper]
