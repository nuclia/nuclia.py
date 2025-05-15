# Changelog


## 4.8.9 (2025-05-15)


- Better http error handling


## 4.8.8 (2025-05-14)


- Fix `nuclia version`
- Fix for Tool validation in ChatModel
- Fix streaming trying to validate error payload as GenerativeChunk

## 4.8.7 (2025-05-13)


- Tools output on response


## 4.8.6 (2025-05-13)


- ChatModel response


## 4.8.5 (2025-05-06)


- Make nucliadb_protos dependency optional


## 4.8.4 (2025-04-25)


- Fix typing


## 4.8.3 (2025-04-24)


- Do not use enum for the region value


## 4.8.2 (2025-04-22)


- Accept full URLs for TUS upload
- Include custom User-Agent in requests


## 4.8.1 (2025-03-25)


- Fix: use asyncio.sleep on async methods


## 4.8.0 (2025-03-13)


- Add knowledgebox backup


## 4.7.0 (2025-03-11)


- Support for custom graph.


## 4.6.4 (2025-03-04)


- Bump nuclia-models dependency


## 4.6.3 (2025-02-24)


- Fix `add_labels` so it does not create new labelsets without kind.


## 4.6.2 (2025-02-21)


- Bump nuclia-models dependency


## 4.6.1 (2025-02-20)


- Bump nuclia-models dependency


## 4.6.0 (2025-02-20)


- Rename `add_labelset` to `set_labelset`
- Support `/catalog` endpoint
- Allow to add a list of labels to a labelset

## 4.5.2 (2025-02-17)


- Cache auth info related requests .


## 4.5.1 (2025-02-14)


- Bump nuclia-models dependency.
- Complete async versions of several sdk modules


## 4.5.0 (2025-01-30)


- Add AI agents documentation
- Support Personal Access Tokens


## 4.4.9 (2025-01-29)


- Keep ChatModel up to date
- Fix nuclia nua chat format error


## 4.4.8 (2025-01-28)


- Fix issue with 64 bit timestamp expirations on windows


## 4.4.7 (2025-01-22)


- Add NUA chat for CrewAI agents


## 4.4.6 (2025-01-22)


- Add support for extract strategy on file uploads, link and text fields.


## 4.4.5 (2025-01-16)


- Fix blocking code on upload and wait routine


## 4.4.4 (2025-01-10)


- Missing dependencies


## 4.4.3 (2025-01-08)

- Add documentation about the `send_to_process` method.
- Fix dependencies

## 4.4.2 (2024-12-20)

- Fix auth validation with async client.
- Allow overwriting client in nua decorator

## 4.4.1 (2024-12-19)

- Adds nuclia tokens

## 4.4.0 (2024-12-18)

- Feature: Add NUA REMi endpoints

## 4.3.11 (2024-12-18)


- Fix async nua `set_config`


## 4.3.10 (2024-12-17)


- Add `del_config` async version
- Fix async `rephrase`


## 4.3.9 (2024-12-11)


- Debug on ask and send to process


## 4.3.8 (2024-12-09)


- Support blanklineSplitter


## 4.3.7 (2024-12-02)


- Allow to pass the mimetype when uploading a file.


## 4.3.6 (2024-12-02)


- Fix dependencies regarding RRF


## 4.3.5 (2024-11-29)


- Allow activity downloads to be filtered by id.


## 4.3.4 (2024-11-29)


- Return prequeries results


## 4.3.3 (2024-11-28)


- Relax dependencies
- Fix paths in Windows
- Support Task Manager API


## 4.3.2 (2024-11-19)


- Fix pagination activity logs


## 4.3.1 (2024-11-13)


- Fix: allow passing context as `ContextItem` in rephrase


## 4.3.0 (2024-11-12)


- Added `REMi` endpoints


## 4.2.7 (2024-11-07)


- Support activity log query and download apis.


## 4.2.6 (2024-10-28)


- Support `context` in `rephrase()`


## 4.2.5 (2024-10-17)


- Support custom prompt on predict rephrase


## 4.2.4 (2024-10-16)


- Fix NUA authentication


## 4.2.3 (2024-10-11)


- Support `top_k`


## 4.2.2 (2024-09-19)


- Optionally override already existing resources when copying


## 4.2.1 (2024-09-16)


- Manage back pressure on resource copy


## 4.2.0 (2024-09-09)


- Download files stored in resources
- Allow to copy resources between KBs


## 4.1.1 (2024-09-03)


- Update dependencies


## 4.1.0 (2024-08-30)


- Support `/predict/rephrase` endpoint


## 4.0.5 (2024-08-01)


- Fix: properly get the kb from the current configuration.


## 4.0.4 (2024-07-26)


- Follow redirect when uploading a remote file via URL


## 4.0.3 (2024-07-26)


- Support `page` and `size` parameters on KB's `list` method


## 4.0.2 (2024-07-24)


- Fix: allow to update the resource slug


## 4.0.1 (2024-07-18)


- Backoff retry rate limit errors in resource create/update ops


## 4.0.0 (2024-07-17)


- Notification endpoint
- Duplication file detection
- Improve serialization of CLI output
- Support to add existing KBs as enabled local KBs
- Listing of available KBs
- Move from print to logger
- Remove sys.exit calls
- Support ask_json with json file path
- Remove deprecated functions and text field on GenerativeFullResponse


## 3.3.0 (2024-06-24)


