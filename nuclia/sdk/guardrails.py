from typing import Optional, Union
from uuid import UUID

from pydantic import TypeAdapter

from nuclia import get_regional_url
from nuclia.data import get_async_auth, get_auth
from nuclia.decorators import account, zone
from nuclia.lib.guardrails import (
    CreateGuardrailPolicy,
    GuardrailPolicy,
    PatchGuardrailPolicy,
)
from nuclia.sdk.auth import AsyncNucliaAuth, NucliaAuth

GUARDRAIL_POLICIES_ENDPOINT = "/api/v1/account/{account_id}/guardrail_policies"
GUARDRAIL_POLICY_ENDPOINT = (
    "/api/v1/account/{account_id}/guardrail_policies/{policy_id}"
)


def _guardrail_policy_url(
    auth: Union[NucliaAuth, AsyncNucliaAuth],
    account_id: str,
    zone_name: str,
    policy_id: Optional[Union[str, UUID]] = None,
) -> str:
    zone_region, zone_origin = auth.resolve_zone_endpoint(zone_name)
    endpoint = (
        GUARDRAIL_POLICY_ENDPOINT.format(
            account_id=account_id,
            policy_id=str(policy_id),
        )
        if policy_id is not None
        else GUARDRAIL_POLICIES_ENDPOINT.format(account_id=account_id)
    )
    return get_regional_url(zone_region, endpoint, origin_url=zone_origin)


class NucliaGuardrails:
    @property
    def _auth(self) -> NucliaAuth:
        return get_auth()

    @account
    @zone
    def create(
        self,
        policy: Union[dict, CreateGuardrailPolicy],
        account_id: Optional[str] = None,
        zone: Optional[str] = None,
        **kwargs,
    ) -> GuardrailPolicy:
        if not account_id:
            raise ValueError("account_id is required")
        if not zone:
            raise ValueError("zone is required")
        body = CreateGuardrailPolicy.model_validate(policy)
        data = self._auth._request(
            "POST",
            _guardrail_policy_url(self._auth, account_id, zone),
            body.model_dump(mode="json"),
        )
        return GuardrailPolicy.model_validate(data)

    @account
    @zone
    def list(
        self,
        account_id: Optional[str] = None,
        zone: Optional[str] = None,
        **kwargs,
    ) -> list[GuardrailPolicy]:
        if not account_id:
            raise ValueError("account_id is required")
        if not zone:
            raise ValueError("zone is required")
        data = self._auth._request(
            "GET",
            _guardrail_policy_url(self._auth, account_id, zone),
        )
        return TypeAdapter(list[GuardrailPolicy]).validate_python(data)

    @account
    @zone
    def get(
        self,
        policy_id: Union[str, UUID],
        account_id: Optional[str] = None,
        zone: Optional[str] = None,
        **kwargs,
    ) -> GuardrailPolicy:
        if not account_id:
            raise ValueError("account_id is required")
        if not zone:
            raise ValueError("zone is required")
        data = self._auth._request(
            "GET",
            _guardrail_policy_url(self._auth, account_id, zone, policy_id),
        )
        return GuardrailPolicy.model_validate(data)

    @account
    @zone
    def update(
        self,
        policy_id: Union[str, UUID],
        policy: Union[dict, PatchGuardrailPolicy],
        account_id: Optional[str] = None,
        zone: Optional[str] = None,
        **kwargs,
    ) -> GuardrailPolicy:
        if not account_id:
            raise ValueError("account_id is required")
        if not zone:
            raise ValueError("zone is required")
        body = PatchGuardrailPolicy.model_validate(policy)
        data = self._auth._request(
            "PATCH",
            _guardrail_policy_url(self._auth, account_id, zone, policy_id),
            body.model_dump(mode="json", exclude_unset=True),
            remove_null=False,
        )
        return GuardrailPolicy.model_validate(data)

    @account
    @zone
    def delete(
        self,
        policy_id: Union[str, UUID],
        account_id: Optional[str] = None,
        zone: Optional[str] = None,
        **kwargs,
    ) -> None:
        if not account_id:
            raise ValueError("account_id is required")
        if not zone:
            raise ValueError("zone is required")
        self._auth._request(
            "DELETE",
            _guardrail_policy_url(self._auth, account_id, zone, policy_id),
        )


class AsyncNucliaGuardrails:
    @property
    def _auth(self) -> AsyncNucliaAuth:
        return get_async_auth()

    @account
    @zone
    async def create(
        self,
        policy: Union[dict, CreateGuardrailPolicy],
        account_id: Optional[str] = None,
        zone: Optional[str] = None,
        **kwargs,
    ) -> GuardrailPolicy:
        if not account_id:
            raise ValueError("account_id is required")
        if not zone:
            raise ValueError("zone is required")
        body = CreateGuardrailPolicy.model_validate(policy)
        data = await self._auth._request(
            "POST",
            _guardrail_policy_url(self._auth, account_id, zone),
            body.model_dump(mode="json"),
        )
        return GuardrailPolicy.model_validate(data)

    @account
    @zone
    async def list(
        self,
        account_id: Optional[str] = None,
        zone: Optional[str] = None,
        **kwargs,
    ) -> list[GuardrailPolicy]:
        if not account_id:
            raise ValueError("account_id is required")
        if not zone:
            raise ValueError("zone is required")
        data = await self._auth._request(
            "GET",
            _guardrail_policy_url(self._auth, account_id, zone),
        )
        return TypeAdapter(list[GuardrailPolicy]).validate_python(data)

    @account
    @zone
    async def get(
        self,
        policy_id: Union[str, UUID],
        account_id: Optional[str] = None,
        zone: Optional[str] = None,
        **kwargs,
    ) -> GuardrailPolicy:
        if not account_id:
            raise ValueError("account_id is required")
        if not zone:
            raise ValueError("zone is required")
        data = await self._auth._request(
            "GET",
            _guardrail_policy_url(self._auth, account_id, zone, policy_id),
        )
        return GuardrailPolicy.model_validate(data)

    @account
    @zone
    async def update(
        self,
        policy_id: Union[str, UUID],
        policy: Union[dict, PatchGuardrailPolicy],
        account_id: Optional[str] = None,
        zone: Optional[str] = None,
        **kwargs,
    ) -> GuardrailPolicy:
        if not account_id:
            raise ValueError("account_id is required")
        if not zone:
            raise ValueError("zone is required")
        body = PatchGuardrailPolicy.model_validate(policy)
        data = await self._auth._request(
            "PATCH",
            _guardrail_policy_url(self._auth, account_id, zone, policy_id),
            body.model_dump(mode="json", exclude_unset=True),
            remove_null=False,
        )
        return GuardrailPolicy.model_validate(data)

    @account
    @zone
    async def delete(
        self,
        policy_id: Union[str, UUID],
        account_id: Optional[str] = None,
        zone: Optional[str] = None,
        **kwargs,
    ) -> None:
        if not account_id:
            raise ValueError("account_id is required")
        if not zone:
            raise ValueError("zone is required")
        await self._auth._request(
            "DELETE",
            _guardrail_policy_url(self._auth, account_id, zone, policy_id),
        )
