# Upload use case

All examples has assumed you [authenticated](AUTH.md) and defined a [default](DEFAULT.md) knowledgebox. In case you want to overwrite or define a one time knowledgebox you should add on any command/function the `url` and `api_key` parameter.

## Upload a file in a KnowledgeBox

Pushing a file to a knowledgebox its easy as:

```bash
nuclia kb upload file --path=FILE_PATH
```

```python
from nuclia import sdk
upload = sdk.NucliaUpload()
upload.file(FILE_PATH)
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

## List resources on a kb

```bash
nuclia kb list
```

## Delete a resource on a kb

```bash
nuclia kb delete --rid=RID
```
