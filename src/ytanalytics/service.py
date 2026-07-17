from __future__ import annotations

from .api import GoogleAPIClient
from .models import AudienceRetentionPoint, ChannelSummary, DateRange, VideoPerformance


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
        table = self.client.analytics_report(
            ids="channel==MINE",
            startDate=period.start.isoformat(),
            endDate=period.end.isoformat(),
            dimensions="video",
            metrics="views,estimatedMinutesWatched,averageViewDuration,subscribersGained",
            sort="-views",
            maxResults=limit,
        )
        ids = [str(row["video"]) for row in table.rows]
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
            for row in table.rows
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
