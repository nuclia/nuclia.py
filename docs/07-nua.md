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

At the moment, the only available service through the CLI/SDK is `predict`. `predict` returns the embeddings of the input text.

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
