from typing import List

from pydantic import BaseModel


class Sentence(BaseModel):
    data: List[float]
    time: float
