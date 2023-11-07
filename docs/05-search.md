# Search and answer generation

## Search

Nuclia supports 2 different search endpoints:

- `search`: returns several result sets according the different search techniques (full-text, fuzzy, semantic).
- `find`: returns a single result set where all different results are merged into a hierarchical structure.

Both endpoints support the same query parameters.

- CLI:

  ```bash
  nuclia kb search search --query="My search"
  nuclia kb search find --query="My search"
  ```

- SDK:

  ```python
  from nuclia import sdk
  search = sdk.NucliaSearch()
  search.search(query="My search")
  search.find(query="My search")
  ```

Get JSON output:

```bash
nuclia kb search find --query="My search" --json
```

Get YAML output:

```bash
nuclia kb search search --query="My search" --yaml
```

## Generative answer

Based on a `find` request, Nuclia use a generative AI to answer the question based on the context without hallucinations and with the find result and relations.

- CLI:

  ```bash
  nuclia kb search chat --query="My question"
  ```

- SDK:

  ```python
  from nuclia import sdk
  search = sdk.NucliaSearch()
  search.chat(query="My question")
  ```
