import pytest
from nuclia_models.predict.generative_responses import (
    ConsumptionGenerative,
    FootnoteCitationsGenerativeResponse,
    TextGenerativeResponse,
)
from nuclia_models.predict.remi import RemiRequest

from nuclia.lib.nua_responses import (
    ChatModel,
    CitationsType,
    Reasoning,
    RerankModel,
    UserPrompt,
)
from nuclia.sdk.predict import AsyncNucliaPredict, NucliaPredict
from nuclia.tests.utils import maybe_await


def test_predict(testing_config):
    np = NucliaPredict()
    embed = np.sentence(
        text="This is my text", model="multilingual-2024-05-06", show_consumption=True
    )
    assert embed.time > 0
    assert len(embed.data) == 1024
    assert embed.consumption is not None


def test_predict_query(testing_config):
    np = NucliaPredict()
    query = np.query(
        text="Ramon, this is my text",
        semantic_model="multilingual-2024-05-06",
        token_model="multilingual",
        generative_model="chatgpt-azure-4o-mini",
        show_consumption=True,
    )
    assert query.language == "en"
    assert query.visual_llm is True
    assert query.entities and query.entities.tokens[0].text == "Ramon"
    assert query.sentence and len(query.sentence.data) == 1024
    assert query.entities.consumption is not None
    assert query.sentence.consumption is not None


def test_rag(testing_config):
    np = NucliaPredict()
    generated = np.rag(
        question="Which is the CEO of Nuclia?",
        context=[
            "Nuclia CTO is Ramon Navarro",
            "Eudald Camprubí is CEO at the same company as Ramon Navarro",
        ],
        model="chatgpt-azure-4o-mini",
        show_consumption=True,
    )
    assert "Eudald" in generated.answer
    assert generated.consumption is not None


def test_generative(testing_config):
    np = NucliaPredict()
    generated = np.generate(text="How much is 2 + 2?", model="chatgpt-azure-4o-mini")
    assert "4" in generated.answer
    assert generated.consumption is None


@pytest.mark.asyncio
async def test_generative_with_consumption(testing_config):
    np = NucliaPredict()
    generated = np.generate(
        text="How much is 2 + 2?", model="chatgpt-azure-4o-mini", show_consumption=True
    )
    assert "4" in generated.answer
    assert generated.consumption is not None

    anp = AsyncNucliaPredict()
    async_generated = await anp.generate(
        text="How much is 2 + 2?", model="chatgpt-azure-4o-mini", show_consumption=True
    )
    assert "4" in async_generated.answer
    assert async_generated.consumption is not None


@pytest.mark.asyncio
async def test_async_generative(testing_config):
    np = AsyncNucliaPredict()
    generated = await np.generate(
        text="How much is 2 + 2?", model="chatgpt-azure-4o-mini"
    )
    assert "4" in generated.answer


def test_stream_generative(testing_config):
    np = NucliaPredict()
    found = False
    for stream in np.generate_stream(
        text="How much is 2 + 2?", model="chatgpt-azure-4o-mini"
    ):
        if isinstance(stream.chunk, TextGenerativeResponse) and stream.chunk.text:
            if "4" in stream.chunk.text:
                found = True
    assert found


@pytest.mark.asyncio
async def test_async_stream_generative(testing_config):
    np = AsyncNucliaPredict()
    consumption_found = False
    found = False
    async for stream in np.generate_stream(
        text="How much is 2 + 2?", model="chatgpt-azure-4o-mini", show_consumption=True
    ):
        if isinstance(stream.chunk, TextGenerativeResponse) and stream.chunk.text:
            if "4" in stream.chunk.text:
                found = True
        elif isinstance(stream.chunk, ConsumptionGenerative):
            consumption_found = True
    assert found
    assert consumption_found


SCHEMA = {
    "name": "ClassificationReverse",
    "description": "Correctly extracted with all the required parameters with correct types",
    "parameters": {
        "$defs": {
            "Options": {
                "enum": ["SPORTS", "POLITICAL"],
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
                "description": "Type of document, SPORT example: elections, Illa, POLITICAL example: football",
                "items": {"$ref": "#/$defs/Options"},
                "title": "Document Type",
                "type": "array",
            },
        },
        "required": ["document_type"],
        "type": "object",
    },
}

