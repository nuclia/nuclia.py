# Search

## Search experience

Its the most basic search experience at Nuclia. You can search resources and paragraphs that match a query by a fulltext match, a fuzzy match or a semantic match. The results will be ordered by each search using BM25, fuzzy distance and semantic distance.

```bash
nuclia search --query="My search"
```

```python
from nuclia import sdk
search = sdk.NucliaSearch()
search.search(query="My search")
```

## Find experience

You get the list of paragraphs matching semantically and by keywords ordered together with a generic reranking strategy.

```bash
nuclia find --query="My search"
```

```python
from nuclia import sdk
search = sdk.NucliaSearch()
search.find(query="My search")
```

## Ask experience

Based on the find experience we use a generative AI to answer the question based on the context without hallucinations and with the find result and relations

```bash
nuclia ask --query="My search"
```

```python
from nuclia import sdk
search = sdk.NucliaSearch()
search.ask(query="My search")
```
