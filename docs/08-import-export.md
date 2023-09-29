# Import/export

## Export a kb

```sh
nuclia kbs my-source-kb default
nuclia kb exports start --path=/some/path/foobar

> Export is ready to be downloaded.
> Downloading export 8be5339818f443f8b6c0afc143d2fe02 to /some/path/foobar: 7.13MB [00:05, 1.36MB/s]
```

## Import it to another kb

```sh
nuclia kbs my-dst-kb default
nuclia kb imports start --path=/some/path/foobar

> Uploading from /some/path/foobar to import: 7.13MB [00:01, 3.77MB/s]
> import_id='317e6816a661450e91ba192afad96b99'
```

The returned `import_id` can be used to check the status of the import:

```sh
nuclia kb imports status --import_id=317e6816a661450e91ba192afad96b99

> status=<Status.FINISHED: 'finished'>
```

Alternately, you can start import and use `--sync`, so the command waits for it to finish:

```sh
nuclia kb imports start --path=/some/path/foobar --sync
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
assert imports.status(import_id=import_id).status == "finished"

imports.start(path="/some/path/kb.export", sync=True)
```
