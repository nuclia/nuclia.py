from typing import Type, Union

import pytest
from nucliadb_models.graph.requests import (
    AnyNode,
    GraphSearchRequest,
    NodeMatchKindName,
)
from nucliadb_models.search import (
    AskRequest,
    CatalogRequest,
    CustomPrompt,
    FindRequest,
    SearchRequest,
)
from pydantic import ValidationError

from nuclia.sdk.search import AsyncNucliaSearch, NucliaSearch
from nuclia.tests.utils import maybe_await


@pytest.mark.parametrize(
    "search_klass",
    [NucliaSearch, AsyncNucliaSearch],
)
@pytest.mark.parametrize(
    "query",
    [
        "Who is hedy Lamarr?",
        {"query": "Who is hedy Lamarr?"},
        SearchRequest(query="Who is hedy Lamarr?"),
    ],
)
async def test_search(
    testing_config,
    search_klass: Union[Type[NucliaSearch], Type[AsyncNucliaSearch]],
    query,
):
    search = search_klass()
    maybe_results = search.search(query=query)
    results = await maybe_await(maybe_results)

    assert len(results.resources.keys()) == 2
    titles = [r.title for r in results.resources.values()]
    assert "Lamarr Lesson plan.pdf" in titles


@pytest.mark.parametrize(
    "search_klass",
    [NucliaSearch, AsyncNucliaSearch],
)
async def test_search_with_filters(
    testing_config,
    search_klass: Union[Type[NucliaSearch], Type[AsyncNucliaSearch]],
):
    search = search_klass()
    maybe_results = search.search(
        query="Who is hedy Lamarr?", filters=["/icon/application/pdf"]
    )
    results = await maybe_await(maybe_results)
    assert len(results.resources.keys()) == 1


@pytest.mark.parametrize(
    "search_klass",
    [NucliaSearch, AsyncNucliaSearch],
)
@pytest.mark.parametrize(
    "query",
    [
        "",
        {"query": ""},
        CatalogRequest(query=""),
    ],
)
async def test_catalog(
    testing_config,
    search_klass: Union[Type[NucliaSearch], Type[AsyncNucliaSearch]],
    query,
):
    search = search_klass()
    maybe_results = search.catalog(query=query)
    results = await maybe_await(maybe_results)
    assert len(results.resources.keys()) >= 2


@pytest.mark.parametrize(
    "search_klass",
    [NucliaSearch, AsyncNucliaSearch],
)
@pytest.mark.parametrize(
    "query",
    [
        "Who is hedy Lamarr?",
        {"query": "Who is hedy Lamarr?"},
        FindRequest(query="Who is Hedy Lamarr?"),
    ],
)
async def test_find(
    testing_config,
    search_klass: Union[Type[NucliaSearch], Type[AsyncNucliaSearch]],
    query,
):
    search = search_klass()
    maybe_results = search.find(query=query)
    results = await maybe_await(maybe_results)
    assert len(results.resources.keys()) == 2
    titles = [r.title for r in results.resources.values()]
    assert "Lamarr Lesson plan.pdf" in titles


@pytest.mark.parametrize(
    "search_klass",
    [NucliaSearch, AsyncNucliaSearch],
)
@pytest.mark.parametrize(
    "query",
    [
        "Who is hedy Lamarr?",
        {"query": "Who is hedy Lamarr?"},
        AskRequest(query="Who is Hedy Lamarr?"),
    ],
)
async def test_ask(
    testing_config,
    search_klass: Union[Type[NucliaSearch], Type[AsyncNucliaSearch]],
    query,
):
    search = search_klass()

    maybe_results = search.ask(query=query)
    results = await maybe_await(maybe_results)
    answer = results.answer.decode()
    assert "Lamarr" in answer


async def test_ask_with_custom_prompt(testing_config):
    search = NucliaSearch()
    async_search = AsyncNucliaSearch()

    ask = AskRequest(
        query="Are Pepito Palotes and Hedy Lamarr friends?",
        prompt=CustomPrompt(
            system="Answer the question. If you don't know the anwser, write 'I don't know' and a list of bullet points with the reasons why you don't know the answer.",
            user="Based on this context {context}, answer the question {question}",
        ),
        generative_model="chatgpt-azure-4o",
    )
    results = search.ask(query=ask)
    async_results = await async_search.ask(query=ask)
    assert results.find_result == async_results.find_result

    answer = results.answer.decode()
    assert "I don't know" in answer, print(answer)

    answer = async_results.answer.decode()
    assert "I don't know" in answer, print(answer)


