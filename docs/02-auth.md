# Authentication

In order to start working you can login either using a user acount, or using an API key.

Note: you can also login with a NUA key if you only need to run some processing, see [NUA](07-nua.md).

## User authentication

With user authentication, there is no limitation to the API endpoints you can use. You manage all the accounts and Knowledge Boxes you have access to. It also allows to manage local NucliaDBs connected to your accounts.

But it does not last very long (30 minutes), and it requires a browser to complete the authentication process.
It is a good fit for interactive use, but not for long running scripts.

- CLI: `nuclia auth login`, and it will trigger a browser authentication flow, so you can copy/paste the token in your terminal.

- SDK: (even if it is not recommended for long running scripts, user authentication can be done in the SDK)

  ```python
  from nuclia import sdk
  sdk.NucliaAuth().set_user_token(USER_TOKEN)
  ```

## Personal access token

A personal access token is a long-lived user token that can be used to authenticate to the API. It is a good fit for long running scripts. It grants the same access as user authentication.

You define its expiration date (default is 90 days), and you can revoke it at any time.

- CLI:

  To generate a token, run:

  ```sh
  nuclia auth create_personal_token --description="My token" --days=30
  ```

  To generate a token and use it as authentication in the CLI, run:

  ```sh
  nuclia auth create_personal_token --description="My token" --days=30 --login
  ```

  To list the tokens, run:

  ```sh
  nuclia auth list_personal_tokens
  ```

  To delete a token, run:

  ```sh
  nuclia auth delete_personal_token [TOKEN_ID]
  ```

- SDK:

  ```python
  from nuclia import sdk
  sdk.NucliaAuth().create_personal_token(description="My token", days=30)
  sdk.NucliaAuth().list_personal_tokens()
  sdk.NucliaAuth().delete_personal_token(token_id=TOKEN_ID)
  ```

## API key

An API key can be generated from the Nuclia Dashboard, see [Get an API key](https://docs.nuclia.dev/docs/guides/getting-started/quick-start/push#get-an-api-key).

When authenticating with an API key, you can only access the Knowledge Box that is associated with this API key.
The authentication will last as long as the key is valid (potentially forever, but an API key can be revoked from the Nuclia Dashboard).

It is the recommended way to authenticate for long running scripts.

- CLI: `nuclia auth kb [KB_URL] [API_KEY]`
- SDK:

  ```python
  from nuclia import sdk
  sdk.NucliaAuth().kb(url=KB_URL, token=API_KEY)
  ```

- Provides access to NucliaDB API. For the managed service you will need a service token.

## Logout

```sh
nuclia auth logout
```

## List configured user accounts, knowledge boxes and NUA keys

You can list the configured authentication mechanisms using:

```bash
nuclia auth show
```
