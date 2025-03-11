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

## Backup and Restore a Knowledge Box

For small knowledge boxes, the import/export feature is sufficient. However, for larger knowledge boxes or to ensure a complete state capture, using backups is more reliable.

---

## Create a Backup

You can create a backup to capture the current state of your knowledge box (KB). This includes both the KB configuration and all associated resources.  

:::note
Backup creation is **asynchronous**. The returned object represents the backup request, and the following fields will be populated **once the backup is completed**
- **`finished_at`**: The timestamp (`datetime`) indicating when the backup was completed.  
- **`size`**: The total size of the backup in bytes.
:::

```python
from nuclia import sdk
from nuclia_models.accounts.backups import BackupCreate

# Authenticate and select the account
sdk.NucliaAuth().login()
sdk.NucliaAccounts().default("<your-account-slug>")

# Create a backup
backup = sdk.NucliaBackup().create(
    backup=BackupCreate(kb_id="<your-kb-id>"),
    zone="<zone>"
)
print(backup)
```

---

## List Created Backups

Retrieve a list of all backups in a specified zone within your account.

```python
from nuclia import sdk

sdk.NucliaAuth().login()
sdk.NucliaAccounts().default("<your-account-slug>")

# List backups
backups = sdk.NucliaBackup().list(zone="<zone>")
print(backups)
```

---

## Delete a Backup

Delete a specific backup by providing its ID.

```python
from nuclia import sdk

sdk.NucliaAuth().login()
sdk.NucliaAccounts().default("<your-account-slug>")

# Delete a backup
sdk.NucliaBackup().delete(id="<backup-id-to-delete>", zone="<zone>")
```

---

## Restore a Backup

Restore a backup into a **new** knowledge box (KB).  

- The **original** knowledge box will remain unchanged.  
- The **backup** will not be deleted after restoration.  
- You must provide a **unique slug** and **title** for the new knowledge box.  
- The new knowledge box is created **immediately**, but the restoration of resources occurs **asynchronously**. This process may take time depending on the **backup size** and other factors.

:::warning
- Ensure the `slug` is unique across your knowledge boxes.
:::

```python
from nuclia import sdk
from nuclia_models.accounts.backups import BackupRestore

sdk.NucliaAuth().login()
sdk.NucliaAccounts().default("<your-account-slug>")

# Restore a backup to a new knowledge box
new_kb = sdk.NucliaBackup().restore(
    restore=BackupRestore(slug="<new-kb-slug>", title="<new-kb-title>"),
    backup_id="<backup-id-to-restore>",
    zone="<zone>",
)
print(new_kb)
```
