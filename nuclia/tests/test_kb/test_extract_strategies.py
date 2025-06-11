from nuclia.sdk.kb import NucliaKB

import pytest


def test_extract_strategies(testing_config):
    nkb = NucliaKB()
    # preventive clean up
    for id in nkb.extract_strategies.list().keys():
        nkb.extract_strategies.delete(id)

    # tests
    nkb.extract_strategies.add(config={"name": "strategy1", "vllm_config": {}})
    all = nkb.extract_strategies.list()
    assert len(all.keys()) == 1
    nkb.extract_strategies.delete(all.keys()[0])
    all = nkb.extract_strategies.list()
    assert len(all.keys()) == 0
