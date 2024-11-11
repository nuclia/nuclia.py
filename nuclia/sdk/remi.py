from nuclia.decorators import kb
from nuclia.lib.kb import NucliaDBClient
from nuclia_models.events.remi import (
    AggregatedRemiScoreMetric,
    RemiQuery,
    RemiQueryResults,
    RemiQueryResultWithContext,
)
from nuclia_models.common.utils import Aggregation
from typing import Union, Optional
from datetime import datetime
from pydantic import TypeAdapter

WAIT_FOR_DOWNLOAD_TIMEOUT = 120


class NucliaRemi:
    @kb
    def query(
        self,
        *args,
        query: Union[
            dict,
            RemiQuery,
        ],
        **kwargs,
    ) -> RemiQueryResults:
        """
        Get a list of rag request that matches a remi scores query.

        :param query: RemiQuery
        """
        _query: RemiQuery
        if isinstance(query, dict):
            _query = RemiQuery.model_validate(query)
        else:
            _query = query

        ndb: NucliaDBClient = kwargs["ndb"]
        response = ndb.remi_query(query=_query)
        return RemiQueryResults.model_validate(response.json())

    @kb
    def get_event(
        self,
        *args,
        event_id: int,
        **kwargs,
    ) -> RemiQueryResultWithContext:
        """
        Get a rag request with full context and REMI scores.
        Intended for obtaining complete context for an item originating from a /remi/query.

        :param event_id: int
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        response = ndb.get_remi_event(event_id=event_id)
        return RemiQueryResultWithContext.model_validate(response.json())

    @kb
    def get_scores(
        self,
        *args,
        starting_at: Union[datetime, str],
        to: Optional[Union[datetime, str]],
        aggregation: Union[Aggregation, str],
        **kwargs,
    ) -> list[AggregatedRemiScoreMetric]:
        ndb: NucliaDBClient = kwargs["ndb"]
        if isinstance(starting_at, str):
            starting_at = datetime.fromisoformat(starting_at)
        if isinstance(to, str):
            to = datetime.fromisoformat(to)
        if isinstance(aggregation, str):
            aggregation = Aggregation[aggregation.upper()]
        response = ndb.get_remi_scores(
            _from=starting_at, to=to, aggregation=aggregation
        )
        ta = TypeAdapter(list[AggregatedRemiScoreMetric])
        return ta.validate_python(response.json())
