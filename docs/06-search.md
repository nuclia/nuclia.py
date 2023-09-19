# Search

## Search experience

Its the most basic search experience at Nuclia. You can search resources and paragraphs that match a query by a fulltext match, a fuzzy match or a semantic match. The results will be ordered by each search using BM25, fuzzy distance and semantic distance.

```bash
nuclia kb search search --query="My search"
```

```python
from nuclia import sdk
search = sdk.NucliaSearch()
search.search(query="My search")
```

Get JSON output:

```bash
nuclia kb search search --query="My search" --json
```

Get YAML output:

```bash
nuclia kb search search --query="My search" --yaml
```

## Find experience

You get the list of paragraphs matching semantically and by keywords ordered together with a generic reranking strategy.

```bash
nuclia kb search find --query="My search"
```

```python
from nuclia import sdk
search = sdk.NucliaSearch()
search.find(query="My search")
```

It also supports indented and YAML output.

## Chat experience

Based on the find experience we use a generative AI to answer the question based on the context without hallucinations and with the find result and relations

```bash
nuclia kb search chat --query="My search"
```

```python
from nuclia import sdk
search = sdk.NucliaSearch()
search.chat(query="My search")
```
