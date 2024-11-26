class ConfigNotFound(Exception):
    pass


class NeedUserToken(Exception):
    pass


class UserTokenExpired(Exception):
    pass


class NotDefinedDefault(Exception):
    pass


class NuaAPIException(Exception):
    def __init__(self, code: int, detail: str):
        self.code = code
        self.detail = detail
        message = f"Exception calling NUA API: {self.code} {self.detail}"
        super().__init__(message)


class AlreadyConsumed(Exception):
    pass


class GettingRemoteFileError(Exception):
    pass


class RateLimitError(Exception):
    pass


class NucliaConnectionError(Exception):
    pass


class KBNotAvailable(Exception):
    pass


class DuplicateError(Exception):
    pass


class InvalidPayload(Exception):
    pass