- Accept all options on `ask()`, `search()` and `find()` methods.


## 3.2.2 (2024-06-19)


- Fix `ask_json` str return


## 3.2.1 (2024-06-19)


- Use Python Dict as a JSON parsed


## 3.2.0 (2024-06-17)


- Add stream NUA generative call
- Deprecation: response of NUA generative direct call will return a `GenerativeFullResponse` object with an answer field. The text field is deprecated.
- Support ask endpoint stream
- Add JSON output with jsonschema

## 3.1.1 (2024-06-13)


- Adapt NUA config


## 3.1.0 (2024-05-31)

### Features

- Support table interpretation when uploading a file

### Fixes

- Upgrade to pydantic 2

## 3.0.0 (2024-05-30)

### Breaking change

- Rename `chat()` to `ask()`

## 2.1.0 (2024-05-17)

- Integrate new /ask endpoint

## 2.0.12 (2024-05-16)

- Add generative stream on NUA API
- Support security groups on search endpoints raw queries

## 2.0.11 (2024-03-27)

- Handle nucliadb back pressure with backoff

## 2.0.10 (2024-03-26)

- Support summarize resources on a KB and Async KB management

## 2.0.9 (2024-03-20)

- Chat needs a timeout.

## 2.0.8 (2024-03-18)

- Support CSS selector when uploading links

## 2.0.7 (2024-03-18)

- Fix bug on export creating folders.

## 2.0.6 (2024-03-15)

- Add async export/import.
- Add Query endpoint.

## 2.0.5 (2024-03-08)

- Fix dependencies.

## 2.0.4 (2024-02-29)

- Allow to download Knowledge Box logs

## 2.0.3 (2024-02-26)

- Fix upload chunk size
- Support async

## 2.0.2 (2024-02-23)

- Check errors when getting remote files
- Increase uploads chunk size to work with both s3 and gcs

## 2.0.1 (2024-02-21)

- Delete and update resources by slug natively with nucliadb-sdk
- Support `all`, `any`, `none` and `not_all` operators in `filters` parameter

## 2.0.0 (2024-02-18)

- Support AsyncIO Auth and Predict

## 1.2.4 (2024-01-18)

- Allow to set remote files field at creation

## 1.2.3 (2024-01-16)

- Support resources summarization

## 1.2.2 (2024-01-11)

- Update Nuclia dependencies to get the new AWS region.

## 1.2.1 (2024-01-08)

- Improve prompt generation

## 1.2.0 (2023-12-21)

** BREAKING CHANGE **

- Use the new regional endpoints

## 1.1.22 (2023-12-15)

- Fix context format and add test

## 1.1.21 (2023-12-11)

- Support the new regional endpoints.
- Fix processing

## 1.1.20 (2023-12-05)

- Add more NUA Predict funtionalities (file processing, summarize)

## 1.1.19 (2023-11-15)

- Improve documentation.
- Improve UX for exports and imports.
- Support `filters` as search parameter on `search`, `find` and `chat`.

## 1.1.18 (2023-11-10)

- Add `generate` and `generate_prompt` support in `NucliaPredict`.

## 1.1.17 (2023-11-02)

- Allow to set `metadata` values in a resource

## 1.1.16 (2023-10-31)

- Fix import/export

## 1.1.15 (2023-10-20)

- Fix file upload sdk example
- Fix auth documentation
- Fix mimetype detection + set a valid field id when none provided

## 1.1.14 (2023-10-04)

- Support public knowledgebox
- Add relations to the find experience

## 1.1.13 (2023-09-29)

- Return RID on upload
- Support KB import/export

## 1.1.12 (2023-09-21)

- Configuration API integration

## 1.1.11 (2023-09-13)

- Replace gnureadline with prompt_toolkit (for Windows compatibility)

## 1.1.10 (2023-08-30)

- Align Python version requirement with nuclia_sdk
- Fix Local nucliadb default retrieval

## 1.1.9 (2023-08-30)

- Relax requirements on PyYaml

## 1.1.8 (2023-08-30)

- Adding support for local NucliaDB
- Fix `--show` when passing a single value

## 1.1.7 (2023-08-28)

- Set KB with no interaction
- Provide custom client on knowledgebox actions

## 1.1.6 (2023-07-27)

- Adding labels and labelset support

## 1.1.5 (2023-07-26)

- Support summary as resource attribute
- Allow to create kb
- Allow to set default account

## 1.1.4 (2023-07-21)

- Fix http status check

## 1.1.3 (2023-07-21)

- Use pyyaml==5.3.1 as 5.4 is broken
- Handle token expiration in a better way

## 1.1.2 (2023-07-10)

- Manage UserTokenExpired in CLI.
- Support `show` and `extracted` when getting a resource.
- Refactor all resource related actions in a class.
- Support `Link` upload

## 1.1.1 (2023-07-07)

- Set region parameter according KB url

## 1.1.0 (2023-07-05)

- Support `--json` and `--yaml` options
- Rename `ask` in `chat` as `ask` will be another new feature
- Support all regular Nuclia resource metadata
- Update the resource if it exists

## 1.0.4 (2023-06-29)

- Fix NUA Key auth and sentence predict
- Pin Nuclia dependencies
- Fix documentation
- Add `search` method in `NucliaSearch`
- Support TextField upload

## 1.0.3 (2023-06-20)

Initial version with support of KB authentication and NUA