TEXT = """"Many football players have existed. Messi is by far the greatest. Messi was born in Rosario, 24th of June 1987"""


@pytest.mark.asyncio
async def test_nua_parse(testing_config):
    np = AsyncNucliaPredict()
    results = await np.generate(
        text=ChatModel(
            question="",
            retrieval=False,
            user_id="Nuclia PY CLI",
            user_prompt=UserPrompt(prompt=TEXT),
            json_schema=SCHEMA,
        )
    )
    assert "SPORTS" in results.object["document_type"]


def test_nua_remi(testing_config):
    np = NucliaPredict()
    results = np.remi(
        RemiRequest(
            user_id="Nuclia PY CLI",
            question="What is the capital of France?",
            answer="Paris is the capital of france!",
            contexts=[
                "Paris is the capital of France.",
                "Berlin is the capital of Germany.",
            ],
        )
    )
    assert results.answer_relevance.score >= 4

    assert results.context_relevance[0] >= 4
    assert results.groundedness[0] >= 4

    assert results.context_relevance[1] < 2
    assert results.groundedness[1] < 2

    assert results.consumption is None


@pytest.mark.asyncio
async def test_nua_async_remi(testing_config):
    np = AsyncNucliaPredict()
    results = await np.remi(
        RemiRequest(
            user_id="Nuclia PY CLI",
            question="What is the capital of France?",
            answer="Paris is the capital of france!",
            contexts=[
                "Paris is the capital of France.",
                "Berlin is the capital of Germany.",
            ],
        ),
        show_consumption=True,
    )
    assert results.answer_relevance.score >= 4

    assert results.context_relevance[0] >= 4
    assert results.groundedness[0] >= 4

    assert results.context_relevance[1] < 2
    assert results.groundedness[1] < 2

    assert results.consumption is not None


def test_nua_rerank(testing_config):
    np = NucliaPredict()
    results = np.rerank(
        RerankModel(
            user_id="Nuclia PY CLI",
            question="What is the capital of France?",
            context={
                "1": "Paris is the capital of France.",
                "2": "Berlin is the capital of Germany.",
            },
        )
    )
    assert results.context_scores["1"] > results.context_scores["2"]
    assert results.consumption is None


@pytest.mark.asyncio
async def test_nua_rerank_with_consumption(testing_config):
    np = NucliaPredict()
    results = np.rerank(
        RerankModel(
            user_id="Nuclia PY CLI",
            question="What is the capital of France?",
            context={
                "1": "Paris is the capital of France.",
                "2": "Berlin is the capital of Germany.",
            },
        ),
        show_consumption=True,
    )
    assert results.context_scores["1"] > results.context_scores["2"]
    assert results.consumption is not None

    anp = AsyncNucliaPredict()
    async_results = await anp.rerank(
        RerankModel(
            user_id="Nuclia PY CLI",
            question="What is the capital of France?",
            context={
                "1": "Paris is the capital of France.",
                "2": "Berlin is the capital of Germany.",
            },
        ),
        show_consumption=True,
    )
    assert async_results.context_scores["1"] > async_results.context_scores["2"]
    assert async_results.consumption is not None


