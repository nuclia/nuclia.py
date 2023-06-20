# Managing default configuration

## Knowledge Boxes

Authenticating your client against the NucliaDB API will ask to make the KnowledgeBox as the default one.

In order to check which Knowledge boxes you have access you can run execute:

```bash
nuclia kbs list
```

```python
from nuclia import sdk
kbs = sdk.NucliaKBS()
kbs.list()
```

In order to set default KB you should use:

```bash
nuclia kbs default KBID
```

```python
from nuclia import sdk
kbs = sdk.NucliaKBS()
kbs.default(KBID)
```

## Nuclia Understanding API key

In order to check which NUA keys you have access you can run execute:

```bash
nuclia nuas list
```

```python
from nuclia import sdk
nuas = sdk.NucliaNUAS()
nuas.list()
```

In order to set default NUA key you should use:

```bash
nuclia nuas default "NUA_CLIENT_ID"
```

```python
from nuclia import sdk
nuas = sdk.NucliaNUAS()
nuas.default(NUA_CLIENT_ID)
```