from typing import List, Optional

from nucliadb_models.search import ChatRequest

from nuclia.sdk import NucliaPredict, NucliaSearch


class Agent:
    prompt: str
    filters: List[str]

    def __init__(self, prompt: str, filters: List[str]):
        self.prompt = prompt
        self.filters = filters
        self.search = NucliaSearch()

    def ask(self, text: str) -> str:
        chat_req = ChatRequest(query=text, prompt=self.prompt, filters=self.filters)
        import pdb

        pdb.set_trace()
        answer = self.search.chat(query=chat_req)
        return answer.answer.decode()


class NucliaAgent:
    def __init__(self):
        self.predict = NucliaPredict()

    def generate_agent(self, text: str, model: Optional[str] = None) -> Agent:
        user_prompt = (
            self.predict.generate(text, model).decode().replace("Prompt: ", "")[:-1]
        )

        agent_prompt = (
            user_prompt
            + " \nAnswer the following question based on the provided context: \n[START OF CONTEXT]\n{context}\n[END OF CONTEXT] Question: {question}"  # noqa
        )

        tokens = self.predict.tokens(text)
        filters = []
        for token in tokens.tokens:
            filters.append(f"/e/{token.ner}/{token.text}")

        return Agent(prompt=agent_prompt, filters=filters)
