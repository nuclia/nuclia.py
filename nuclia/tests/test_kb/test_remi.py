from nuclia.sdk.kb import NucliaKB
from nuclia.tests.fixtures import IS_PROD
from nuclia_models.events.remi import RemiQuery, ContextRelevanceQuery


def test_remi_query(testing_config):
    if not IS_PROD:
        assert True
        return
    nkb = NucliaKB()
    remi_query = nkb.remi.query(
        query=RemiQuery(
            month="2024-11",
            context_relevance=ContextRelevanceQuery(
                value=0, operation="gt", aggregation="average"
            ),
        )
    )
    assert len(remi_query.data) == 10
    remi_event = nkb.remi.get_remi_event(event_id=remi_query.data[0].id)
    assert remi_event is not None