@pytest.mark.asyncio
async def test_generative_with_reasoning(testing_config):
    np = NucliaPredict()
    generated = np.generate(
        ChatModel(
            question=(
                "Create the simplest possible regex pattern that from the following list it matches all aws zones"
                " but not aws-il and also matches progress zone?\n\n - aws-il-central-1-1\n\n - aws-us-east-2-1\n\n"
                " - aws-europe-central-1-1\n\n - gke-prod-1\n\n - progress-proc-us-east-2-1"
            ),
            retrieval=False,
            user_id="Nuclia PY CLI",
            generative_model="chatgpt-azure-o3-mini",
            max_tokens=4000,
            reasoning=Reasoning(display=True, effort="high", budget_tokens=1024),
            user_prompt=UserPrompt(prompt="{question}"),
        ),
    )
    assert "progress" in generated.answer, generated.answer
    # Reasoning is not very consistent since the model decides when to use it
    # assert "progress" in generated.reasoning, generated.reasoning

    anp = AsyncNucliaPredict()
    async_generated = await anp.generate(
        text=ChatModel(
            question=(
                "Create the simplest possible regex pattern that from the following list it matches all aws zones"
                " but not aws-il and also matches progress zone?\n\n - aws-il-central-1-1\n\n - aws-us-east-2-1\n\n"
                " - aws-europe-central-1-1\n\n - gke-prod-1\n\n - progress-proc-us-east-2-1"
            ),
            retrieval=False,
            user_id="Nuclia PY CLI",
            generative_model="chatgpt-azure-o3-mini",
            max_tokens=4000,
            reasoning=Reasoning(display=True, effort="high", budget_tokens=1024),
            user_prompt=UserPrompt(prompt="{question}"),
        ),
    )
    assert "progress" in async_generated.answer, async_generated.answer
    # Reasoning is not very consistent since the model decides when to use it
    # assert "progress" in async_generated.reasoning, async_generated.reasoning


@pytest.fixture(scope="function")
def chat_example_md_citations() -> ChatModel:
    return ChatModel(
        question="What is Progress Agentic RAG, and what plans they provide?",
        user_id="asd",
        citations=CitationsType.LLM_FOOTNOTES,
        query_context={
            "2c6db015b370ec47abaf43aa704a16fd/f/2c6db015b370ec47abaf43aa704a16fd": "Progress Agentic RAG provides AI-powered search and knowledge management solutions.",
            "d854cbe0da054e0da186d1a722015057/l/46abb334c7afaf128e7c1e0ce877b9bb": "**Progress Agentic RAG Plans Pricing**\n* Fly: $700/month\n* Growth: $1,750/month\n* Enterprise: Contact sales",
        },
        max_tokens=1500,
    )


def test_citation_footnote_to_context(testing_config, chat_example_md_citations):
    np = NucliaPredict()
    footnote_found = False
    for stream in np.generate_stream(
        chat_example_md_citations, model="chatgpt-azure-4o-mini"
    ):
        if isinstance(stream.chunk, FootnoteCitationsGenerativeResponse):
            # Verify that footnote_to_context mapping exists
            assert stream.chunk.footnote_to_context is not None
            assert len(stream.chunk.footnote_to_context) > 0

            # Verify that the footnote IDs map to context keys from query_context
            for footnote_id, context_key in stream.chunk.footnote_to_context.items():
                assert context_key in chat_example_md_citations.query_context
                footnote_found = True

    assert footnote_found, "FootnoteCitationsGenerativeResponse chunk should be present"


@pytest.mark.asyncio
async def test_async_citation_footnote_to_context(
    testing_config, chat_example_md_citations
):
    np = AsyncNucliaPredict()
    footnote_found = False
    async for stream in np.generate_stream(
        chat_example_md_citations, model="chatgpt-azure-4o-mini"
    ):
        if isinstance(stream.chunk, FootnoteCitationsGenerativeResponse):
            # Verify that footnote_to_context mapping exists
            assert stream.chunk.footnote_to_context is not None
            assert len(stream.chunk.footnote_to_context) > 0

            # Verify that the footnote IDs map to context keys from query_context
            for footnote_id, context_key in stream.chunk.footnote_to_context.items():
                assert context_key in chat_example_md_citations.query_context
                footnote_found = True

    assert footnote_found, "FootnoteCitationsGenerativeResponse chunk should be present"


@pytest.mark.asyncio
@pytest.mark.parametrize("client_class", [NucliaPredict, AsyncNucliaPredict])
async def test_image_generation_support(testing_config, client_class):
    client = client_class()
    generated = await maybe_await(
        client.generate(
            ChatModel(
                question="Generate an image of a futuristic city skyline at sunset with flying cars",
                retrieval=False,
                user_id="Nuclia PY CLI",
                generative_model="gemini-2.5-flash-image",
                max_tokens=4000,
                user_prompt=UserPrompt(prompt="{question}"),
            ),
        )
    )
    assert len(generated.images) > 0
    for image in generated.images:
        assert image.content_type.startswith("image/")
        assert len(image.b64encoded) > 100
