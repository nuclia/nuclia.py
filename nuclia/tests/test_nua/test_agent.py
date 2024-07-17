from nuclia.sdk.agent import NucliaAgent


def test_agent(testing_config):
    np = NucliaAgent()
    agent_prompt = np.generate_prompt(
        text="You will answer questions about this topic in the way of a Spanish historian",
        agent_definition="Toledo",
        model="chatgpt4o",
    )
    assert "Toledo" in agent_prompt
