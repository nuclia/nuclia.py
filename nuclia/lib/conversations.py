from typing import List, Optional

from pydantic import BaseModel


class Body(BaseModel):
    text: str
    format: str = "PLAIN"


class Message(BaseModel):
    who: Optional[str] = None
    to: Optional[List[str]] = None
    uuid: Optional[str] = None
    timestamp: Optional[str] = None
    message: Body


class Conversation(BaseModel):
    slug: Optional[str] = None
    messages: Optional[List[Message]] = []


class Conversations(BaseModel):
    conversations: Optional[List[Conversation]] = []
