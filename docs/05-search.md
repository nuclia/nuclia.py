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
  nuclia kb search chat --query="My question"
  ```

- SDK:

  ```python
  from nuclia import sdk
  search = sdk.NucliaSearch()
  search.chat(query="My question")
  ```

## Filtering

Any endpoint that involves search (`search`, `find` and `chat`) support the following filtering parameters:

- `filters`: a list of label strings to filter for.
- `filters_operator`: the filtering operator to use for the request. It can be one of the following:
  - `all`: this is the default. Will make search return results containing all specified filter labels.
  - `any`: returns results containing at least one of the labels.
  - `none`: returns results that do not contain any of the labels.
  - `not_all`: returns results that do not contain all specified labels.

Here are some examples:

- CLI:

  ```bash
  nuclia kb search find --query="My search" --filters="['/classification.labels/region/Europe','/classification.labels/region/Asia']" --filters_operator="any"
  ```

- SDK:

  ```python
  from nuclia import sdk
  search = sdk.NucliaSearch()
  search.chat(query="My question", filters=['/classification.labels/region/Europe','/classification.labels/region/Asia'], filters_operator="any")
  ```
