from nuclia.sdk.predict import NucliaPredict


def test_predict(testing_config):
    np = NucliaPredict()
    embed = np.sentence(text="This is my text", model="multilingual-2023-02-21")
    assert embed.time > 0
    assert len(embed.data) == 768


def test_rag(testing_config):
    np = NucliaPredict()
    generated = np.rag(
        question="Which is the CEO of Nuclia?",
        context=[
            "Nuclia CTO is Ramon Navarro",
            "Eudald Camprubí is CEO at the same company as Ramon Navarro",
        ],
        model="chatgpt",
    )
    assert b"Eudald" in generated
