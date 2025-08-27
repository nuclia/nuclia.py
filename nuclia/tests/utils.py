import inspect
from typing import Awaitable, TypeVar, Union

T = TypeVar("T")


async def maybe_await(aw_or_value: Union[Awaitable[T], T]) -> T:
    """Given a result from a call to a sync or an async function (a value or an
    awaitable of a value), await if needed and return the value. This is useful
    to test sync and async versions of the SDK using the same test functions.

    """
    if inspect.isawaitable(aw_or_value):
        return await aw_or_value
    else:
        return aw_or_value
