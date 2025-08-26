from time import sleep

from nucliadb_sdk.v2.exceptions import NotFoundError

from nuclia.sdk.kb import NucliaKB


def test_graph(testing_config):
    nkb = NucliaKB()

    # ensure KB is clean
    try:
        nkb.delete_graph(slug="graph1")
    except NotFoundError:
        pass

    nkb.add_graph(
        slug="graph1",
        graph=[
            {
                "source": {"group": "People", "value": "Alice"},
                "destination": {"group": "People", "value": "Bob"},
                "label": "is friend of",
            },
            {
                "source": {"group": "People", "value": "Alice"},
                "destination": {"group": "City", "value": "Toulouse"},
                "label": "lives in",
            },
            {
                "source": {"group": "People", "value": "Bob"},
                "destination": {"group": "Food", "value": "Cheese"},
                "label": "eat",
            },
        ],
    )
    relations = nkb.get_graph(slug="graph1")
    assert len(relations) == 3

    # XXX: sometimes, nucliadb needs some more time to index the graph. We retry
    # some times and fail if that keeps hapenning
    RETRIES = 5
    DELAY = 0.5
    for _ in range(RETRIES):
        paths = nkb.search.graph(
            query={"query": {"prop": "path", "source": {"value": "Alice"}}}
        )
        try:
            assert len(paths.paths) == 2
        except AssertionError:
            # wait for a bit before retrying
            print("Graph was not indexed yet, waiting a bit...")
            sleep(DELAY)
        else:
            break
    assert len(paths.paths) == 2

    nkb.update_graph(
        slug="graph1",
        graph=[
            {
                "source": {"group": "People", "value": "Victor"},
                "destination": {"group": "Food", "value": "Cheese"},
                "label": "eat",
            },
        ],
    )
    relations = nkb.get_graph(slug="graph1")
    assert len(relations) == 4

    for _ in range(RETRIES):
        paths = nkb.search.graph(
            query={"query": {"prop": "path", "source": {"value": "Victor"}}}
        )
        try:
            assert len(paths.paths) == 1
        except AssertionError:
            print("Graph was not indexed yet, waiting a bit...")
            sleep(DELAY)
        else:
            break
    assert len(paths.paths) == 1

    nkb.delete_graph(slug="graph1")
    try:
        sleep(0.5)
        nkb.get_graph(slug="graph1")
        assert False
    except NotFoundError:
        assert True
