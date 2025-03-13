# Backup and Restore a Knowledge Box

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
