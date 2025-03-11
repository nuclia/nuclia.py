from nuclia import sdk
from nuclia_models.accounts.backups import BackupCreate, BackupRestore
from nuclia.tests.fixtures import TESTING_ACCOUNT_SLUG, TESTING_KBID
import random
import string
from nuclia.sdk.kbs import NucliaKBS

ZONE = "europe-1"


def test_backup(testing_config):
    sdk.NucliaAccounts().default(TESTING_ACCOUNT_SLUG)

    backup = sdk.NucliaBackup().create(
        backup=BackupCreate(kb_id=TESTING_KBID),
        zone=ZONE,
    )
    assert backup.id is not None

    backups = sdk.NucliaBackup().list(zone=ZONE)
    backup_ids = [b.id for b in backups]
    assert backup.id in backup_ids

    new_kb_slug = "".join(random.choices(string.ascii_letters, k=6))
    new_kb = sdk.NucliaBackup().restore(
        restore=BackupRestore(slug=new_kb_slug), backup_id=backup.id, zone=ZONE
    )

    kbs = NucliaKBS()
    kbs.delete(id=new_kb.id)

    sdk.NucliaBackup().delete(id=backup.id, zone=ZONE)


def test_delete_all_backups(testing_config):
    sdk.NucliaAccounts().default(TESTING_ACCOUNT_SLUG)

    backups = sdk.NucliaBackup().list(zone=ZONE)
    for b in backups:
        sdk.NucliaBackup().delete(id=b.id, zone=ZONE)
