from nuclia import sdk
from nuclia_models.accounts.backups import BackupCreate, BackupRestore
from nuclia.tests.fixtures import TESTING_ACCOUNT_SLUG, TESTING_KBID
import random
import string
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
    new_kb_slug = "BackupTestSDK" + "".join(random.choices(string.ascii_letters, k=4))
    with pytest.raises(Exception) as exc_info:
        _ = sdk.NucliaBackup().restore(
            restore=BackupRestore(
                slug=new_kb_slug, title="Test SDK KB (can be deleted)"
            ),
            backup_id=backup.id,
            zone=ZONE,
        )

    # We don't want to wait till backup is ready to not slow down the test pipeline.
    # We already have a test for this on E2E repo
    expected_message = {
        "status": 409,
        "message": '{"detail":"Backup is still in progress. Please wait until it is completed."}',
    }
    assert exc_info.value.args[0] == expected_message

    # Delete the backup
    sdk.NucliaBackup().delete(id=backup.id, zone=ZONE)


def test_delete_all_backups(testing_config):
    sdk.NucliaAccounts().default(TESTING_ACCOUNT_SLUG)

    backups = sdk.NucliaBackup().list(zone=ZONE)
    for b in backups:
        # Delete backup
        sdk.NucliaBackup().delete(id=b.id, zone=ZONE)


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
    new_kb_slug = "BackupTestSDK" + "".join(random.choices(string.ascii_letters, k=4))
    with pytest.raises(Exception) as exc_info:
        _ = await sdk.NucliaBackup().restore(
            restore=BackupRestore(
                slug=new_kb_slug, title="Test SDK KB (can be deleted)"
            ),
            backup_id=backup.id,
            zone=ZONE,
        )

    # We don't want to wait till backup is ready to not slow down the test pipeline.
    # We already have a test for this on E2E repo
    expected_message = {
        "status": 409,
        "message": '{"detail":"Backup is still in progress. Please wait until it is completed."}',
    }
    assert exc_info.value.args[0] == expected_message

    # Delete the backup
    await sdk.AsyncNucliaBackup().delete(id=backup.id, zone=ZONE)