def test_ask_with_markdown_answer(testing_config):
    search = NucliaSearch()
    ask = AskRequest(
        query="Who is Hedy Lamarr and what did she do?",
        prompt=CustomPrompt(
            system="Answer the question and use lists as much as possible.",
            user="Based on this context {context}, answer the question {question}",
        ),
        generative_model="gemini-2.5-pro",
        prefer_markdown=True,
    )
    results = search.ask(query=ask)
    answer = results.answer.decode()
    markdown_keywords = ["**", "#", "1.", "*"]
    assert any([keyword in answer.lower() for keyword in markdown_keywords]), answer


SCHEMA = {
    "name": "ClassificationReverse",
    "description": "Correctly extracted with all the required parameters with correct types",
    "parameters": {
        "$defs": {
            "Options": {
                "enum": ["SPORTS", "TECHNOLOGY"],
                "title": "Options",
                "type": "string",
            }
        },
        "properties": {
            "title": {"default": "label", "title": "Title", "type": "string"},
            "description": {
                "default": "Define labels to classify the subject of the document",
                "title": "Description",
                "type": "string",
            },
            "document_type": {
                "description": "Type of document, SPORT example: elections, Illa, POLITICAL example: football, TECHNOLOGY example: computer",
                "items": {"$ref": "#/$defs/Options"},
                "title": "Document Type",
                "type": "array",
            },
        },
        "required": ["document_type"],
        "type": "object",
    },
}


def test_ask_json(testing_config):
    search = NucliaSearch()
    results = search.ask_json(
        query="Who is hedy Lamarr?", filters=["/icon/application/pdf"], schema=SCHEMA
    )

    assert "TECHNOLOGY" in results.object["document_type"]


@pytest.mark.asyncio
async def test_ask_json_async(testing_config):
    search = AsyncNucliaSearch()
    results = await search.ask_json(
        query="Who is hedy Lamarr?",
        filters=["/icon/application/pdf"],
        schema=SCHEMA,
        show_consumption=True,
    )

    assert "TECHNOLOGY" in results.object["document_type"]
    assert results.consumption is not None


@pytest.mark.parametrize(
    "search_klass",
    [NucliaSearch, AsyncNucliaSearch],
)
@pytest.mark.parametrize(
    "query",
    [
        {
            "query": {
                "prop": "node",
                "value": "Hedy",
                "match": "fuzzy",
            }
        },
        GraphSearchRequest(query=AnyNode(value="Hedy", match=NodeMatchKindName.FUZZY)),
    ],
)
async def test_graph(
    testing_config,
    search_klass: Union[Type[NucliaSearch], Type[AsyncNucliaSearch]],
    query,
):
    search = search_klass()
    maybe_results = search.graph(query=query)
    results = await maybe_await(maybe_results)
    assert len(results.paths) >= 22


async def test_search_query_type_check(
    testing_config,
) -> None:
    query = object()  # invalid on every call

    search = NucliaSearch()
    with pytest.raises(TypeError):
        search.search(query=query)
    with pytest.raises(TypeError):
        search.find(query=query)
    with pytest.raises(TypeError):
        search.catalog(query=query)
    with pytest.raises(TypeError):
        search.ask(query=query)
    with pytest.raises(TypeError):
        search.ask_json(schema={}, query=query)
    with pytest.raises(TypeError):
        search.graph(query=query)

    async_search = AsyncNucliaSearch()
    with pytest.raises(TypeError):
        await async_search.search(query=query)
    with pytest.raises(TypeError):
        await async_search.find(query=query)
    with pytest.raises(TypeError):
        await async_search.catalog(query=query)
    with pytest.raises(TypeError):
        await async_search.ask(query=query)
    with pytest.raises(TypeError):
        async for _ in async_search.ask_stream(query=query):
            pass
    with pytest.raises(TypeError):
        await async_search.ask_json(schema={}, query=query)
    with pytest.raises(TypeError):
        await async_search.graph(query=query)


async def test_search_query_validation_errors(
    testing_config,
) -> None:
    query = {"query": object()}  # invalid on every call

    search = NucliaSearch()
    with pytest.raises(ValidationError):
        search.search(query=query)
    with pytest.raises(ValidationError):
        search.find(query=query)
    with pytest.raises(ValidationError):
        search.catalog(query=query)
    with pytest.raises(ValidationError):
        search.ask(query=query)
    with pytest.raises(ValidationError):
        search.ask_json(schema={}, query=query)
    with pytest.raises(ValidationError):
        search.graph(query=query)

    async_search = AsyncNucliaSearch()
    with pytest.raises(ValidationError):
        await async_search.search(query=query)
    with pytest.raises(ValidationError):
        await async_search.find(query=query)
    with pytest.raises(ValidationError):
        await async_search.catalog(query=query)
    with pytest.raises(ValidationError):
        await async_search.ask(query=query)
    with pytest.raises(ValidationError):
        async for _ in async_search.ask_stream(query=query):
            pass
    with pytest.raises(ValidationError):
        await async_search.ask_json(schema={}, query=query)
    with pytest.raises(ValidationError):
        await async_search.graph(query=query)
