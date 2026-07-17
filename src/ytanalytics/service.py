from __future__ import annotations

from .api import GoogleAPIClient
from .models import (
    AudienceRetentionPoint,
    ChannelSummary,
    DateRange,
    VideoDetails,
    VideoPerformance,
)


class AnalyticsService:
    def __init__(self, client: GoogleAPIClient) -> None:
        self.client = client

    def channel_summary(self, period: DateRange) -> ChannelSummary:
        table = self.client.analytics_report(
            ids="channel==MINE",
            startDate=period.start.isoformat(),
            endDate=period.end.isoformat(),
            metrics=(
                "views,estimatedMinutesWatched,averageViewDuration,"
                "subscribersGained,subscribersLost"
            ),
        )
        row = table.rows[0] if table.rows else {}
        return ChannelSummary(
            start_date=period.start,
            end_date=period.end,
            views=row.get("views", 0),
            watch_time_minutes=row.get("estimatedMinutesWatched", 0),
            average_view_duration_seconds=row.get("averageViewDuration", 0),
            subscribers_gained=row.get("subscribersGained", 0),
            subscribers_lost=row.get("subscribersLost", 0),
        )

    def top_videos(self, period: DateRange, *, limit: int = 10) -> list[VideoPerformance]:
        return self._ranked_videos(period, limit=limit, sort="-views")

    def bottom_videos(self, period: DateRange, *, limit: int = 5) -> list[VideoPerformance]:
        rows: list[dict] = []
        start_index = 1
        page_size = 200
        while True:
            table = self.client.analytics_report(
                ids="channel==MINE",
                startDate=period.start.isoformat(),
                endDate=period.end.isoformat(),
                dimensions="video",
                metrics=(
                    "views,estimatedMinutesWatched,averageViewDuration,subscribersGained"
                ),
                sort="-views",
                maxResults=page_size,
                startIndex=start_index,
            )
            rows.extend(table.rows)
            if len(table.rows) < page_size:
                break
            start_index += len(table.rows)
        return self._video_performance(list(reversed(rows[-limit:])))

    def _ranked_videos(
        self,
        period: DateRange,
        *,
        limit: int,
        sort: str,
    ) -> list[VideoPerformance]:
        table = self.client.analytics_report(
            ids="channel==MINE",
            startDate=period.start.isoformat(),
            endDate=period.end.isoformat(),
            dimensions="video",
            metrics="views,estimatedMinutesWatched,averageViewDuration,subscribersGained",
            sort=sort,
            maxResults=limit,
        )
        return self._video_performance(list(table.rows))

    def _video_performance(self, rows: list[dict]) -> list[VideoPerformance]:
        ids = [str(row["video"]) for row in rows]
        titles = self.client.video_titles(ids)
        return [
            VideoPerformance(
                video_id=str(row["video"]),
                title=titles.get(str(row["video"])),
                views=row.get("views", 0),
                watch_time_minutes=row.get("estimatedMinutesWatched", 0),
                average_view_duration_seconds=row.get("averageViewDuration", 0),
                subscribers_gained=row.get("subscribersGained", 0),
            )
            for row in rows
        ]

    def audience_retention(
        self, video_id: str, period: DateRange
    ) -> list[AudienceRetentionPoint]:
        """Return the audience-retention curve for one owned video."""
        video_id = video_id.strip()
        if not video_id:
            raise ValueError("video ID must not be empty")

        table = self.client.analytics_report(
            ids="channel==MINE",
            startDate=period.start.isoformat(),
            endDate=period.end.isoformat(),
            dimensions="elapsedVideoTimeRatio",
            metrics="audienceWatchRatio",
            filters=f"video=={video_id}",
        )
        return [
            AudienceRetentionPoint(
                elapsed_video_time_ratio=row["elapsedVideoTimeRatio"],
                audience_watch_ratio=row["audienceWatchRatio"],
            )
            for row in table.rows
        ]

    def video_details(self, video_id: str) -> VideoDetails:
        video_id = video_id.strip()
        if not video_id:
            raise ValueError("video ID must not be empty")
        return self.client.video_details(video_id)
