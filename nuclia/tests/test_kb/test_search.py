from nuclia.sdk.search import NucliaSearch
from nuclia.tests.fixtures import IS_PROD


def test_find(testing_config):
    if IS_PROD:
        assert True
        return
    search = NucliaSearch()
    results = search.find(query="Who is hedy Lamarr?")
    assert len(results.resources.keys()) == 2
    titles = [r.title for r in results.resources.values()]
    assert "Lamarr Lesson plan.pdf" in titles


def test_find_object(testing_config):
    if IS_PROD:
        assert True
        return
    search = NucliaSearch()
    results = search.find(query={"query": "Who is hedy Lamarr?"})
    assert len(results.resources.keys()) == 2
    titles = [r.title for r in results.resources.values()]
    assert "Lamarr Lesson plan.pdf" in titles


def test_search(testing_config):
    if IS_PROD:
        assert True
        return
    search = NucliaSearch()
    results = search.search(query="Who is hedy Lamarr?")
    assert len(results.resources.keys()) == 2
    titles = [r.title for r in results.resources.values()]
    assert "Lamarr Lesson plan.pdf" in titles


def test_search_object(testing_config):
    if IS_PROD:
        assert True
        return
    search = NucliaSearch()
    results = search.search(query={"query": "Who is hedy Lamarr?"})
    assert len(results.resources.keys()) == 2
    titles = [r.title for r in results.resources.values()]
    assert "Lamarr Lesson plan.pdf" in titles


def test_filters(testing_config):
    if IS_PROD:
        assert True
        return
    search = NucliaSearch()
    results = search.find(
        query="Who is hedy Lamarr?", filters=["/icon/application/pdf"]
    )
    assert len(results.resources.keys()) == 1
