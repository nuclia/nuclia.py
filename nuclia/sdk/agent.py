from typing import List, Optional

from nucliadb_models.search import AskRequest


class Agent:
    prompt: str
    filters: List[str]

    def __init__(self, prompt: str, filters: List[str]):
        self.prompt = prompt
        self.filters = filters
        from nuclia.sdk import NucliaSearch

        self.search = NucliaSearch()

    def ask(self, text: str) -> str:
        ask_req = AskRequest(query=text, prompt=self.prompt, filters=self.filters)
        answer = self.search.ask(query=ask_req)
        return answer.answer.decode()


class NucliaAgent:
    def __init__(self):
        from nuclia.sdk import NucliaPredict

        self.predict = NucliaPredict()

    def generate_prompt(
        self, text: str, agent_definition: str, model: Optional[str] = None
    ) -> str:
        user_prompt = self.predict.generate(
            f"""Define a prompt for an agent that will answer questions about this topic: {agent_definition}
                taking into account the following guidelines:
                {text}
                IMPORTANT:
                It does not need to be a perfect prompt, even if you do not have enough information, return a prompt.
                PROMPT:""",
            model,
        ).answer.replace("Prompt: ", "")[:-1]

        agent_prompt = (
            "Answer the following question based on the provided context: \n[START OF CONTEXT]\n{context}\n[END OF CONTEXT] Question: "  # noqa
            + user_prompt
            + " {question}"
        )  # noqa

        return agent_prompt

    def generate_agent(
        self, topic: str, agent_definition: str = "agent", model: Optional[str] = None
    ) -> Agent:
        agent_prompt = self.generate_prompt(topic, agent_definition, model)

        tokens = self.predict.tokens(topic)
        filters = []
        for token in tokens.tokens:
            filters.append(f"/e/{token.ner}/{token.text}")

        return Agent(prompt=agent_prompt, filters=filters)
