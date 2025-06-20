# Upload contents

All examples assume you [authenticated](02-auth.md) and defined a [default Knowledge Box](03-kb.md).

In case you want to overwrite or define a one time knowledgebox you should add on any command/function the `url` and `api_key` parameter.

## Upload a file in a KnowledgeBox

Push a file to a Knowledge Box:

```bash
nuclia kb upload file --path=FILE_PATH
```

```python
from nuclia import sdk
upload = sdk.NucliaUpload()
upload.file(path=FILE_PATH)
```

## Upload a file in an existing resource

In case you want to upload a file inside a resource you can use:

```bash
nuclia kb upload file --path=FILE_PATH  --rid=RESOURCE_ID --field=FIELD_ID
```

In case that `FIELD_ID` is not defined filename will be used

## Upload a remote file in a Knowledge Box

Streaming a file to a Knowledge Box from an external URL its easy as:

```bash
nuclia kb upload remote --origin=REMOTE_FILE_URL
```

## Interpret tables in a file

When uploading a file, you can ask Nuclia to interpret tables in the file:

```bash
nuclia kb upload file --path=FILE_PATH --interpretTables
```

```python
from nuclia import sdk
upload = sdk.NucliaUpload()
upload.file(path=FILE_PATH, interpretTables=True)
```

## Upload a remote file in an existing resource

In case you want to stream a file inside a resource you can use:

```bash
nuclia kb upload remote --origin=REMOTE_FILE_URL --rid=RESOURCE_ID --field=FIELD_ID
```

In case that `FIELD_ID` is not defined filename will be used

## Upload a text in a Knowledge Box

Push a text to a Knowledge Box:

```bash
nuclia kb upload text --path=FILE_PATH
```

```python
from nuclia import sdk
upload = sdk.NucliaUpload()
upload.text(FILE_PATH)
```

Pass the text from standard input:

```bash
echo "This is a message" | nuclia kb upload text --stdin
```

Set a specific format (default is `PLAIN`):

```bash
nuclia kb upload text --path=FILE_PATH --format=MARKDOWN
```

Define a slug for the resource:

```bash
nuclia kb upload text --path=FILE_PATH --slug=SLUG
```

Pass `origin` or `extra` metadata:

```bash
nuclia kb upload text --path=FILE_PATH --origin='{"url":"https://somwhere.com"}' --extra='{"metadata":{"whatever":42}}'
```

## Upload a web page in a Knowledge Box

Push a link to a Knowledge Box:

```bash
nuclia kb upload link --uri=THE_URI
```

```python
from nuclia import sdk
upload = sdk.NucliaUpload()
upload.link(uri=THE_URI)
```

You can narrow down the indexed content by providing a CSS selector:

```bash
nuclia kb upload link --uri=THE_URI --selector="CSS_SELECTOR"
```

## Upload a conversation

First, you need to provide a JSON file containing the conversation messages following this format:

```json
[
  {
    "who": "ORIGIN_UUID",
    "to": ["DESTINATION_UUID"],
    "ident": "UNIQUE_IDENTIFIER",
    "timestamp": "MESSAGE_DATETIME",
    "content": {
      "text": "MESSAGE",
      "format": "MESSAGE_TYPE"
    }
  }
]
```

- `ORIGIN_UUID`: Identification of the user who sent the message
- `DESTINATION_UUID`: Identification of the users who received the message
- `UNIQUE_IDENTIFIER`: Identification of the message, needs to be unique in the conversation
- `MESSAGE_DATETIME`: Message date time in ISO format
- `MESSAGE_TYPE`: Format of the message: `0` for `PLAIN` or `1` for `HTML` or `MARKDOWN` or `RST`

[Example](https://github.com/nuclia/nuclia.py/nuclia/tests/assets/conversation.json)

Then, you can upload it with:

- CLI:

  ```bash
  nuclia kb upload conversation --path=FILE
  ```

- SDK:
  ```python
  from nuclia import sdk
  upload = sdk.NucliaUpload()
  upload.conversation(path=FILE)
  ```

## Upload a custom knowledge graph

Create a custom knowledge graph:

- CLI:

  ```bash
  nuclia kb add_graph --slug=SLUG --graph=JSON_ENCODED_GRAPH
  ```

- SDK:
  ```python
  from nuclia import sdk
  kb = sdk.NucliaKB()
  kb.add_graph(slug=SLUG, graph=[
     {
         "source": {"group": "People", "value": "Alice"},
         "destination": {"group": "People", "value": "Bob"},
         "label": "is friend of",
     },
     {
         "source": {"group": "People", "value": "Alice"},
         "destination": {"group": "City", "value": "Toulouse"},
         "label": "lives in",
     },
     {
         "source": {"group": "People", "value": "Bob"},
         "destination": {"group": "Food", "value": "Cheese"},
         "label": "eat",
     },
  ])
  ```

Get a graph:

- CLI:

  ```bash
  nuclia kb get_graph --slug=SLUG
  ```

- SDK:
  ```python
  from nuclia import sdk
  kb = sdk.NucliaKB()
  graph = kb.get_graph(slug=SLUG)
  ```

Delete a graph:

- CLI:

  ```bash
  nuclia kb delete_graph --slug=SLUG
  ```

- SDK:
  ```python
  from nuclia import sdk
  kb = sdk.NucliaKB()
  kb.delete_graph(slug=SLUG)
  ```

Update a graph:

```python
from nuclia import sdk
kb = sdk.NucliaKB()
kb.update_graph(slug="graph1", graph=[
    {
        "source": {"group": "People", "value": "Alice"},
        "destination": {"group": "People", "value": "Victor"},
        "label": "is friend of",
    }
])
```

Overrides a graph:

```python
from nuclia import sdk
kb = sdk.NucliaKB()
kb.update_graph(slug="graph1", overrides=True, graph=[
    {
        "source": {"group": "People", "value": "Alice"},
        "destination": {"group": "People", "value": "Victor"},
        "label": "is friend of",
    }
])
```

## Use extract strategies

Extract strategies allow you to perform specific processing at ingestion time. It can be useful to handle complex tables extraction, or to support unusual layouts.

### Manage extract strategies

CLI:

```bash
nuclia kb extract_strategies add --config='{"name":"strategy1","vllm_config":{}}'
nuclia kb extract_strategies list
nuclia kb extract_strategies delete --id=1361c0c7-918a-4a7f-b44b-ba37437619fb
```

SDK:

```python
from nuclia import sdk
extract_strategies = sdk.NucliaKB().extract_strategies
print(extract_strategies.list())
id = extract_strategies.add(config={"name": "strategy1", "vllm_config": {}})
extract_strategies.delete(id=id)
```

### Use extract strategies

CLI:

```bash
nuclia kb upload file --path=FILE_PATH --extract_strategy=1361c0c7-918a-4a7f-b44b-ba37437619fb
```

SDK:

```python
from nuclia import sdk
upload = sdk.NucliaUpload()
upload.file(path=FILE_PATH, extract_strategy="1361c0c7-918a-4a7f-b44b-ba37437619fb")
```
