class ConfigNotFound(Exception):
    pass


class NeedUserToken(Exception):
    pass


class UserTokenExpired(Exception):
    pass


class NotDefinedDefault(Exception):
    pass


class APIException(Exception):
    api_name: str

    def __init__(self, code: int, detail: str):
        self.code = code
        self.detail = detail
        message = f"Exception calling {self.api_name} API: {self.code} {self.detail}"
        super().__init__(message)


class RaoAPIException(APIException):
    api_name: str = "RAO"


class NuaAPIException(APIException):
    api_name: str = "NUA"


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
