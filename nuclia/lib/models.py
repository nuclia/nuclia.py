from nuclia_models.events.activity_logs import (
    ActivityLogsQueryResponse,
    BaseConfigModel,
    DownloadRequest,
)
from nucliadb_models.metadata import (
    Relation,
    RelationNodeType,
    RelationType,
)
from pydantic import BaseModel
from typing import Optional, Union


class ActivityLogsOutput(BaseConfigModel):
    data: list[ActivityLogsQueryResponse]  # type: ignore
    has_more: bool


DownloadRequestOutput = type(
    "DownloadRequestOutput",
    (BaseModel,),
    {
        "__annotations__": {
            name: field.annotation
            for name, field in DownloadRequest.model_fields.items()
            if name not in {"id", "query", "user_id"}
        }
    },
)


class GraphEntity(BaseModel):
    value: str
    group: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "group": self.group,
            "type": RelationNodeType.ENTITY,
        }


class GraphRelation(BaseModel):
    label: Optional[str] = None
    source: GraphEntity
    destination: GraphEntity

    def to_relation(self) -> Relation:
        return Relation.parse_obj(
            {
                "from": self.source.to_dict(),
                "to": self.destination.to_dict(),
                "label": self.label,
                "relation": RelationType.ENTITY,
            }
        )


def get_relation(relation: Union[GraphRelation, dict]) -> GraphRelation:
    if isinstance(relation, dict):
        return GraphRelation.parse_obj(relation)
    else:
        return relation
