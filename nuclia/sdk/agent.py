from typing import List, Optional

from nucliadb_models.search import ChatRequest


class Agent:
    prompt: str
    filters: List[str]

    def __init__(self, prompt: str, filters: List[str]):
        self.prompt = prompt
        self.filters = filters
        from nuclia.sdk import NucliaSearch

        self.search = NucliaSearch()

    def ask(self, text: str) -> str:
        chat_req = ChatRequest(query=text, prompt=self.prompt, filters=self.filters)
        answer = self.search.chat(query=chat_req)
        return answer.answer.decode()


class NucliaAgent:
    def __init__(self):
        from nuclia.sdk import NucliaPredict

        self.predict = NucliaPredict()

    def generate_agent(self, text: str, model: Optional[str] = None) -> Agent:
        user_prompt = (
            self.predict.generate(
                f"Define a prompt for an agent that will answer questions about {text}",
                model,
            )
            .decode()
            .replace("Prompt: ", "")[:-1]
        )

        agent_prompt = (
            "Answer the following question based on the provided context: \n[START OF CONTEXT]\n{context}\n[END OF CONTEXT] Question: "  # noqa
            + user_prompt
            + " {question}"
        )  # noqa
        tokens = self.predict.tokens(text)
        filters = []
        for token in tokens.tokens:
            filters.append(f"/e/{token.ner}/{token.text}")

        return Agent(prompt=agent_prompt, filters=filters)
