import asyncio
import base64
import datetime
import json
import webbrowser
from time import time
from typing import Any, Dict, List, Optional, Tuple, Union

from httpx import AsyncClient, Client, ConnectError
from nucliadb_models.resource import KnowledgeBoxObj
from prompt_toolkit import prompt
from pydantic import TypeAdapter
from tabulate import tabulate

from nuclia import get_global_url, get_regional_url, is_nuclia_hosted
from nuclia.config import (
    Account,
    Config,
    EphemeralToken,
    KnowledgeBox,
    PersonalTokenCreate,
    PersonalTokenItem,
    RetrievalAgentOrchestrator,
    RetrievalAgentOrchestratorObj,
    User,
    Zone,
    retrieve_account,
    retrieve_nua,
)
from nuclia.exceptions import NeedUserToken, UserTokenExpired
from nuclia.lib.utils import build_httpx_async_client, build_httpx_client
from nuclia.sdk.logger import logger

USER = "/api/v1/user/welcome"
MEMBER = "/api/v1/user"
ACCOUNTS = "/api/v1/accounts"
ZONES = "/api/v1/zones"
LIST_KBS = "/api/v1/account/{account}/kbs"
LIST_AGENTS = "/api/v1/account/{account}/kbs?mode=agent_no_memory"
LIST_AGENTS_NO_MEM = "/api/v1/account/{account}/kbs?mode=agent"
VALIDATE_AGENT = "/api/v1/account/{account}/kb/{agent_id}"
VERIFY_NUA = "/api/authorizer/info"
PERSONAL_TOKENS = "/api/v1/user/pa_tokens"
PERSONAL_TOKEN = "/api/v1/user/pa_token/{token_id}"
SA_EPHEMERAL_TOKEN = "/api/v1/ephemeral_token"


class BaseNucliaAuth:
    _inner_config: Optional[Config] = None

    @property
    def _config(self) -> Config:
        if self._inner_config is None:
            from nuclia.data import get_config

            self._inner_config = get_config()
        return self._inner_config

    def get_account_id(self, account_slug: str) -> str:
        account_obj = retrieve_account(self._config.accounts or [], account_slug)
        if not account_obj:
            raise ValueError(f"Account {account_slug} not found")
        return account_obj.id

    def list_nuas(self):
        result = []
        result.extend(
            self._config.nuas_token if self._config.nuas_token is not None else []
        )
        return result

    def default_nua(self, nua: str):
        nuas = self._config.nuas_token if self._config.nuas_token is not None else []
        nua_obj = retrieve_nua(nuas, nua)

        if nua_obj is None:
            raise KeyError("NUA KEY not found")
        self._config.set_default_nua(nua_obj.client_id)
        self._config.save()

    def default_kb(self, kbid: str):
        self._config.set_default_kb(kbid=kbid)

    def unset_kb(self, kbid: str):
        self._config.unset_default_kb(kbid=kbid)


def print_config(config: Config):
    if config.default:
        if config.default.account:
            print(f"Default account:        {config.default.account}")
        if config.default.kbid:
            kb_obj = config.get_kb(config.default.kbid)
            print(f"Default KnowledgeBox:  {kb_obj}\n")
        if config.default.agent_id:
            agent_obj = config.get_agent(config.default.agent_id)
            print(f"Default Retrieval Agent Orchestrator:           {agent_obj}\n")


def print_nuas(config: Config):
    if config.default:
        if config.default.nua:
            nua = config.get_nua(config.default.nua)
            print(
                f"Default NUA KEY:        {nua.region} {nua.client_id} ({nua.account}) \n"
            )

    if len(config.nuas_token):
        print("NUA Keys Registered locally: \n")
        data = []
        for nua in config.nuas_token:
            data.append(
                [
                    nua.client_id,
                    nua.region,
                    nua.account,
                ]
            )
        print(
            tabulate(
                data,
                headers=[
                    "Client ID",
                    "Region",
                    "Account",
                ],
            )
        )
        print()


