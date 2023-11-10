from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class Sentence(BaseModel):
    data: List[float]
    time: float


class Author(str, Enum):
    NUCLIA = "NUCLIA"
    USER = "USER"


class Message(BaseModel):
    author: Author
    text: str


class UserPrompt(BaseModel):
    prompt: str


class ChatModel(BaseModel):
    question: str
    retrieval: bool = True
    user_id: str
    system: Optional[str] = None
    chat_history: List[Message] = []
    context: List[Message] = []
    query_context: List[str] = []
    truncate: Optional[bool] = False
    user_prompt: Optional[UserPrompt] = None


class Token(BaseModel):
    text: str
    ner: str
    start: int
    end: int


class Tokens(BaseModel):
    tokens: List[Token]
    time: float
