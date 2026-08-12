class CollectorError(RuntimeError):
    """Base class for expected collector failures."""


class SourceUnavailable(CollectorError):
    """The source could not be retrieved successfully."""


class EntryListNotPublished(CollectorError):
    """The page is available but does not contain the expected entry list yet."""


class ParsingFailed(CollectorError):
    """The source looked relevant but could not be parsed safely."""

