# Authentication

In order to start working you can login using multiple mechanism:

- User auth:

  - CLI: `nuclia auth login`
  - SDK:

    ```python
    from nuclia import sdk
    sdk.NucliaAuth().set_user_token(USER_TOKEN)
    ```

  - Provides:
    - CRUD experience on top of accounts and knowledgeboxes
    - Access to managed NucliaDBs connected to your accounts

- Nuclia Understanding API

  - CLI: `nuclia auth nua region=REGION token=NUA_KEY`
  - SDK:

    ```python
    from nuclia import sdk
    sdk.NucliaAuth().nua(region=REGION, token=NUA_KEY)
    ```

  - Provides:
    - Access to Nuclia Understanding API (extract, predict & train)

- NucliaDB API (Knowledge Box)

  - CLI: `nuclia auth kb KB_URL [TOKEN]`
  - SDK:

    ```python
    from nuclia import sdk
    sdk.NucliaAuth().kb(url=KB_URL, token=API_KEY, interactive=False)
    ```

  - Provides access to NucliaDB API. For the managed service you will need a service token.

## List configured user accounts, knowledge boxes and NUA keys

You can list the configured authentication mechanisms using:

```bash
nuclia auth show
```
