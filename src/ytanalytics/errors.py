class YTAnalyticsError(Exception):
    """Base exception rendered as a concise CLI error."""


class AuthenticationError(YTAnalyticsError):
    """The selected profile cannot authenticate."""


class APIError(YTAnalyticsError):
    """A Google API request failed."""

