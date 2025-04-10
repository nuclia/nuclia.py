from nuclia.sdk.kb import NucliaKB
from nucliadb_sdk.v2.exceptions import NotFoundError

from time import sleep


def test_graph(testing_config):
    nkb = NucliaKB()
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
    nkb.delete_graph(slug="graph1")
    try:
        sleep(0.5)
        nkb.get_graph(slug="graph1")
        assert False
    except NotFoundError:
        assert True
