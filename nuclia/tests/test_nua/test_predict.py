from nuclia_models.predict.generative_responses import TextGenerativeResponse

from nuclia.lib.nua_responses import ChatModel, UserPrompt
from nuclia.sdk.predict import AsyncNucliaPredict, NucliaPredict
import pytest
from nuclia_models.predict.remi import RemiRequest


def test_predict(testing_config):
    np = NucliaPredict()
    embed = np.sentence(text="This is my text", model="multilingual-2024-05-06")
    assert embed.time > 0
    assert len(embed.data) == 1024


def test_predict_query(testing_config):
    np = NucliaPredict()
    query = np.query(
        text="Ramon, this is my text",
        semantic_model="multilingual-2024-05-06",
        token_model="multilingual",
        generative_model="chatgpt-azure-4o-mini",
    )
    assert query.language == "en"
    assert query.visual_llm is True
    assert query.entities and query.entities.tokens[0].text == "Ramon"
    assert query.sentence and len(query.sentence.data) == 1024


def test_rag(testing_config):
    np = NucliaPredict()
    generated = np.rag(
        question="Which is the CEO of Nuclia?",
        context=[
            "Nuclia CTO is Ramon Navarro",
            "Eudald Camprubí is CEO at the same company as Ramon Navarro",
        ],
        model="chatgpt-azure-4o-mini",
    )
    assert "Eudald" in generated.answer


def test_generative(testing_config):
    np = NucliaPredict()
    generated = np.generate(text="How much is 2 + 2?", model="chatgpt-azure-4o-mini")
    assert "4" in generated.answer


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
    async for stream in np.generate_stream(
        text="How much is 2 + 2?", model="chatgpt-azure-4o-mini"
    ):
        if isinstance(stream.chunk, TextGenerativeResponse) and stream.chunk.text:
            if "4" in stream.chunk.text:
                found = True
    assert found


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
        )
    )
    assert results.answer_relevance.score >= 4

    assert results.context_relevance[0] >= 4
    assert results.groundedness[0] >= 4

    assert results.context_relevance[1] < 2
    assert results.groundedness[1] < 2
