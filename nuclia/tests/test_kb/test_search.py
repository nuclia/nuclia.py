from nuclia.sdk.search import AsyncNucliaSearch, NucliaSearch
from nucliadb_models.search import AskRequest, CustomPrompt


def test_find(testing_config):
    search = NucliaSearch()
    results = search.find(query="Who is hedy Lamarr?")
    assert len(results.resources.keys()) == 2
    titles = [r.title for r in results.resources.values()]
    assert "Lamarr Lesson plan.pdf" in titles


def test_find_object(testing_config):
    search = NucliaSearch()
    results = search.find(query={"query": "Who is hedy Lamarr?"})
    assert len(results.resources.keys()) == 2
    titles = [r.title for r in results.resources.values()]
    assert "Lamarr Lesson plan.pdf" in titles


def test_ask(testing_config):
    search = NucliaSearch()
    results = search.ask(query="Who is Hedy Lamarr?")
    answer = results.answer.decode()
    assert "Lamarr" in answer


def test_ask_with_custom_prompt(testing_config):
    search = NucliaSearch()
    ask = AskRequest(
        query="Are Pepito Palotes and Hedy Lamarr friends?",
        prompt=CustomPrompt(
            system="Answer the question. If you don't know the anwser, write 'I don't know' and a list of bullet points with the reasons why you don't know the answer.",
            user="Based on this context {context}, answer the question {question}",
        ),
        generative_model="chatgpt-azure-4o",
    )
    results = search.ask(query=ask)
    answer = results.answer.decode()
    assert "I don't know" in answer, print(answer)


def test_ask_with_markdown_answer(testing_config):
    search = NucliaSearch()
    ask = AskRequest(
        query="Who is Hedy Lamarr and what did she do?",
        prompt=CustomPrompt(
            system="Answer the question and use lists as much as possible.",
            user="Based on this context {context}, answer the question {question}",
        ),
        generative_model="gemini-1-5-pro",
        prefer_markdown=True,
    )
    results = search.ask(query=ask)
    answer = results.answer.decode()
    markdown_keywords = ["**", "#", "1.", "*"]
    assert any([keyword in answer.lower() for keyword in markdown_keywords]), answer


def test_search(testing_config):
    search = NucliaSearch()
    results = search.search(query="Who is hedy Lamarr?")
    assert len(results.resources.keys()) == 2
    titles = [r.title for r in results.resources.values()]
    assert "Lamarr Lesson plan.pdf" in titles


def test_search_object(testing_config):
    search = NucliaSearch()
    results = search.search(query={"query": "Who is hedy Lamarr?"})
    assert len(results.resources.keys()) == 2
    titles = [r.title for r in results.resources.values()]
    assert "Lamarr Lesson plan.pdf" in titles


def test_filters(testing_config):
    search = NucliaSearch()
    results = search.find(
        query="Who is hedy Lamarr?", filters=["/icon/application/pdf"]
    )
    assert len(results.resources.keys()) == 1


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


async def test_ask_json_async(testing_config):
    search = AsyncNucliaSearch()
    results = await search.ask_json(
        query="Who is hedy Lamarr?", filters=["/icon/application/pdf"], schema=SCHEMA
    )

    assert "TECHNOLOGY" in results.object["document_type"]
