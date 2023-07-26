# Changelog

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
