import pytest

from ytanalytics.api import parse_youtube_duration
from ytanalytics.errors import APIError


@pytest.mark.parametrize(
    ("value", "seconds"),
    [("PT28S", 28), ("PT2M3S", 123), ("PT1H2M3S", 3723)],
)
def test_parse_youtube_duration(value: str, seconds: int) -> None:
    assert parse_youtube_duration(value) == seconds


def test_parse_youtube_duration_rejects_unknown_format() -> None:
    with pytest.raises(APIError, match="unsupported"):
        parse_youtube_duration("P1D")
