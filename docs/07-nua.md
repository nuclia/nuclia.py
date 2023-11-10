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

### Agent

`agent` allows to generate LLM agents from an initial prompt:

- CLI:

  ```bash
  nuclia nua agent generate_prompt --text="Toronto"
  ```

  (with the CLI, you will obtain the prompt itself, not an agent directly)

- SDK:

  ```python
  from nuclia import sdk
  nuclia_agent = sdk.NucliaAgent()
  agent = nuclia_agent.generate_agent("Toronto")
  print(agent.ask("Tell me about the parks"))
  ```

  (with the SDK, you will obtain an agent directly, you can call `ask` on it to generate answers)
