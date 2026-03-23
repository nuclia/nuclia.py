import pytest

from nuclia.exceptions import (
    AlreadyConsumed,
    APIException,
    ConfigNotFound,
    DuplicateError,
    GettingRemoteFileError,
    InvalidPayload,
    KBNotAvailable,
    NuaAPIException,
    NucliaConnectionError,
    NeedUserToken,
    NotDefinedDefault,
    RaoAPIException,
    RateLimitError,
    UserTokenExpired,
)


def test_api_exception_message():
    # APIException requires api_name to be defined - use a concrete subclass
    exc = RaoAPIException(404, "Not found")
    assert exc.code == 404
    assert exc.detail == "Not found"
    assert "404" in str(exc)
    assert "Not found" in str(exc)


def test_rao_api_exception():
    exc = RaoAPIException(500, "Server error")
    assert exc.api_name == "RAO"
    assert "RAO" in str(exc)
    assert exc.code == 500


def test_nua_api_exception():
    exc = NuaAPIException(403, "Forbidden")
    assert exc.api_name == "NUA"
    assert "NUA" in str(exc)
    assert exc.code == 403


def test_simple_exceptions_are_instantiable():
    for exc_class in [
        ConfigNotFound,
        NeedUserToken,
        UserTokenExpired,
        NotDefinedDefault,
        AlreadyConsumed,
        GettingRemoteFileError,
        RateLimitError,
        NucliaConnectionError,
        KBNotAvailable,
        DuplicateError,
        InvalidPayload,
    ]:
        exc = exc_class("test message")
        assert isinstance(exc, Exception)
