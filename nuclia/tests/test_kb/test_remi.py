from nuclia.sdk.kb import NucliaKB
from nuclia.tests.fixtures import IS_PROD
from nuclia_models.events.remi import RemiQuery, ContextRelevanceQuery
from datetime import datetime
from nuclia_models.common.utils import Aggregation


def test_remi_query_and_get_event(testing_config):
    if not IS_PROD:
        assert True
        return
    nkb = NucliaKB()
    remi_query = nkb.remi.query(
        query=RemiQuery(
            month="2024-10",
            context_relevance=ContextRelevanceQuery(
                value=0, operation="eq", aggregation="max"
            ),
        )
    )
    assert len(remi_query.data) == 10
    remi_event = nkb.remi.get_event(event_id=remi_query.data[0].id)
    assert remi_event.id == remi_query.data[0].id


def test_remi_scores(testing_config):
    if not IS_PROD:
        assert True
        return
    nkb = NucliaKB()
    remi_scores_data = nkb.remi.get_scores(
        starting_at=datetime(year=2024, month=10, day=1),
        to=datetime(year=2024, month=11, day=1),
        aggregation=Aggregation.DAY,
    )
    assert len(remi_scores_data) == 32
