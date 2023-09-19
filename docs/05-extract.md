# Extract data from a resource

Once you have [uploaded](04-upload.md) a resource you can extract data from it.

```bash
nuclia kb resource get --rid=RESOURCE_ID --show=extracted --json
```

```python
from nuclia import sdk
resource = sdk.NucliaResource()
resource.get(rid=RESOURCE_ID, show='extracted')
```

Note: If the resource is not processed yet, a warning will be shown.

The extracted data is nested in the `extracted` key of each resource's field.

For example, if you have upload a file with:

```bash
nuclia kb upload file --path=FILE_PATH --field=file1
```

the corresponding extracted data will be in `data.files.file1.extracted`.

It contains the extracted text, the paragraphs, the entities, the relations between entities and all the file metadata.

## Get embeddings

You can get the embeddings of the indexed text by using the `extracted=vectors` option:

```bash
nuclia kb resource get --rid=RESOURCE_ID --show=extracted --extracted=vectors --json
```

```python
from nuclia import sdk
resource = sdk.NucliaResource()
resource.get(rid=RESOURCE_ID, show='extracted', extracted='vectors')
```
