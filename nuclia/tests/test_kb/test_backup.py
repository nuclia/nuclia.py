from nuclia.tests.fixtures import IS_PROD
from nuclia import sdk
from nuclia_models.accounts.backups import BackupCreate
from nuclia.tests.fixtures import TESTING_ACCOUNT_SLUG, TESTING_KBID

ZONE = "europe-1"


def test_create_backup(testing_config):
    if not IS_PROD:
        assert True
        return

    sdk.NucliaAccounts().default(TESTING_ACCOUNT_SLUG)

    backup = sdk.NucliaBackup().create(
        backup=BackupCreate(kb_id=TESTING_KBID),
        zone=ZONE,
    )
    assert backup.id is not None

    backups = sdk.NucliaBackup().list(zone=ZONE)
    backup_ids = [b.id for b in backups]
    assert backup.id in backup_ids

    sdk.NucliaBackup().delete(id=backup.id, zone=ZONE)


def test_delete_all_backups(testing_config):
    if not IS_PROD:
        assert True
        return

    sdk.NucliaAccounts().default(TESTING_ACCOUNT_SLUG)

    backups = sdk.NucliaBackup().list(zone=ZONE)
    for id in backups:
        sdk.NucliaBackup().delete(id=id, zone=ZONE)
