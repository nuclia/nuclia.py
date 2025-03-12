from nuclia import sdk
from nuclia_models.accounts.backups import BackupCreate, BackupRestore
from nuclia.tests.fixtures import TESTING_ACCOUNT_SLUG, TESTING_KBID
import random
import string
from nuclia.sdk.kbs import NucliaKBS, AsyncNucliaKBS
import pytest

ZONE = "europe-1"


def test_backup(testing_config):
    sdk.NucliaAccounts().default(TESTING_ACCOUNT_SLUG)

    # Create a backup
    backup = sdk.NucliaBackup().create(
        backup=BackupCreate(kb_id=TESTING_KBID),
        zone=ZONE,
    )
    assert backup.id is not None

    backups = sdk.NucliaBackup().list(zone=ZONE)
    backup_ids = [b.id for b in backups]
    assert backup.id in backup_ids

    # Restore the KB
    new_kb_slug = "".join(random.choices(string.ascii_letters, k=6))
    new_kb = sdk.NucliaBackup().restore(
        restore=BackupRestore(slug=new_kb_slug, title="SDK test kb (can be deleted)"),
        backup_id=backup.id,
        zone=ZONE,
    )

    # Delete the restored KB
    kbs = NucliaKBS()
    kbs.delete(id=new_kb.id)

    # Delete the backup
    sdk.NucliaBackup().delete(id=backup.id, zone=ZONE)


def test_delete_all_backups(testing_config):
    sdk.NucliaAccounts().default(TESTING_ACCOUNT_SLUG)
    kbs = NucliaKBS()

    backups = sdk.NucliaBackup().list(zone=ZONE)
    for b in backups:
        # Delete backup
        sdk.NucliaBackup().delete(id=b.id, zone=ZONE)
        # Delete KB
        kbs.delete(id=b.kb_data.id)


@pytest.mark.asyncio
async def test_backup_async(testing_config):
    sdk.NucliaAccounts().default(TESTING_ACCOUNT_SLUG)

    # Create a backup
    backup = await sdk.AsyncNucliaBackup().create(
        backup=BackupCreate(kb_id=TESTING_KBID),
        zone=ZONE,
    )
    assert backup.id is not None

    backups = await sdk.AsyncNucliaBackup().list(zone=ZONE)
    backup_ids = [b.id for b in backups]
    assert backup.id in backup_ids

    # Restore the KB
    new_kb_slug = "".join(random.choices(string.ascii_letters, k=6))
    new_kb = await sdk.AsyncNucliaBackup().restore(
        restore=BackupRestore(slug=new_kb_slug, title="SDK test kb (can be deleted)"),
        backup_id=backup.id,
        zone=ZONE,
    )

    # Delete the restored KB
    kbs = AsyncNucliaKBS()
    await kbs.delete(id=new_kb.id)

    # Delete the backup
    await sdk.AsyncNucliaBackup().delete(id=backup.id, zone=ZONE)
