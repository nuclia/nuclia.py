from nuclia.sdk.predict import NucliaPredict


def test_predict(testing_config):
    np = NucliaPredict()
    embed = np.sentence(text="This is my text", model="multilingual-2023-02-21")
    assert embed.time > 0
    assert len(embed.data) == 768
