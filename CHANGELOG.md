# Changelog

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
