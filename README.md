# Nuclia Python Client

In order to install

```bash
pip install nuclia
```

## Authentication

### Nuclia

You can login with your Nuclia user [How to sign-up](https://nuclia.cloud/user/signup) via

```bash
nuclia auth login
```

### Nuclia Knowledgebox

You can login to a specific knowledgebox if you have a Service Token (How to get a Service Token) or your NucliaDB is [deployed on-premise](https://docs.nuclia.dev/docs/nucliadb/deploy)

```bash
nuclia auth kb --url KB_URL --token SERVICE_TOKEN
```

KB_URL its the url of the Knowledge Box. On the cloud service you can retrieve it on the dashboard. On the on-premise/community deployment its the url mapped to it.

### Nuclia Understanding API

You can login with a Nuclia Understanding API key to process files, predict and train using our system

```bash
nuclia auth nua --key ZZZZ
```

## Documentation

You can find the documentation [here](https://github.com/nuclia/nuclia.py/tree/main/docs/01-README.md)