class NucliaAuth(BaseNucliaAuth):
    client: Client

    def __init__(self):
        self.client = build_httpx_client()

    def show(self) -> None:
        self._show_user()
        print_config(self._config)

        data_kbs = []
        data_agents = []
        for account in self.accounts():
            for kb in self.kbs(account.id):
                try:
                    kb_obj = self._config.get_kb(kb.id)
                except StopIteration:
                    kb_obj = None

                role: Optional[str] = ""
                if (
                    kb_obj is not None
                    and kb_obj.region is not None
                    and kb_obj.token is not None
                ):
                    permissions = self.client.get(
                        get_regional_url(kb_obj.region, "/api/authorizer/info"),
                        headers={"X-NUCLIA-SERVICEACCOUNT": f"Bearer {kb_obj.token}"},
                    )
                    if permissions.status_code == 200:
                        role = permissions.json().get("user", {}).get("role")
                        if role is not None:
                            role = role.lstrip("S")

                default = ""
                if (
                    self._config.default is not None
                    and self._config.default.kbid == kb.id
                ):
                    default = "*"

                data_kbs.append(
                    [
                        default,
                        account.slug,
                        kb.id,
                        kb.slug,
                        kb.title,
                        kb.region,
                        kb.url,
                        role,
                    ]
                )
            for agent in self.agents(account.id):
                try:
                    agent_obj = self._config.get_agent(agent.id)
                except StopIteration:
                    agent_obj = None

                arole: Optional[str] = ""
                if (
                    agent_obj is not None
                    and agent_obj.region is not None
                    and agent_obj.token is not None
                ):
                    permissions = self.client.get(
                        get_regional_url(agent_obj.region, "/api/authorizer/info"),
                        headers={
                            "X-NUCLIA-SERVICEACCOUNT": f"Bearer {agent_obj.token}"
                        },
                    )
                    if permissions.status_code == 200:
                        arole = permissions.json().get("user", {}).get("role")
                        if arole is not None:
                            arole = arole.lstrip("S")

                default = ""
                if (
                    self._config.default is not None
                    and self._config.default.agent_id == agent.id
                ):
                    default = "*"

                data_agents.append(
                    [
                        default,
                        account.slug,
                        agent.id,
                        agent.slug,
                        agent.title,
                        agent.region,
                        arole,
                    ]
                )

        print(
            tabulate(
                data_kbs,
                headers=[
                    "Default",
                    "Account ID",
                    "KnowledgeBox ID",
                    "KnowledgeBox slug",
                    "KnowledgeBox Title",
                    "KnowledgeBox Region",
                    "KnowledgeBox URL",
                    "Local Token Available",
                ],
            )
        )
        print()
        print(
            tabulate(
                data_agents,
                headers=[
                    "Default",
                    "Account ID",
                    "Retrieval Agent ID",
                    "Retrieval Agent slug",
                    "Retrieval Agent Title",
                    "Retrieval Agent Region",
                    "Retrieval Agent URL",
                    "Local Token Available",
                ],
            )
        )
        print()

    def nucliadb(self, url: str = "http://localhost:8080"):
        """
        Setup a local NucliaDB. Needs to be the base url of the NucliaDB server
        """
        resp = self.client.get(url)
        if resp.status_code != 200 or b"Nuclia" not in resp.content:
            raise Exception("Not a valid URL")
        self._config.set_default_nucliadb(nucliadb=url)

    def kb(self, url: str, token: Optional[str] = None) -> Optional[str]:
        url = url.strip("/")
        kb = self.validate_kb(url, token)
        if kb is not None:
            logger.info("Validated")
            self._config.set_kb_token(
                url=url,
                token=token,
                title=kb.config.title if kb.config is not None else "",
                kbid=kb.uuid,
            )
            self._config.set_default_kb(kbid=kb.uuid)
            return kb.uuid
        else:
            logger.error("Invalid service token")
            return None

    def agent(
        self, region: str, account_id: str, agent_id: str, token: Optional[str] = None
    ) -> Optional[str]:
        agent = self.validate_agent(
            account_id=account_id, agent_id=agent_id, region=region, token=token
        )
        # For now we validate kb to assess if the agent has memory or not
        memory = False
        kb_check = self.validate_kb(
            url=get_regional_url(region, f"/api/v1/kb/{agent_id}"), token=token
        )
        if kb_check is not None:
            memory = True
        if agent:
            logger.info("Validated")

            self._config.set_agent_token(
                region=region,
                agent_id=agent.id,
                memory=memory,
                account_id=account_id,
                token=token,
                title=agent.title,
            )
            self._config.set_default_agent(agent_id=agent.id)
            return agent.id
        else:
            logger.error("Invalid service token")
            return None

    def nua(self, token: str) -> Optional[str]:
        client_id, account_type, account, base_region = self.validate_nua(token)
        if account is not None and client_id is not None and base_region is not None:
            logger.info("Validated")
            self._config.set_nua_token(
                client_id=client_id,
                account_type=account_type,
                account=account,
                base_region=base_region,
                token=token,
            )
            self.default_nua(client_id)
            return client_id
        else:
            logger.error("Invalid NUA token")
            return None

    def nuas(self):
        print_nuas(self._config)

    def validate_nua(
        self, token: str
    ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        # Validate the code is ok
        token_payload = token.split(".")[1]
        token_payload_decoded = str(base64.b64decode(token_payload + "=="), "utf-8")
        payload = json.loads(token_payload_decoded)
        base_path = payload["iss"]
        url = base_path.strip("/") + VERIFY_NUA
        resp = self.client.get(
            url,
            headers={"x-nuclia-nuakey": f"Bearer {token}"},
        )
        if resp.status_code == 200:
            data = resp.json().get("user")
            return (
                data.get("user_id"),
                data.get("account_type"),
                data.get("account_id"),
                payload.get("iss"),
            )
        else:
            return None, None, None, None

    def get_account_from_service_token(
        self, region: str, token: str
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Extract account ID, KB/agent ID, and role from a service account token (API key).

        Args:
            region: The region where the KB/agent is located (e.g., 'europe-1')
            token: The service account token (API key)

        Returns:
            Tuple of (account_id, kb_id, role) or (None, None, None) if invalid
        """
        url = get_regional_url(region, "/api/authorizer/info")
        resp = self.client.get(
            url,
            headers={"x-nuclia-serviceaccount": f"Bearer {token}"},
        )
        if resp.status_code == 200:
            data = resp.json().get("user")
            if data:
                return (
                    data.get("account_id"),
                    data.get("kb_id"),
                    data.get("role"),
                )
        return None, None, None

    def validate_kb(
        self, url: str, token: Optional[str] = None
    ) -> Optional[KnowledgeBoxObj]:
        # Validate the code is ok
        data = None
        if token is None:
            if is_nuclia_hosted(url):
                # Use nuclia User Auth
                data = self._request("GET", url)
            else:
                # Validate OSS version
                resp = self.client.get(
                    url,
                    headers={"X-NucliaDB-ROLES": "READER"},
                )
                if resp.status_code == 200:
                    data = resp.json()
        else:
            # Validate Cloud version
            resp = self.client.get(
                url,
                headers={"X-Nuclia-Serviceaccount": f"Bearer {token}"},
            )
            if resp.status_code == 200:
                data = resp.json()
        if data is not None:
            return KnowledgeBoxObj.model_validate(data)
        else:
            return None

    def validate_agent(
        self, account_id: str, agent_id: str, region: str, token: Optional[str] = None
    ) -> Optional[RetrievalAgentOrchestratorObj]:
        url = VALIDATE_AGENT.format(account=account_id, agent_id=agent_id)
        resp = self.client.get(
            get_regional_url(region, url),
            headers={"X-Nuclia-Serviceaccount": f"Bearer {token}"},
        )
        if resp.status_code == 200:
            data = resp.json()
            return RetrievalAgentOrchestratorObj.model_validate(data)
        else:
            return None

    def get_user(self) -> User:
        resp = self._request("GET", get_global_url(MEMBER))
        assert resp
        return User.model_validate_json(resp.json)

    def _show_user(self):
        resp = None
        try:
            resp = self._request("GET", get_global_url(MEMBER))
        except NeedUserToken:
            print("No user logged in.")
        if resp:
            print()
            print(f"User: {resp.get('name')} <{resp.get('email')}>")
            print(f"Type: {resp.get('type')}")
            print()

    def login(self):
        """
        Lets redirect the user to the UI to capture a token
        """
        if self._validate_user_token():
            logger.info("Logged in!")
            self._show_user()
            return

        webbrowser.open(get_global_url("/redirect?display=token"))
        # we cannot use Python's `input` here because the copy/pasted token is too long
        code = prompt("Follow the browser flow and copy the token and paste it here:")
        print("Checking...")
        self.set_user_token(code)

    def logout(self):
        """
        Remove the current user token.
        """
        self._config.remove_user_token()

    def set_user_token(self, code: str):
        if self._validate_user_token(code):
            self._config.set_user_token(code)
            logger.info("Auth completed!")
            self.post_login()
        else:
            print("Invalid token auth not completed")

    def _extract_account(self, token: str) -> str:
        base64url = token.split(".")[1]
        data = json.loads(
            base64.urlsafe_b64decode(base64url + "=" * (4 - len(base64url) % 4))
        )
        return data.get("jti")

    def _validate_user_token(self, code: Optional[str] = None) -> bool:
        # Validate the code is ok
        if code is None:
            code = self._config.token
        resp = self.client.get(
            get_global_url(USER),
            headers={"Authorization": f"Bearer {code}"},
        )
        if resp.status_code == 200:
            return True
        else:
            return False

    def post_login(self):
        self.accounts()
        self.zones()

    def create_ephemeral_token(
        self, kbid: str, ttl: Optional[int] = None
    ) -> EphemeralToken:
        # Try to get as KB first, then as agent
        kb_obj: Union[RetrievalAgentOrchestrator, KnowledgeBox, None] = None
        try:
            kb_obj = self._config.get_kb(kbid)
        except (StopIteration, KeyError):
            try:
                kb_obj = self._config.get_agent(kbid)
            except (StopIteration, KeyError):
                pass

        if kb_obj is None:
            raise ValueError("KnowledgeBox or Agent not found")

        if kb_obj.region is None:
            raise ValueError("KnowledgeBox/Agent region not set")

        payload = {}
        if ttl is not None:
            payload["ttl"] = ttl
        resp = self.client.post(
            get_regional_url(kb_obj.region, SA_EPHEMERAL_TOKEN),
            headers={"X-NUCLIA-SERVICEACCOUNT": f"Bearer {kb_obj.token}"},
            json=payload,
        )
        return EphemeralToken(token=resp.json().get("token"))

    def create_personal_token(
        self, description: str, days: int = 90, login: bool = False
    ) -> PersonalTokenCreate:
        expiration_date = datetime.datetime.now() + datetime.timedelta(days=days)
        resp = self._request(
            "POST",
            get_global_url(PERSONAL_TOKENS),
            {
                "description": description,
                "expiration_date": expiration_date.isoformat(),
            },
        )
        token = PersonalTokenCreate.model_validate(resp)
        if login:
            self.set_user_token(token.token)
        return token

    def delete_personal_token(self, token_id: str) -> None:
        self._request(
            "DELETE", get_global_url(PERSONAL_TOKEN.format(token_id=token_id))
        )

    def list_personal_tokens(self) -> List[PersonalTokenItem]:
        resp = self._request("GET", get_global_url(PERSONAL_TOKENS))
        ta = TypeAdapter(List[PersonalTokenItem])
        return ta.validate_python(resp)

    def _request(
        self, method: str, path: str, data: Optional[Any] = None, remove_null=True
    ):
        if not self._config.token:
            raise NeedUserToken()
        kwargs: Dict[str, Any] = {
            "headers": {"Authorization": f"Bearer {self._config.token}"}
        }
        if data is not None:
            if remove_null:
                data = {k: v for k, v in data.items() if v is not None}
            kwargs["content"] = json.dumps(data)

        resp = self.client.request(
            method,
            path,
            **kwargs,
        )
        if resp.status_code == 204:
            return None
        elif resp.status_code >= 200 and resp.status_code < 300:
            return resp.json()
        elif resp.status_code >= 300 and resp.status_code < 400:
            return None
        elif resp.status_code == 403 or resp.status_code == 401:
            raise UserTokenExpired()
        else:
            raise Exception({"status": resp.status_code, "message": resp.text})

    def accounts(self) -> List[Account]:
        accounts = self._request("GET", get_global_url(ACCOUNTS))
        result: List[Account] = []
        self._config.accounts = []
        if accounts is None:
            return result
        for account in accounts:
            account_obj = Account.model_validate(account)
            result.append(account_obj)
            self._config.accounts.append(account_obj)
        self._config.save()
        return result

    def zones(self) -> List[Zone]:
        zones = self._request("GET", get_global_url(ZONES))
        if self._config.accounts is None:
            self._config.accounts = []
        self._config.zones = []
        result: List[Zone] = []
        if zones is None:
            return result
        for zone in zones:
            zone_obj = Zone.model_validate(zone)
            result.append(zone_obj)
            self._config.zones.append(zone_obj)
        self._config.save()
        return result

    def kbs(self, account: str) -> List[KnowledgeBox]:
        result: List[KnowledgeBox] = []
        zones = self.zones()
        for zoneObj in zones:
            zoneSlug = zoneObj.slug
            if not zoneSlug:
                continue
            path = get_regional_url(zoneSlug, LIST_KBS.format(account=account))
            try:
                kbs = self._request("GET", path)
            except UserTokenExpired:
                return []
            except ConnectError:
                logger.error(
                    f"Connection error to {get_regional_url(zoneSlug, '')}, skipping zone"
                )
                continue
            if kbs is not None:
                for kb in kbs:
                    url = get_regional_url(zoneSlug, f"/api/v1/kb/{kb['id']}")
                    kb_obj = KnowledgeBox(
                        url=url,
                        id=kb["id"],
                        slug=kb["slug"],
                        title=kb["title"],
                        account=account,
                        region=zoneSlug,
                    )
                    result.append(kb_obj)
        return result

    def agents(self, account: str) -> List[RetrievalAgentOrchestrator]:
        result: List[RetrievalAgentOrchestrator] = []
        zones = self.zones()
        for zoneObj in zones:
            zoneSlug = zoneObj.slug
            if not zoneSlug:
                continue
            for has_memory, url_template in (
                (True, LIST_AGENTS),
                (False, LIST_AGENTS_NO_MEM),
            ):
                path = get_regional_url(zoneSlug, url_template.format(account=account))
                try:
                    agents = self._request("GET", path)
                except UserTokenExpired:
                    return []
                except ConnectError:
                    logger.error(
                        f"Connection error to {get_regional_url(zoneSlug, '')}, skipping zone"
                    )
                    continue
                if agents is not None:
                    for agent in agents:
                        ra_obj = RetrievalAgentOrchestrator(
                            id=agent["id"],
                            account=account,
                            memory=has_memory,
                            title=agent["title"],
                            slug=agent["slug"],
                            region=zoneSlug,
                        )
                        result.append(ra_obj)
        return result


class AsyncNucliaAuth(BaseNucliaAuth):
    client: AsyncClient

    def __init__(self):
        self.client = build_httpx_async_client()
        self._cache = {}  # Manual cache storage
        self._lock = asyncio.Lock()

    async def show(self):
        await self._show_user()
        print_config(self._config)

    async def nucliadb(self, url: str = "http://localhost:8080"):
        """
        Setup a local NucliaDB. Needs to be the base url of the NucliaDB server
        """
        resp = await self.client.get(url)
        if resp.status_code != 200 or b"Nuclia" not in resp.content:
            raise Exception("Not a valid URL")
        self._config.set_default_nucliadb(nucliadb=url)

    async def kb(self, url: str, token: Optional[str] = None) -> Optional[str]:
        url = url.strip("/")
        kb = await self.validate_kb(url, token)
        if kb is not None:
            logger.info("Validated")
            self._config.set_kb_token(
                url=url,
                token=token,
                title=kb.config.title if kb.config is not None else "",
                kbid=kb.uuid,
            )
            self._config.set_default_kb(kbid=kb.uuid)
            return kb.uuid
        else:
            logger.error("Invalid service token")
            return None

    async def agent(
        self, region: str, account_id: str, agent_id: str, token: Optional[str] = None
    ) -> Optional[str]:
        agent = await self.validate_agent(
            account_id=account_id, agent_id=agent_id, region=region, token=token
        )
        # For now we validate kb to assess if the agent has memory or not
        memory = False
        kb_check = await self.validate_kb(
            url=get_regional_url(region, f"/api/v1/kb/{agent_id}"), token=token
        )
        if kb_check is not None:
            memory = True
        if agent:
            logger.info("Validated")

            self._config.set_agent_token(
                region=region,
                agent_id=agent.id,
                memory=memory,
                account_id=account_id,
                token=token,
                title=agent.title,
            )
            self._config.set_default_agent(agent_id=agent.id)
            return agent.id
        else:
            logger.error("Invalid service token")
            return None

    async def nua(self, token: str) -> Optional[str]:
        client_id, account_type, account, base_region = await self.validate_nua(token)
        if account is not None and client_id is not None and base_region is not None:
            logger.info("Validated")
            self._config.set_nua_token(
                client_id=client_id,
                account_type=account_type,
                account=account,
                base_region=base_region,
                token=token,
            )
            return client_id
        else:
            logger.error("Invalid NUA token")
            return None

    async def validate_nua(
        self, token: str
    ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        # Validate the code is ok
        token_payload = token.split(".")[1]
        token_payload_decoded = str(base64.b64decode(token_payload + "=="), "utf-8")
        payload = json.loads(token_payload_decoded)
        base_path = payload["iss"]
        url = base_path.strip("/") + VERIFY_NUA
        resp = await self.client.get(
            url,
            headers={"x-nuclia-nuakey": f"Bearer {token}"},
        )
        if resp.status_code == 200:
            data = resp.json().get("user")
            return (
                data.get("user_id"),
                data.get("account_type"),
                data.get("account_id"),
                payload.get("iss"),
            )
        else:
            return None, None, None, None

    async def get_account_from_service_token(
        self, region: str, token: str
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Extract account ID, KB/agent ID, and role from a service account token (API key).

        Args:
            region: The region where the KB/agent is located (e.g., 'europe-1')
            token: The service account token (API key)

        Returns:
            Tuple of (account_id, kb_id, role) or (None, None, None) if invalid
        """
        url = get_regional_url(region, "/api/authorizer/info")
        resp = await self.client.get(
            url,
            headers={"x-nuclia-serviceaccount": f"Bearer {token}"},
        )
        if resp.status_code == 200:
            data = resp.json().get("user")
            if data:
                return (
                    data.get("account_id"),
                    data.get("kb_id"),
                    data.get("role"),
                )
        return None, None, None

    async def validate_kb(
        self, url: str, token: Optional[str] = None
    ) -> Optional[KnowledgeBoxObj]:
        # Validate the code is ok
        data = None
        if token is None:
            if is_nuclia_hosted(url):
                # Use nuclia User Auth
                data = await self._request("GET", url)
            else:
                # Validate OSS version
                resp = await self.client.get(
                    url,
                    headers={"X-NucliaDB-ROLES": "READER"},
                )
                if resp.status_code == 200:
                    data = resp.json()
        else:
            # Validate Cloud version
            resp = await self.client.get(
                url,
                headers={"X-Nuclia-Serviceaccount": f"Bearer {token}"},
            )
            if resp.status_code == 200:
                data = resp.json()
        if data is not None:
            return KnowledgeBoxObj.model_validate(data)
        else:
            return None

    async def validate_agent(
        self, account_id: str, agent_id: str, region: str, token: Optional[str] = None
    ) -> Optional[RetrievalAgentOrchestratorObj]:
        url = VALIDATE_AGENT.format(account=account_id, agent_id=agent_id)
        resp = await self.client.get(
            get_regional_url(region, url),
            headers={"X-Nuclia-Serviceaccount": f"Bearer {token}"},
        )
        if resp.status_code == 200:
            data = resp.json()
            return RetrievalAgentOrchestratorObj.model_validate(data)
        else:
            return None

    async def _show_user(self):
        resp = await self._request("GET", get_global_url(MEMBER))
        assert resp
        print(f"User: {resp.get('name')} <{resp.get('email')}>")
        print(f"Type: {resp.get('type')}")

    async def login(self):
        """
        Lets redirect the user to the UI to capture a token
        """
        if await self._validate_user_token():
            logger.info("Logged in!")
            await self._show_user()
            return

        webbrowser.open(get_global_url("/redirect?display=token"))
        # we cannot use Python's `input` here because the copy/pasted token is too long
        code = prompt("Follow the browser flow and copy the token and paste it here:")
        logger.info("Checking...")
        await self.set_user_token(code)

    def logout(self):
        """
        Remove the current user token.
        """
        self._config.remove_user_token()

    async def set_user_token(self, code: str):
        if await self._validate_user_token(code):
            self._config.set_user_token(code)
            logger.info("Auth completed!")
            await self.post_login()
        else:
            logger.error("Invalid token auth not completed")

    def _extract_account(self, token: str) -> str:
        base64url = token.split(".")[1]
        data = json.loads(
            base64.urlsafe_b64decode(base64url + "=" * (4 - len(base64url) % 4))
        )
        return data.get("jti")

    async def _validate_user_token(self, code: Optional[str] = None) -> bool:
        # Validate the code is ok
        if code is None:
            code = self._config.token
        resp = await self.client.get(
            get_global_url(USER),
            headers={"Authorization": f"Bearer {code}"},
        )
        if resp.status_code == 200:
            return True
        else:
            return False

    async def post_login(self):
        await self.accounts()
        await self.zones()

    async def _cached_request(self, method: str, path: str) -> Any:
        async with self._lock:
            if path in self._cache:
                exp, value = self._cache[(path)]
                if time() <= exp:
                    return value  # Return cached response
            response = await self._request(method, path)
            self._cache[path] = (time() + 60, response)
            return response

    async def _request(
        self, method: str, path: str, data: Optional[Any] = None, remove_null=True
    ):
        if not self._config.token:
            raise NeedUserToken()
        kwargs: Dict[str, Any] = {
            "headers": {"Authorization": f"Bearer {self._config.token}"}
        }

        if data is not None:
            if remove_null:
                data = {k: v for k, v in data.items() if v is not None}
            kwargs["data"] = json.dumps(data)
        resp = await self.client.request(
            method,
            path,
            **kwargs,
        )
        if resp.status_code == 204:
            return None
        elif resp.status_code >= 200 and resp.status_code < 300:
            return resp.json()
        elif resp.status_code >= 300 and resp.status_code < 400:
            return None
        elif resp.status_code == 403 or resp.status_code == 401:
            raise UserTokenExpired()
        else:
            raise Exception({"status": resp.status_code, "message": resp.text})

    async def accounts(self, cached: bool = True) -> List[Account]:
        _request = self._cached_request if cached else self._request
        accounts = await _request("GET", get_global_url(ACCOUNTS))
        result: List[Account] = []
        self._config.accounts = []
        if accounts is None:
            return result
        for account in accounts:
            account_obj = Account.model_validate(account)
            result.append(account_obj)
            self._config.accounts.append(account_obj)
        self._config.save()
        return result

    async def zones(self, cached: bool = True) -> List[Zone]:
        _request = self._cached_request if cached else self._request
        zones = await _request("GET", get_global_url(ZONES))
        if self._config.accounts is None:
            self._config.accounts = []
        self._config.zones = []
        result: List[Zone] = []
        if zones is None:
            return result
        for zone in zones:
            zone_obj = Zone.model_validate(zone)
            result.append(zone_obj)
            self._config.zones.append(zone_obj)
        self._config.save()
        return result

    async def kbs(self, account: str, cached: bool = True) -> List[KnowledgeBox]:
        _request = self._cached_request if cached else self._request
        result: List[KnowledgeBox] = []
        zones = await self.zones()
        for zoneObj in zones:
            zoneSlug = zoneObj.slug
            if not zoneSlug:
                continue
            path = get_regional_url(zoneSlug, LIST_KBS.format(account=account))
            try:
                kbs = await _request("GET", path)
            except UserTokenExpired:
                return result
            except ConnectError:
                logger.error(
                    f"Connection error to {get_regional_url(zoneSlug, '')}, skipping zone"
                )
                continue
            if kbs is not None:
                for kb in kbs:
                    url = get_regional_url(zoneSlug, f"/api/v1/kb/{kb['id']}")
                    kb_obj = KnowledgeBox(
                        url=url,
                        id=kb["id"],
                        slug=kb["slug"],
                        title=kb["title"],
                        account=account,
                        region=zoneSlug,
                    )
                    result.append(kb_obj)
        return result

    async def create_ephemeral_token(
        self, kbid: str, ttl: Optional[int] = None
    ) -> EphemeralToken:
        # Try to get as KB first, then as agent
        kb_obj: Union[RetrievalAgentOrchestrator, KnowledgeBox, None] = None
        try:
            kb_obj = self._config.get_kb(kbid)
        except (StopIteration, KeyError):
            try:
                kb_obj = self._config.get_agent(kbid)
            except (StopIteration, KeyError):
                pass

        if kb_obj is None:
            raise ValueError("KnowledgeBox or Agent not found")

        if kb_obj.region is None:
            raise ValueError("KnowledgeBox/Agent region not set")

        payload = {}
        if ttl is not None:
            payload["ttl"] = ttl
        resp = await self.client.post(
            get_regional_url(kb_obj.region, SA_EPHEMERAL_TOKEN),
            headers={"X-NUCLIA-SERVICEACCOUNT": f"Bearer {kb_obj.token}"},
            json=payload,
        )
        return EphemeralToken(token=resp.json().get("token"))

    async def agents(
        self, account: str, cached: bool = True
    ) -> List[RetrievalAgentOrchestrator]:
        _request = self._cached_request if cached else self._request
        result: List[RetrievalAgentOrchestrator] = []
        zones = await self.zones()
        for zoneObj in zones:
            zoneSlug = zoneObj.slug
            if not zoneSlug:
                continue
            for has_memory, url_template in (
                (True, LIST_AGENTS),
                (False, LIST_AGENTS_NO_MEM),
            ):
                path = get_regional_url(zoneSlug, url_template.format(account=account))
                try:
                    agents = await _request("GET", path)
                except UserTokenExpired:
                    return []
                except ConnectError:
                    logger.error(
                        f"Connection error to {get_regional_url(zoneSlug, '')}, skipping zone"
                    )
                    continue
                if agents is not None:
                    for agent in agents:
                        ra_obj = RetrievalAgentOrchestrator(
                            id=agent["id"],
                            account=account,
                            memory=has_memory,
                            title=agent["title"],
                            slug=agent["slug"],
                            region=zoneSlug,
                        )
                        result.append(ra_obj)
        return result
