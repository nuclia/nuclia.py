# Nuclia Python Client

In order to install

```bash
pip install nuclia
```

## Authentication

You can login with your Nuclia user (How to signup) via

```bash
nuclia auth
```

You can login to a specific knowledgebox if you have a Service Token (How to get a Service Token)

```bash
nuclia auth -kb XXX -a YYYY --key ZZZZ
```

You can login with a NUA key for prediction

```bash
nuclia auth --key ZZZZ
```
