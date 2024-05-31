from typing import List

from nucliadb_models import Message
from pydantic import RootModel


class Conversation(RootModel[List[Message]]):
    pass
