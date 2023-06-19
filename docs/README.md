# Nuclia CLI/SDK

This SDK/CLI is designed to provide an easy use cased focus experience with Nuclia API.

There are two developer experiences:

- CLI: by using the cli `nuclia` you can interact with Nuclia via command line
- SDK: Using python you can replicate each command using the same structure

## Nuclia Management/Authentication API

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

  - CLI: `nuclia auth nua APIKEY`
  - SDK:

    ```python
    from nuclia import sdk
    sdk.NucliaAuth().set_user_token(USER_TOKEN)
    ```

  - Provides:
    - Access to Nuclia Understanding API (extract, predict & train)

- NucliaDB API
  - `nuclia auth kb KB_URL [TOKEN]`
  - Provides access to NucliaDB API. For the managed service you will need a service token.

## Manage Knowledge Boxes



Authenticating your client against the NucliaDB API will ask to make the KnowledgeBox as the default one.

## Use Cases

- [Upload files](UPLOAD.md)
- Upload urls
- [Upload conversation](CONVERSATION.md)
- Extract information from a file
- Detect Entities
- Get embedding from text
- Get answer from a context
