# The Nuclia Understanding API

The Nuclia Understanding API (or NUA) allows to call the processing services of Nuclia and retrieve the results, it does not involve any Knowledge Box, nothing gets stored in Nuclia cloud infrastructure.

## Authentication with a NUA key

- CLI: `nuclia auth nua REGION NUA_KEY`
- SDK:

  ```python
  from nuclia import sdk
  sdk.NucliaAuth().nua(token=NUA_KEY)
  ```

In order to check which NUA keys you have access you can run execute:

- CLI:

  ```bash
  nuclia auth nuas
  ```

- SDK:

  ```python
  from nuclia import sdk
  sdk.NucliaAuth().nuas()
  ```

In order to set default NUA key you should use:

```bash
nuclia auth default_nua NUA_CLIENT_ID
```

## Services

### Predict

`predict` can return the embeddings of an input text:

- CLI:

  ```bash
  nuclia nua predict sentence --text="A SENTENCE"
  ```

- SDK:

  ```python
  from nuclia import sdk
  predict = sdk.NucliaPredict()
  predict.sentence(text="A SENTENCE")
  ```

It can identify tokens in a text:

- CLI:

  ```bash
  nuclia nua predict tokens --text="Who is Henriet? Does she speak English or Dutch?"
  ```

  > tokens=[Token(text='Henriet', ner='PERSON', start=7, end=14), Token(text='English', ner='LANGUAGE', start=31, end=38), Token(text='Dutch', ner='LANGUAGE', start=42, end=47)] time=0.009547710418701172

- SDK:

  ```python
  from nuclia import sdk
  predict = sdk.NucliaPredict()
  predict.tokens(text="Who is Henriet? Does she speak English or Dutch?")
  ```

It can generate text from a prompt:

- CLI:

  ```bash
  nuclia nua predict generate --text="How to tell a good story?"
  ```

- SDK:

  ```python
  from nuclia import sdk
  predict = sdk.NucliaPredict()
  predict.generate(text="How to tell a good story?")
  ```

It can summarize a list of texts:

- CLI:

  ```bash
  nuclia nua predict summarize --texts='["TEXT1", "TEXT2"]'
  ```

- SDK:

  ```python
  from nuclia import sdk
  predict = sdk.NucliaPredict()
  predict.summarize(texts=["TEXT1", "TEXT2"])
  ```

It can generate a response to a question given a context:

- CLI:

  ```bash
  nuclia nua predict rag --question="QUESTION" --context='["TEXT1", "TEXT2"]'
  ```

- SDK:

  ```python
  from nuclia import sdk
  predict = sdk.NucliaPredict()
  predict.rag(question="QUESTION", context=["TEXT1", "TEXT2"])
  ```

It can rephrase a user question into a proper question more suitable for a search engine (optionally using a context):

- CLI:

  ```bash
  nuclia nua predict rephrase --question="french revolution causes"
  > What were the causes of the French Revolution?
  nuclia nua predict rephrase --question="next step" --user_context='["pan con tomate recipe", "first step: blend the tomatoes"]'
  > What is the next step in the pan con tomate recipe after blending the tomatoes?
  ```

- SDK:

  ```python
  from nuclia import sdk
  predict = sdk.NucliaPredict()
  predict.rephrase(question="french revolution causes")
  ```

You can provide a custom prompt to the rephrase method:

```python
from nuclia import sdk
predict = sdk.NucliaPredict()
res = predict.rephrase(
    question="ONU creation date",
    prompt="Rephrase the question but preserve acronyms if any. Question: {question}"
)
```

It can also evaluate a RAG Experience using our REMi model, which will compute the Answer Relevance and Context Relevance and Groundedness scores for each context. More information about the REMi model can be found [here](https://nuclia.com/developers/remi-open-source-rag-evaluation-model/).

- CLI:

  ```bash
  nuclia nua predict remi --user_id="Nuclia PY CLI" --question="What is the capital of France?" --answer="Paris is the capital of France" --contexts='["Paris is the capital of France.", "Berlin is the capital of Germany."]'
  > time=1.0570876598358154 answer_relevance=AnswerRelevance(score=5, reason='The response is accurate and directly answers the query completely.') context_relevance=[5, 0] groundedness=[5, 0]
  ```

- SDK:
  
    ```python
    from nuclia import sdk
    from nuclia_models.predict.remi import RemiRequest
    predict = sdk.NucliaPredict()
    predict.remi(
        RemiRequest(
            user_id="Nuclia PY CLI",
            question="What is the capital of France?",
            answer="Paris is the capital of France!",
            contexts=[
                "Paris is the capital of France.",
                "Berlin is the capital of Germany.",
            ],
        )
    )
    ```

### Agent

`agent` allows to generate LLM agents from an initial prompt:

- CLI:

  ```bash
  nuclia nua agent generate_prompt --text="Toronto" --agent_definition="city guide"
  ```

  (with the CLI, you will obtain the prompt text itself, not an agent directly)

- SDK:

  ```python
  from nuclia import sdk
  nuclia_agent = sdk.NucliaAgent()
  agent = nuclia_agent.generate_agent("Toronto", "city guide")
  print(agent.ask("Tell me about the parks"))
  ```

  (with the SDK, you will obtain an agent directly, you can call `ask` on it to generate answers)

### Process

`process` allows to process a file:

- CLI:

  ```bash
  nuclia nua process file --path="path/to/file.txt"
  ```

  And you can check the status with:

  ```bash
  nuclia nua process status
  ```

- SDK:

  ```python
  from nuclia import sdk
  process = sdk.NucliaProcess()
  process.file(path="path/to/file.txt")
  print(process.status())
  ```
