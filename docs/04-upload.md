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
