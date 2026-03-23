import pytest

from nucliadb_models.metadata import RelationNodeType, RelationType

from nuclia.lib.models import GraphEntity, GraphRelation, get_relation


def test_graph_entity_to_dict():
    entity = GraphEntity(value="Paris", group="CITY")
    result = entity.to_dict()
    assert result["value"] == "Paris"
    assert result["group"] == "CITY"
    assert result["type"] == RelationNodeType.ENTITY


def test_graph_entity_to_dict_no_group():
    entity = GraphEntity(value="Paris")
    result = entity.to_dict()
    assert result["group"] is None
    assert result["type"] == RelationNodeType.ENTITY


def test_graph_relation_to_relation():
    source = GraphEntity(value="France", group="COUNTRY")
    destination = GraphEntity(value="Paris", group="CITY")
    relation = GraphRelation(label="CAPITAL", source=source, destination=destination)

    result = relation.to_relation()
    assert result.relation == RelationType.ENTITY
    assert result.label == "CAPITAL"
    assert result.from_.value == "France"
    assert result.to.value == "Paris"


def test_graph_relation_to_relation_no_label():
    source = GraphEntity(value="France", group="COUNTRY")
    destination = GraphEntity(value="Paris", group="CITY")
    relation = GraphRelation(source=source, destination=destination)

    result = relation.to_relation()
    assert result.label is None


def test_get_relation_with_graph_relation_instance():
    source = GraphEntity(value="A")
    destination = GraphEntity(value="B")
    gr = GraphRelation(source=source, destination=destination)

    result = get_relation(gr)
    assert result is gr


def test_get_relation_with_dict():
    data = {
        "source": {"value": "A", "group": None},
        "destination": {"value": "B", "group": None},
        "label": "RELATES_TO",
    }
    result = get_relation(data)
    assert isinstance(result, GraphRelation)
    assert result.label == "RELATES_TO"
    assert result.source.value == "A"
