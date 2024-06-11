# Search and answer generation

## Search

Nuclia supports 2 different search endpoints:

- `search`: returns several result sets according the different search techniques (full-text, fuzzy, semantic).
- `find`: returns a single result set where all different results are merged into a hierarchical structure.

Both endpoints support the same query parameters.

- CLI:

  ```bash
  nuclia kb search search --query="My search"
  nuclia kb search find --query="My search" --filters="['/icon/application/pdf','/classification.labels/region/Asia']"
  ```

- SDK:

  ```python
  from nuclia import sdk
  search = sdk.NucliaSearch()
  search.search(query="My search", filters=['/icon/application/pdf', '/classification.labels/region/Asia'])
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

Based on a `find` request, Nuclia uses a generative AI to answer the question based on the context without hallucinations and with the find result and relations.

- CLI:

  ```bash
  nuclia kb search ask --query="My question"
  ```

- SDK:

  ```python
  from nuclia import sdk
  search = sdk.NucliaSearch()
  search.ask(query="My question")
  ```

  You can also use the `AskRequest` item to configure the request with all the parameters supported:

  ```python
  from nuclia import sdk
  from nucliadb_models.search import AskRequest

  search = sdk.NucliaSearch()
  query = AskRequest(query="My question", prefer_markdown=True, citations=True)
  search.ask(query)
  ```

## Filtering

Any endpoint that involves search (`search`, `find` and `ask`) also support more advanced filtering expressions. Expressions can have one of the following operators:

- `all`: this is the default. Will make search return results containing all specified filter labels.
- `any`: returns results containing at least one of the labels.
- `none`: returns results that do not contain any of the labels.
- `not_all`: returns results that do not contain all specified labels.

Note that multiple expressions can be chained in the `filters` parameter and the conjunction of all of them will be computed.

Here are some examples:

- CLI:

  ```bash
  nuclia kb search find --query="My search" --filters="[{'any':['/icon/application/pdf','/icon/image/mp4']}]"
  ```

- SDK:

  ```python
  from nuclia import sdk
  from nucliadb_models.search import Filter

  search = sdk.NucliaSearch()
  search.ask(
    query="My question",
    filters=[Filter(any=['/classification.labels/region/Europe','/classification.labels/region/Asia'])],
  )
  ```
