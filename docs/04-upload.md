# Upload use case

All examples assume you [authenticated](02-auth.md) and defined a [default](03-default.md) knowledgebox. In case you want to overwrite or define a one time knowledgebox you should add on any command/function the `url` and `api_key` parameter.

## Upload a file in a KnowledgeBox

Push a file to a knowledgebox:

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

## Upload a remote file in a KnowledgeBox

Streaming a file to a knowledgebox from an external URL its easy as:

```bash
nuclia kb upload remote --origin=REMOTE_FILE_URL
```

## Upload a remote file in an existing resource

In case you want to stream a file inside a resource you can use:

```bash
nuclia kb upload remote --origin=REMOTE_FILE_URL --rid=RESOURCE_ID --field=FIELD_ID
```

In case that `FIELD_ID` is not defined filename will be used

## Upload a text in a KnowledgeBox

Push a text to a knowledgebox:

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

## Upload an URL in a KnowledgeBox

Push a text to a knowledgebox:

```bash
nuclia kb upload link --uri=THE_URI
```

```python
from nuclia import sdk
upload = sdk.NucliaUpload()
upload.link(uri=THE_URI)
```

## List resources on a kb

```bash
nuclia kb list
```

## Delete a resource on a kb

```bash
nuclia kb delete --rid=RID
```
