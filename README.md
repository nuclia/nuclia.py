# Nuclia Python Client

In order to install

```bash
pip install nuclia
```

## Authentication

### Nuclia

You can login with your Nuclia user [How to sign-up](https://rag.progress.cloud/user/signup) via

```bash
nuclia auth login
```

### Nuclia Knowledgebox

You can login to a specific knowledgebox if you have a Service Token (How to get a Service Token) or your NucliaDB is [deployed on-premise](https://docs.rag.progress.cloud/docs/nucliadb/deploy)

```bash
nuclia auth kb --url KB_URL --token SERVICE_TOKEN
```

KB_URL its the url of the Knowledge Box. On the cloud service you can retrieve it on the dashboard. On the on-premise/community deployment its the url mapped to it.

### Nuclia Understanding API

You can login with a Nuclia Understanding API key to process files, predict and train using our system

```bash
nuclia auth nua --key ZZZZ
```

## Guardrails

Account guardrail policies can be managed with the synchronous or asynchronous
SDK:

```python
from nuclia.lib.guardrails import CreateGuardrailPolicy
from nuclia.sdk import NucliaGuardrails

guardrails = NucliaGuardrails()
policy = guardrails.create(
    CreateGuardrailPolicy(
        name="Safety policy",
        instruction="Flag requests that ask for dangerous instructions.",
        query="Does the request violate the safety policy?",
        enabled=True,
        blocking=True,
    ),
    zone="europe-1",
)
```

Enabled account policies are evaluated automatically for Predict chat requests.
Content can also be evaluated directly against a configured or inline policy:

```python
from nuclia.lib.guardrails import GuardrailRequest
from nuclia.sdk import NucliaPredict

result = NucliaPredict().guardrail(
    GuardrailRequest(
        content="Content to evaluate",
        policy_id=str(policy.id),
    )
)
```

Policy violations always block chat generation. The `blocking` setting controls
failure handling: evaluation failures fail closed when enabled and fail open
when disabled.

## Documentation

You can find the documentation [here](https://github.com/nuclia/nuclia.py/tree/main/docs/01-README.md)

## For internal use

Find more information on the internal CI setup [here](https://github.com/nuclia/internal/tree/main/ci/nucliapy.md)