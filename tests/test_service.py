from datetime import date

from ytanalytics.models import DateRange, ResultTable
from ytanalytics.service import AnalyticsService


class FakeClient:
    def __init__(self):
        self.last_params = None

    def analytics_report(self, **params):
        self.last_params = params
        if params.get("dimensions") == "elapsedVideoTimeRatio":
            return ResultTable(
                headers=("elapsedVideoTimeRatio", "audienceWatchRatio"),
                rows=(
                    {"elapsedVideoTimeRatio": 0.01, "audienceWatchRatio": 1.1},
                    {"elapsedVideoTimeRatio": 1.0, "audienceWatchRatio": 0.42},
                ),
            )
        if params.get("dimensions") == "video":
            return ResultTable(
                headers=("video", "views"),
                rows=({"video": "abc", "views": 99, "estimatedMinutesWatched": 12},),
            )
        return ResultTable(
            headers=("views",),
            rows=({"views": 100, "estimatedMinutesWatched": 50},),
        )

    def video_titles(self, video_ids):
        return {"abc": "Example video"}


def test_channel_summary_normalizes_google_names() -> None:
    result = AnalyticsService(FakeClient()).channel_summary(
        DateRange(start=date(2026, 1, 1), end=date(2026, 1, 28))
    )
    assert result.views == 100
    assert result.watch_time_minutes == 50


def test_top_videos_enriches_titles() -> None:
    result = AnalyticsService(FakeClient()).top_videos(
        DateRange(start=date(2026, 1, 1), end=date(2026, 1, 28))
    )
    assert result[0].title == "Example video"
    assert result[0].views == 99


def test_audience_retention_uses_required_dimension_metric_and_filter() -> None:
    client = FakeClient()
    result = AnalyticsService(client).audience_retention(
        "abc", DateRange(start=date(2026, 1, 1), end=date(2026, 1, 28))
    )

    assert result[0].elapsed_video_time_ratio == 0.01
    assert result[0].audience_watch_ratio == 1.1
    assert result[-1].audience_watch_ratio == 0.42
    assert client.last_params == {
        "ids": "channel==MINE",
        "startDate": "2026-01-01",
        "endDate": "2026-01-28",
        "dimensions": "elapsedVideoTimeRatio",
        "metrics": "audienceWatchRatio",
        "filters": "video==abc",
    }
