from nuclia.sdk.predict import NucliaPredict


def test_predict(testing_config):
    np = NucliaPredict()
    embed = np.sentence(text="This is my text", model="multilingual-2023-02-21")
    assert embed.time > 0
    assert len(embed.data) == 768


def test_predict_query(testing_config):
    np = NucliaPredict()
    query = np.query(
        text="Ramon, this is my text",
        semantic_model="multilingual-2023-02-21",
        token_model="multilingual",
        generative_model="chatgpt-azure-3",
    )
    assert query.language == "en"
    assert query.visual_llm is False
    assert query.max_context == 4000
    assert query.entities and query.entities.tokens[0].text == "Ramon"
    assert query.sentence and len(query.sentence.data) == 768


def test_rag(testing_config):
    np = NucliaPredict()
    generated = np.rag(
        question="Which is the CEO of Nuclia?",
        context=[
            "Nuclia CTO is Ramon Navarro",
            "Eudald Camprubí is CEO at the same company as Ramon Navarro",
        ],
        model="chatgpt-azure-3",
    )
    assert "Eudald" in generated.answer
