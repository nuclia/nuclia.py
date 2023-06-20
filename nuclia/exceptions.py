class ConfigNotFound(Exception):
    pass


class NeedUserToken(Exception):
    pass


class UserTokenExpired(Exception):
    pass


class NotDefinedDefault(Exception):
    pass


class NuaAPIException(Exception):
    pass
