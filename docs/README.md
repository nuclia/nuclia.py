# Nuclia CLI/SDK

This SDK/CLI is designed to provide an easy use cased focus experience with Nuclia API.

## Nuclia Management/Authentication API

In order to start working you can login using multiple mechanism:

- User auth:
  - `nuclia auth login`
  - Provides a CRUD experience on top of accounts and knowledgeboxes
  - Provides access to managed NucliaDBs connected to your accounts

- Nuclia Understanding API
  - `nuclia auth nua APIKEY`
  - Provides access to Nuclia Understanding API

- NucliaDB API
  - `nuclia auth kb KB_URL [TOKEN]`
  - Provides access to NucliaDB API. For the managed service you will need a service token.

## Manage Knowledge Boxes



Authenticating your client against the NucliaDB API will ask to make the KnowledgeBox as the default one.

## Use Cases

- Upload files
- Upload urls
- Upload conversation
- Extract information from a file
- Detect Entities
- Get embedding from text
- Get answer from a context
