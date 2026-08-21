class ResourceAlreadyExistsError(Exception):
    """Raised when attempting to create a new resource with a slug that already exists."""

    pass


class ResourceNotFoundError(Exception):
    """Raised when a resource with the specified ID or slug cannot be found."""

    pass


# Keeping the `Topic` alias for backwards compatibility, but it is now deprecated in favor of `Resource`.
TopicAlreadyExistsError = ResourceAlreadyExistsError
TopicNotFoundError = ResourceNotFoundError


class EntryAlreadyExistsError(Exception):
    """Raised when attempting to create a new entry with an ID that already exists for the resource and user."""

    pass
