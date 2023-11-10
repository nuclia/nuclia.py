# The Nuclia Understanding API

The Nuclia Understanding API (or NUA) allows to call the processing services of Nuclia and retrieve the results, it does not involve any Knowledge Box, nothing gets stored in Nuclia cloud infrastructure.

## Authentication with a NUA key

- CLI: `nuclia auth nua REGION NUA_KEY`
- SDK:

  ```python
  from nuclia import sdk
  sdk.NucliaAuth().nua(region=REGION, token=NUA_KEY)
  ```

In order to check which NUA keys you have access you can run execute:

- CLI:

  ```bash
  nuclia nuas list
  ```

- SDK:

  ```python
  from nuclia import sdk
  nuas = sdk.NucliaNUAS()
  nuas.list()
  ```

In order to set default NUA key you should use:

```bash
nuclia nuas default NUA_CLIENT_ID
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
