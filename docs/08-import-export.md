# Import/export

## Export a kb

```sh
nuclia kbs default my-source-kb
nuclia kb exports start --path=/some/path/kb.export

> Export for KB started. export_id=77ae82a2acea4c708cd775e6ce0ab30b
> Generating export. Status: scheduled: 0resources [00:03, ?resources/s]
> Export is ready. Will be downloaded to /some/path/kb.export.
> Downloading data: 100%|█████████████████████████████████████████████████████████| 3.66M/3.66M [00:00<00:00, 14.1MiB/s
```

## Import it to another kb

```sh
nuclia kbs default my-destination-kb
nuclia kb imports start --path=/some/path/kb.export

> Importing from /some/path/kb.export
> Uploading data: 100%|███████████████████████████████████████████████████████████| 3.66M/3.66M [00:00<00:00, 23.1MiB/s]
> Import task started.
> import_id='134965fb268e4565a6f483152e7c520a'
```

The returned `import_id` can be used to check the status of the import:

```sh
nuclia kb imports status --import_id=317e6816a661450e91ba192afad96b99

> status=<Status.FINISHED: 'finished'>
```

Alternately, you can start import and use `--sync`, so the command waits for it to finish:

```sh
nuclia kb imports start --path=/some/path/kb.export --sync
```

## Using the SDK

```python
from nuclia import sdk

exports = sdk.NucliaExports()
export_id = exports.start().export_id
assert exports.status(export_id=export_id).value == "finished"
exports.download(export_id=export_id, path="/some/path/kb.export")

imports = sdk.NucliaImports()
import_id = imports.start(path="/some/path/kb.export").import_id
```

Then you can check the status of the import:

```python
assert imports.status(import_id=import_id).status == "finished"
```

You can also run the import synchronously:

```python
imports.start(path="/some/path/kb.export", sync=True)
```
