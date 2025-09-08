from nuclia.sdk.kb import NucliaKB


def test_split_strategies(testing_config):
    nkb = NucliaKB()
    # preventive clean up
    for id in nkb.split_strategies.list().keys():
        nkb.split_strategies.delete(id=id)

    # tests
    nkb.split_strategies.add(config={"name": "strategy1", "max_paragraph": 400})
    all = nkb.split_strategies.list()
    assert len(all.keys()) == 1
    nkb.split_strategies.delete(id=list(all.keys())[0])
    all = nkb.split_strategies.list()
    assert len(all.keys()) == 0
