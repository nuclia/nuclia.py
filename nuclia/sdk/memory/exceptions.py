class TopicAlreadyExistsError(Exception):
    """Raised when attempting to create a new topic with a slug that already exists."""

    pass


class TopicNotFoundError(Exception):
    """Raised when an topic with the specified ID or slug cannot be found."""

    pass


class EntryAlreadyExistsError(Exception):
    """Raised when attempting to create a new entry with an ID that already exists for the topic and user."""

    pass
