from typing import Optional

from nuclia import get_regional_url
from nuclia.config import retrieve, retrieve_account
from nuclia.data import get_async_auth, get_auth
from nuclia.decorators import account, accounts, zone
from nuclia.sdk.auth import AsyncNucliaAuth, NucliaAuth

AGENTS_ENDPOINT = "/api/v1/account/{account}/kbs?mode=agent"
AGENT_ENDPOINT = "/api/v1/account/{account}/kb/{agent}"


class NucliaAgents:
    @property
    def _auth(self) -> NucliaAuth:
        auth = get_auth()
        return auth

    @accounts
    def list(self, account: Optional[str] = None):
        if account is None:
            result = []
            accounts = (
                self._auth._config.accounts
                if self._auth._config.accounts is not None
                else []
            )
            for account_obj in accounts:
                if account_obj.slug is not None:
                    result.extend(self._auth.agents(account_obj.id))
            self._auth._config.agents = result
            self._auth._config.save()

            # List the Knowledge Boxes configured as Service Token
            result.extend(
                self._auth._config.agents_token
                if self._auth._config.agents_token is not None
                else []
            )
            return result
        else:
            matching_account = retrieve_account(
                self._auth._config.accounts or [], account
            )
            if not matching_account:
                raise ValueError("Account not found")
            return self._auth.agents(matching_account.id)

    @accounts
    @account
    @zone
    def get(
        self,
        slug: Optional[str] = None,
        id: Optional[str] = None,
        **kwargs,
    ):
        zone = kwargs.get("zone")
        if not zone:
            raise ValueError("zone is required")
        if not id and not slug:
            raise ValueError("id or slug is required")
        if slug and not id:
            agents = self._auth.agents(kwargs["account_id"])
            agent_obj = retrieve(agents, slug)
            if not agent_obj:
                raise ValueError("Retrieval Agent not found")
            id = agent_obj.id
        path = get_regional_url(
            zone, AGENT_ENDPOINT.format(account=kwargs["account_id"], agent=id)
        )
        return self._auth._request("GET", path)

    def default(self, agent: str):
        agents = (
            self._auth._config.agents if self._auth._config.agents is not None else []
        )
        agent_obj = retrieve(agents, agent)
        if agent_obj is None:
            agents = (
                self._auth._config.agents_token
                if self._auth._config.agents_token is not None
                else []
            )
            agent_obj = retrieve(agents, agent)

        if agent_obj is None:
            raise KeyError("Retrieval Agent not found")
        self._auth._config.set_default_agent(agent_obj.id)
        self._auth._config.save()


class AsyncNucliaAgents:
    @property
    def _auth(self) -> AsyncNucliaAuth:
        auth = get_async_auth()
        return auth

    @accounts
    async def list(self, account: Optional[str] = None):
        if account is None:
            result = []
            accounts = (
                self._auth._config.accounts
                if self._auth._config.accounts is not None
                else []
            )
            for account_obj in accounts:
                if account_obj.slug is not None:
                    result.extend(await self._auth.agents(account_obj.id))
            self._auth._config.agents = result
            self._auth._config.save()

            # List the Knowledge Boxes configured as Service Token
            result.extend(
                self._auth._config.agents_token
                if self._auth._config.agents_token is not None
                else []
            )
            return result
        else:
            matching_account = retrieve_account(
                self._auth._config.accounts or [], account
            )
            if not matching_account:
                raise ValueError("Account not found")
            return await self._auth.agents(matching_account.id)

    @accounts
    @account
    @zone
    async def get(
        self,
        slug: Optional[str] = None,
        id: Optional[str] = None,
        **kwargs,
    ):
        zone = kwargs.get("zone")
        if not zone:
            raise ValueError("zone is required")
        if not id and not slug:
            raise ValueError("id or slug is required")
        if slug and not id:
            agents = await self._auth.agents(kwargs["account_id"])
            agent_obj = retrieve(agents, slug)
            if not agent_obj:
                raise ValueError("Retrieval Agent not found")
            id = agent_obj.id
        path = get_regional_url(
            zone, AGENT_ENDPOINT.format(account=kwargs["account_id"], agent=id)
        )
        return await self._auth._request("GET", path)

    def default(self, agent: str):
        agents = (
            self._auth._config.agents if self._auth._config.agents is not None else []
        )
        agent_obj = retrieve(agents, agent)
        if agent_obj is None:
            agents = (
                self._auth._config.agents_token
                if self._auth._config.agents_token is not None
                else []
            )
            agent_obj = retrieve(agents, agent)

        if agent_obj is None:
            raise KeyError("Retrieval Agent not found")
        self._auth._config.set_default_agent(agent_obj.id)
        self._auth._config.save()
