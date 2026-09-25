from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, call
from uuid import UUID

import pytest
from nuclia_models.accounts.guardrails import (
    CreateGuardrailPolicy,
    PatchGuardrailPolicy,
)

from nuclia import get_regional_url
from nuclia.sdk.guardrails import AsyncNucliaGuardrails, NucliaGuardrails

ACCOUNT_ID = "11111111-1111-1111-1111-111111111111"
POLICY_ID = UUID("22222222-2222-2222-2222-222222222222")
ZONE = "europe-1"
POLICIES_URL = get_regional_url(
    ZONE,
    f"/api/v1/account/{ACCOUNT_ID}/guardrail_policies",
)
POLICY_URL = f"{POLICIES_URL}/{POLICY_ID}"


def policy_response(**overrides):
    now = datetime.now(timezone.utc).isoformat()
    response = {
        "id": str(POLICY_ID),
        "account_id": ACCOUNT_ID,
        "name": "Safety",
        "description": "Block unsafe requests",
        "instruction": "Flag unsafe content.",
        "query": "Is this unsafe?",
        "target": "QUERY",
        "enabled": True,
        "blocking": True,
        "created_at": now,
        "updated_at": now,
    }
    response.update(overrides)
    return response


def test_guardrail_policy_crud(monkeypatch):
    auth = Mock()
    auth.accounts = Mock()
    auth.resolve_zone_endpoint.return_value = (ZONE, None)
    auth._request.side_effect = [
        policy_response(),
        [policy_response()],
        policy_response(),
        policy_response(description=None),
        None,
    ]
    monkeypatch.setattr("nuclia.sdk.guardrails.get_auth", lambda: auth)
    monkeypatch.setattr("nuclia.decorators.get_auth", lambda: auth)

    guardrails = NucliaGuardrails()
    created = guardrails.create(
        CreateGuardrailPolicy(
            name="Safety",
            description="Block unsafe requests",
            instruction="Flag unsafe content.",
            query="Is this unsafe?",
            enabled=True,
        ),
        account_id=ACCOUNT_ID,
        zone=ZONE,
    )
    policies = guardrails.list(account_id=ACCOUNT_ID, zone=ZONE)
    fetched = guardrails.get(POLICY_ID, account_id=ACCOUNT_ID, zone=ZONE)
    updated = guardrails.update(
        POLICY_ID,
        PatchGuardrailPolicy(description=None),
        account_id=ACCOUNT_ID,
        zone=ZONE,
    )
    guardrails.delete(POLICY_ID, account_id=ACCOUNT_ID, zone=ZONE)

    assert created.id == POLICY_ID
    assert policies[0].id == POLICY_ID
    assert fetched.id == POLICY_ID
    assert updated.description is None
    assert auth.accounts.call_count == 5
    assert auth._request.call_args_list == [
        call(
            "POST",
            POLICIES_URL,
            {
                "name": "Safety",
                "description": "Block unsafe requests",
                "instruction": "Flag unsafe content.",
                "query": "Is this unsafe?",
                "target": "QUERY",
                "enabled": True,
                "blocking": True,
            },
        ),
        call("GET", POLICIES_URL),
        call("GET", POLICY_URL),
        call(
            "PATCH",
            POLICY_URL,
            {"description": None},
            remove_null=False,
        ),
        call("DELETE", POLICY_URL),
    ]


@pytest.mark.asyncio
async def test_async_guardrail_policy_crud(monkeypatch):
    auth = Mock()
    auth.accounts = AsyncMock()
    auth.resolve_zone_endpoint.return_value = (ZONE, None)
    auth._request = AsyncMock(
        side_effect=[
            policy_response(),
            [policy_response()],
            policy_response(),
            policy_response(enabled=False),
            None,
        ]
    )
    monkeypatch.setattr("nuclia.sdk.guardrails.get_async_auth", lambda: auth)
    monkeypatch.setattr("nuclia.decorators.get_async_auth", lambda: auth)

    guardrails = AsyncNucliaGuardrails()
    await guardrails.create(
        {
            "name": "Safety",
            "instruction": "Flag unsafe content.",
            "query": "Is this unsafe?",
        },
        account_id=ACCOUNT_ID,
        zone=ZONE,
    )
    policies = await guardrails.list(account_id=ACCOUNT_ID, zone=ZONE)
    await guardrails.get(POLICY_ID, account_id=ACCOUNT_ID, zone=ZONE)
    updated = await guardrails.update(
        POLICY_ID,
        {"enabled": False},
        account_id=ACCOUNT_ID,
        zone=ZONE,
    )
    await guardrails.delete(POLICY_ID, account_id=ACCOUNT_ID, zone=ZONE)

    assert policies[0].id == POLICY_ID
    assert updated.enabled is False
    assert auth.accounts.await_count == 5
    assert auth._request.await_args_list[-2:] == [
        call(
            "PATCH",
            POLICY_URL,
            {"enabled": False},
            remove_null=False,
        ),
        call("DELETE", POLICY_URL),
    ]
