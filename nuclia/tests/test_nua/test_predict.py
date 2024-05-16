from nuclia.sdk.predict import AsyncNucliaPredict, NucliaPredict


def test_predict(testing_config):
    np = NucliaPredict()
    embed = np.sentence(text="This is my text", model="multilingual-2024-05-06")
    assert embed.time > 0
    assert len(embed.data) == 1024


def test_predict_query(testing_config):
    np = NucliaPredict()
    query = np.query(
        text="Ramon, this is my text",
        semantic_model="multilingual-2024-05-06",
        token_model="multilingual",
        generative_model="chatgpt-azure-3",
    )
    assert query.language == "en"
    assert query.visual_llm is False
    assert query.max_context == 16385
    assert query.entities and query.entities.tokens[0].text == "Ramon"
    assert query.sentence and len(query.sentence.data) == 1024


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


def test_generative(testing_config):
    np = NucliaPredict()
    generated = np.generate(text="How much is 2 + 2?", model="chatgpt-azure-3")
    assert "4" in generated.answer


async def test_async_generative(testing_config):
    np = AsyncNucliaPredict()
    generated = await np.generate(text="How much is 2 + 2?", model="chatgpt-azure-3")
    assert "4" in generated.answer


def test_stream_generative(testing_config):
    np = NucliaPredict()
    generated = np.generate_stream(text="How much is 2 + 2?", model="chatgpt-azure-3")
    assert "4" in generated.text


async def test_async_stream_generative(testing_config):
    np = AsyncNucliaPredict()
    generated = await np.generate_stream(
        text="How much is 2 + 2?", model="chatgpt-azure-3"
    )
    assert "4" in generated.text
