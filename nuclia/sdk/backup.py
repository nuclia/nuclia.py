from typing import Optional, Union

from nuclia import get_regional_url
from nuclia.data import get_auth, get_async_auth
from nuclia.decorators import account, accounts, zone
from nuclia.sdk.auth import NucliaAuth, AsyncNucliaAuth
from nuclia_models.accounts.backups import (
    BackupCreate,
    BackupCreateResponse,
    BackupResponse,
    BackupRestore,
)
from pydantic import TypeAdapter, BaseModel
from uuid import UUID

BACKUPS_ENDPOINT = "/api/v1/account/{account_id}/backups"
BACKUP_ENDPOINT = "/api/v1/account/{account_id}/backup/{backup_id}"
RESTORE_ENDPOINT = "/api/v1/account/{account_id}/backup/{backup_id}/restore"


class KnowledgeBoxCreated(BaseModel):
    id: str


class NucliaBackup:
    @property
    def _auth(self) -> NucliaAuth:
        auth = get_auth()
        return auth

    @account
    @zone
    def list(
        self, account_id: Optional[str] = None, zone: Optional[str] = None, **kwargs
    ) -> list[BackupResponse]:
        if not zone:
            raise ValueError("zone is required")
        if not account_id:
            raise ValueError("account_id is required")

        path = get_regional_url(zone, BACKUPS_ENDPOINT.format(account_id=account_id))
        data = self._auth._request("GET", path)

        ta = TypeAdapter(list[BackupResponse])
        return ta.validate_python(data)

    @accounts
    @account
    @zone
    def create(
        self,
        backup: Union[dict, BackupCreate],
        account_id: Optional[str] = None,
        zone: Optional[str] = None,
        **kwargs,
    ) -> BackupCreateResponse:
        if not zone:
            raise ValueError("zone is required")
        if not account_id:
            raise ValueError("account_id is required")

        body: BackupCreate
        if isinstance(backup, dict):
            body = BackupCreate.model_validate(backup)
        else:
            body = backup

        path = get_regional_url(zone, BACKUPS_ENDPOINT.format(account_id=account_id))
        data = self._auth._request(
            "POST", path, body.model_dump(mode="json", exclude_unset=True)
        )
        return BackupCreateResponse.model_validate(data)

    @accounts
    @account
    @zone
    def delete(
        self,
        id: Union[str, UUID],
        account_id: Optional[str] = None,
        zone: Optional[str] = None,
        **kwargs,
    ):
        if not zone:
            raise ValueError("zone is required")
        if not account_id:
            raise ValueError("account_id is required")

        path = get_regional_url(
            zone, BACKUP_ENDPOINT.format(account_id=account_id, backup_id=str(id))
        )
        self._auth._request("DELETE", path)

    @accounts
    @account
    @zone
    def restore(
        self,
        restore: BackupRestore,
        backup_id: Union[str, UUID],
        account_id: Optional[str] = None,
        zone: Optional[str] = None,
        **kwargs,
    ) -> KnowledgeBoxCreated:
        if not zone:
            raise ValueError("zone is required")
        if not account_id:
            raise ValueError("account_id is required")

        body: BackupRestore
        if isinstance(restore, dict):
            body = BackupRestore.model_validate(restore)
        else:
            body = restore

        path = get_regional_url(
            zone,
            RESTORE_ENDPOINT.format(account_id=account_id, backup_id=str(backup_id)),
        )
        data = self._auth._request(
            "POST", path, body.model_dump(mode="json", exclude_unset=True)
        )
        return KnowledgeBoxCreated.model_validate(data)


class AsyncNucliaBackup:
    @property
    def _auth(self) -> AsyncNucliaAuth:
        auth = get_async_auth()
        return auth

    @account
    @zone
    async def list(
        self, account_id: Optional[str] = None, zone: Optional[str] = None, **kwargs
    ) -> list[BackupResponse]:
        if not zone:
            raise ValueError("zone is required")
        if not account_id:
            raise ValueError("account_id is required")

        path = get_regional_url(zone, BACKUPS_ENDPOINT.format(account_id=account_id))
        data = await self._auth._request("GET", path)

        ta = TypeAdapter(list[BackupResponse])
        return ta.validate_python(data)

    @accounts
    @account
    @zone
    async def create(
        self,
        backup: Union[dict, BackupCreate],
        account_id: Optional[str] = None,
        zone: Optional[str] = None,
        **kwargs,
    ) -> BackupCreateResponse:
        if not zone:
            raise ValueError("zone is required")
        if not account_id:
            raise ValueError("account_id is required")

        body: BackupCreate
        if isinstance(backup, dict):
            body = BackupCreate.model_validate(backup)
        else:
            body = backup

        path = get_regional_url(zone, BACKUPS_ENDPOINT.format(account_id=account_id))
        data = await self._auth._request(
            "POST", path, body.model_dump(mode="json", exclude_unset=True)
        )
        return BackupCreateResponse.model_validate(data)

    @accounts
    @account
    @zone
    async def delete(
        self,
        id: Union[str, UUID],
        account_id: Optional[str] = None,
        zone: Optional[str] = None,
        **kwargs,
    ):
        if not zone:
            raise ValueError("zone is required")
        if not account_id:
            raise ValueError("account_id is required")

        path = get_regional_url(
            zone, BACKUP_ENDPOINT.format(account_id=account_id, backup_id=str(id))
        )
        await self._auth._request("DELETE", path)

    @accounts
    @account
    @zone
    async def restore(
        self,
        restore: BackupRestore,
        backup_id: Union[str, UUID],
        account_id: Optional[str] = None,
        zone: Optional[str] = None,
        **kwargs,
    ) -> KnowledgeBoxCreated:
        if not zone:
            raise ValueError("zone is required")
        if not account_id:
            raise ValueError("account_id is required")

        body: BackupRestore
        if isinstance(restore, dict):
            body = BackupRestore.model_validate(restore)
        else:
            body = restore

        path = get_regional_url(
            zone,
            RESTORE_ENDPOINT.format(account_id=account_id, backup_id=str(backup_id)),
        )
        data = await self._auth._request(
            "POST", path, body.model_dump(mode="json", exclude_unset=True)
        )
        return KnowledgeBoxCreated.model_validate(data)
