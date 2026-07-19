from __future__ import annotations

from datetime import UTC, date, datetime
from statistics import mean, pstdev

from .api import GoogleAPIClient
from .models import (
    AudienceRetentionPoint,
    ChannelAnomaly,
    ChannelForecast,
    ChannelSummary,
    ChannelTrendPoint,
    ContentType,
    DateRange,
    GrowthAudit,
    GrowthRecommendation,
    MetricDelta,
    RetentionCheckpoint,
    RetentionDiagnosis,
    RetentionEvent,
    SegmentPerformance,
    VideoAnalytics,
    VideoDetails,
    VideoPerformance,
    VideoRankMetric,
)

SUMMARY_METRICS = (
    "views,estimatedMinutesWatched,averageViewDuration,subscribersGained,subscribersLost"
)
VIDEO_METRICS = (
    "engagedViews,views,estimatedMinutesWatched,averageViewDuration,"
    "averageViewPercentage,subscribersGained,subscribersLost,likes,comments,shares"
)
SEGMENT_METRICS = "engagedViews,views,estimatedMinutesWatched"


class AnalyticsService:
    def __init__(self, client: GoogleAPIClient) -> None:
        self.client = client

    def channel_summary(self, period: DateRange) -> ChannelSummary:
        table = self.client.analytics_report(
            ids="channel==MINE",
            startDate=period.start.isoformat(),
            endDate=period.end.isoformat(),
            metrics=SUMMARY_METRICS,
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

    def channel_trend(self, period: DateRange) -> list[ChannelTrendPoint]:
        table = self.client.analytics_report(
            ids="channel==MINE",
            startDate=period.start.isoformat(),
            endDate=period.end.isoformat(),
            dimensions="day",
            metrics=f"engagedViews,{SUMMARY_METRICS}",
            sort="day",
        )
        return [
            ChannelTrendPoint(
                day=date.fromisoformat(str(row["day"])),
                views=row.get("views", 0),
                engaged_views=row.get("engagedViews", 0),
                watch_time_minutes=row.get("estimatedMinutesWatched", 0),
                average_view_duration_seconds=row.get("averageViewDuration", 0),
                subscribers_gained=row.get("subscribersGained", 0),
                subscribers_lost=row.get("subscribersLost", 0),
                net_subscribers=row.get("subscribersGained", 0) - row.get("subscribersLost", 0),
            )
            for row in table.rows
        ]

    def channel_comparison(self, period: DateRange) -> list[MetricDelta]:
        current = self.channel_summary(period)
        previous = self.channel_summary(period.previous())
        values = (
            ("views", current.views, previous.views),
            ("watch_time_minutes", current.watch_time_minutes, previous.watch_time_minutes),
            (
                "average_view_duration_seconds",
                current.average_view_duration_seconds,
                previous.average_view_duration_seconds,
            ),
            ("net_subscribers", current.net_subscribers, previous.net_subscribers),
        )
        return [_metric_delta(name, now, before) for name, now, before in values]

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
                metrics=("views,estimatedMinutesWatched,averageViewDuration,subscribersGained"),
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

    def video_analytics(
        self,
        period: DateRange,
        *,
        video_ids: list[str] | None = None,
    ) -> list[VideoAnalytics]:
        if video_ids is not None and not video_ids:
            return []
        if video_ids is not None and len(video_ids) > 500:
            raise ValueError("a report can compare at most 500 videos")
        rows: list[dict] = []
        start_index = 1
        page_size = 200
        while True:
            params: dict = {
                "ids": "channel==MINE",
                "startDate": period.start.isoformat(),
                "endDate": period.end.isoformat(),
                "dimensions": "video",
                "metrics": VIDEO_METRICS,
                "sort": "-views",
                "maxResults": page_size,
                "startIndex": start_index,
            }
            if video_ids is not None:
                params["filters"] = f"video=={','.join(video_ids)}"
            table = self.client.analytics_report(**params)
            rows.extend(table.rows)
            if len(table.rows) < page_size:
                break
            start_index += len(table.rows)

        ids = [str(row["video"]) for row in rows]
        metadata = self.client.video_metadata(ids)
        results: list[VideoAnalytics] = []
        for row in rows:
            video_id = str(row["video"])
            item = metadata.get(video_id)
            views = int(row.get("views", 0))
            engaged_views = int(row.get("engagedViews", 0))
            subscribers = int(row.get("subscribersGained", 0))
            interactions = sum(int(row.get(key, 0)) for key in ("likes", "comments", "shares"))
            published_date = item.published_at.date() if item and item.published_at else None
            active_days = _active_days(period, published_date)
            results.append(
                VideoAnalytics(
                    video_id=video_id,
                    title=item.title if item else None,
                    published_at=item.published_at if item else None,
                    duration_seconds=item.duration_seconds if item else 0,
                    aspect_ratio=item.aspect_ratio if item else None,
                    content_type=item.content_type if item else ContentType.unknown,
                    views=views,
                    engaged_views=engaged_views,
                    watch_time_minutes=row.get("estimatedMinutesWatched", 0),
                    average_view_duration_seconds=row.get("averageViewDuration", 0),
                    average_view_percentage=row.get("averageViewPercentage", 0),
                    subscribers_gained=subscribers,
                    subscribers_lost=row.get("subscribersLost", 0),
                    likes=row.get("likes", 0),
                    comments=row.get("comments", 0),
                    shares=row.get("shares", 0),
                    views_per_day=views / active_days,
                    subscribers_per_1000_views=_per_thousand(subscribers, views),
                    engagement_per_1000_views=_per_thousand(interactions, views),
                    engaged_view_ratio=engaged_views / views if views else None,
                )
            )
        return results

    def rank_videos(
        self,
        period: DateRange,
        *,
        metric: VideoRankMetric = VideoRankMetric.views,
        limit: int = 10,
        content_type: ContentType | None = None,
        descending: bool = True,
    ) -> list[VideoAnalytics]:
        videos = self.video_analytics(period)
        if content_type is not None:
            videos = [item for item in videos if item.content_type == content_type]
        attribute = {
            VideoRankMetric.watch_time: "watch_time_minutes",
        }.get(metric, metric.value)
        videos.sort(
            key=lambda item: (
                getattr(item, attribute) if getattr(item, attribute) is not None else -1
            ),
            reverse=descending,
        )
        return videos[:limit]

    def compare_videos(self, video_ids: list[str], period: DateRange) -> list[VideoAnalytics]:
        normalized = list(dict.fromkeys(item.strip() for item in video_ids if item.strip()))
        if len(normalized) < 2:
            raise ValueError("provide at least two video IDs to compare")
        return self.video_analytics(period, video_ids=normalized)

    def shorts_performance(
        self,
        period: DateRange,
        *,
        limit: int = 25,
        metric: VideoRankMetric = VideoRankMetric.engaged_view_ratio,
    ) -> list[VideoAnalytics]:
        return self.rank_videos(
            period,
            metric=metric,
            limit=limit,
            content_type=ContentType.shorts,
        )

    def traffic_sources(self, period: DateRange) -> list[SegmentPerformance]:
        return self._segments(period, "insightTrafficSourceType", sort="-views")

    def traffic_search(self, period: DateRange, *, limit: int = 25) -> list[SegmentPerformance]:
        return self._segments(
            period,
            "insightTrafficSourceDetail",
            filters="insightTrafficSourceType==YT_SEARCH",
            sort="-views",
            max_results=min(limit, 25),
        )

    def audience_devices(self, period: DateRange) -> list[SegmentPerformance]:
        return self._segments(period, "deviceType", sort="-views")

    def audience_geography(self, period: DateRange, *, limit: int = 25) -> list[SegmentPerformance]:
        return self._segments(period, "country", sort="-views", max_results=limit)

    def audience_subscribers(self, period: DateRange) -> list[SegmentPerformance]:
        return self._segments(period, "subscribedStatus", sort="-views")

    def _segments(
        self,
        period: DateRange,
        dimension: str,
        *,
        filters: str | None = None,
        sort: str | None = None,
        max_results: int | None = None,
    ) -> list[SegmentPerformance]:
        params: dict = {
            "ids": "channel==MINE",
            "startDate": period.start.isoformat(),
            "endDate": period.end.isoformat(),
            "dimensions": dimension,
            "metrics": SEGMENT_METRICS,
        }
        if filters:
            params["filters"] = filters
        if sort:
            params["sort"] = sort
        if max_results:
            params["maxResults"] = max_results
        table = self.client.analytics_report(**params)
        total_views = sum(int(row.get("views", 0)) for row in table.rows)
        total_watch = sum(float(row.get("estimatedMinutesWatched", 0)) for row in table.rows)
        return [
            SegmentPerformance(
                segment=_segment_label(dimension, str(row[dimension])),
                segment_code=str(row[dimension]),
                views=row.get("views", 0),
                engaged_views=row.get("engagedViews", 0),
                watch_time_minutes=row.get("estimatedMinutesWatched", 0),
                view_share=_safe_ratio(row.get("views", 0), total_views),
                watch_time_share=_safe_ratio(row.get("estimatedMinutesWatched", 0), total_watch),
            )
            for row in table.rows
        ]

    def audience_retention(self, video_id: str, period: DateRange) -> list[AudienceRetentionPoint]:
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

    def retention_diagnosis(self, video_id: str, period: DateRange) -> RetentionDiagnosis:
        details = self.video_details(video_id)
        points = sorted(
            self.audience_retention(video_id, period),
            key=lambda point: point.elapsed_video_time_ratio,
        )
        if not points:
            raise ValueError("YouTube returned no retention data for this video and period")
        checkpoint_specs: list[tuple[str, float]] = []
        for seconds in (1, 3, 5, 10):
            if seconds <= details.duration_seconds:
                checkpoint_specs.append((f"{seconds}s", seconds / details.duration_seconds))
        checkpoint_specs.extend([("25%", 0.25), ("50%", 0.5), ("75%", 0.75), ("end", 1.0)])
        checkpoints = [
            RetentionCheckpoint(
                label=label,
                elapsed_seconds=ratio * details.duration_seconds,
                elapsed_ratio=ratio,
                audience_watch_ratio=_interpolate_retention(points, ratio),
            )
            for label, ratio in checkpoint_specs
        ]
        changes = [
            (
                current.audience_watch_ratio - previous.audience_watch_ratio,
                current,
            )
            for previous, current in zip(points, points[1:], strict=False)
        ]
        drops = sorted(changes, key=lambda item: item[0])[:3]
        spikes = sorted(changes, key=lambda item: item[0], reverse=True)[:3]
        events = [
            RetentionEvent(
                event_type="drop",
                elapsed_seconds=point.elapsed_video_time_ratio * details.duration_seconds,
                elapsed_ratio=point.elapsed_video_time_ratio,
                change=change,
                audience_watch_ratio=point.audience_watch_ratio,
            )
            for change, point in drops
            if change < 0
        ] + [
            RetentionEvent(
                event_type="rewatch_spike",
                elapsed_seconds=point.elapsed_video_time_ratio * details.duration_seconds,
                elapsed_ratio=point.elapsed_video_time_ratio,
                change=change,
                audience_watch_ratio=point.audience_watch_ratio,
            )
            for change, point in spikes
            if change > 0
        ]
        return RetentionDiagnosis(
            video_id=details.video_id,
            title=details.title,
            duration_seconds=details.duration_seconds,
            curve_area=_curve_area(points),
            ending_retention=_interpolate_retention(points, 1.0),
            checkpoints=checkpoints,
            events=events,
        )

    def channel_forecast(
        self,
        period: DateRange,
        *,
        forecast_days: int = 28,
    ) -> ChannelForecast:
        trend = self.channel_trend(period)
        if len(trend) < 7:
            raise ValueError("forecasting requires at least seven days of analytics data")
        views_slope, views_intercept, views_r2 = _linear_regression(
            [float(item.views) for item in trend]
        )
        subs_slope, subs_intercept, _ = _linear_regression(
            [float(item.net_subscribers) for item in trend]
        )
        start = len(trend)
        projected_views = sum(
            max(0, views_intercept + views_slope * day)
            for day in range(start, start + forecast_days)
        )
        projected_subscribers = sum(
            subs_intercept + subs_slope * day for day in range(start, start + forecast_days)
        )
        confidence = "high" if views_r2 >= 0.7 else "medium" if views_r2 >= 0.4 else "low"
        return ChannelForecast(
            history_days=len(trend),
            forecast_days=forecast_days,
            projected_views=round(projected_views),
            projected_net_subscribers=round(projected_subscribers),
            daily_views_slope=views_slope,
            confidence=confidence,
        )

    def channel_anomalies(
        self,
        period: DateRange,
        *,
        threshold: float = 2.0,
    ) -> list[ChannelAnomaly]:
        trend = self.channel_trend(period)
        return _anomalies(trend, "views", threshold) + _anomalies(
            trend, "net_subscribers", threshold
        )

    def growth_audit(self, period: DateRange) -> GrowthAudit:
        current = self.channel_summary(period)
        comparison = self.channel_comparison(period)
        videos = self.video_analytics(period)
        traffic = self.traffic_sources(period)
        top = sorted(videos, key=lambda item: item.views, reverse=True)[:5]
        converters = sorted(
            (item for item in videos if item.views >= 100),
            key=lambda item: item.subscribers_per_1000_views,
            reverse=True,
        )[:5]
        recommendations = _growth_recommendations(
            current=current,
            comparison=comparison,
            videos=videos,
            traffic=traffic,
            top=top,
            converters=converters,
        )
        return GrowthAudit(
            generated_at=datetime.now(UTC),
            current_period=period,
            previous_period=period.previous(),
            current_summary=current,
            comparison=comparison,
            videos=sorted(videos, key=lambda item: item.views, reverse=True),
            top_videos=top,
            top_subscriber_converters=converters,
            traffic_sources=traffic[:10],
            recommendations=recommendations,
        )

    def video_details(self, video_id: str) -> VideoDetails:
        video_id = video_id.strip()
        if not video_id:
            raise ValueError("video ID must not be empty")
        return self.client.video_details(video_id)


def _metric_delta(name: str, current: float, previous: float) -> MetricDelta:
    change = current - previous
    percent = change / abs(previous) if previous else None
    return MetricDelta(
        metric=name,
        current=current,
        previous=previous,
        absolute_change=change,
        percent_change=percent,
    )


def _active_days(period: DateRange, published_at: date | None) -> int:
    start = max(period.start, published_at) if published_at else period.start
    return max(1, (period.end - start).days + 1)


def _per_thousand(value: int | float, views: int) -> float:
    return value * 1000 / views if views else 0


def _safe_ratio(value: int | float, total: int | float) -> float:
    return value / total if total else 0


def _segment_label(dimension: str, value: str) -> str:
    if dimension == "insightTrafficSourceType":
        return {
            "YT_CHANNEL": "Channel pages",
            "SHORTS": "Shorts feed",
            "YT_OTHER_PAGE": "Other YouTube pages",
            "YT_SEARCH": "YouTube search",
            "SUBSCRIBER": "Subscriptions feed",
            "EXT_URL": "External websites",
            "NOTIFICATION": "Notifications",
            "NO_LINK_OTHER": "Direct or unknown",
            "RELATED_VIDEO": "Suggested videos",
            "HASHTAGS": "Hashtag pages",
            "PLAYLIST": "Playlists",
            "SOUND_PAGE": "Sound pages",
            "SHORTS_CONTENT_LINKS": "Shorts related links",
        }.get(value, value.replace("_", " ").title())
    if dimension == "deviceType":
        return value.replace("_", " ").title()
    if dimension == "subscribedStatus":
        return {
            "SUBSCRIBED": "Subscribed",
            "UNSUBSCRIBED": "Not subscribed",
        }.get(value, value.replace("_", " ").title())
    return value


def _interpolate_retention(points: list[AudienceRetentionPoint], ratio: float) -> float:
    if ratio <= points[0].elapsed_video_time_ratio:
        return points[0].audience_watch_ratio
    if ratio >= points[-1].elapsed_video_time_ratio:
        return points[-1].audience_watch_ratio
    for left, right in zip(points, points[1:], strict=False):
        if left.elapsed_video_time_ratio <= ratio <= right.elapsed_video_time_ratio:
            width = right.elapsed_video_time_ratio - left.elapsed_video_time_ratio
            if width == 0:
                return right.audience_watch_ratio
            progress = (ratio - left.elapsed_video_time_ratio) / width
            return left.audience_watch_ratio + progress * (
                right.audience_watch_ratio - left.audience_watch_ratio
            )
    return points[-1].audience_watch_ratio


def _curve_area(points: list[AudienceRetentionPoint]) -> float:
    area = 0.0
    for left, right in zip(points, points[1:], strict=False):
        width = right.elapsed_video_time_ratio - left.elapsed_video_time_ratio
        area += width * (left.audience_watch_ratio + right.audience_watch_ratio) / 2
    return area


def _linear_regression(values: list[float]) -> tuple[float, float, float]:
    xs = list(range(len(values)))
    x_mean = mean(xs)
    y_mean = mean(values)
    denominator = sum((x - x_mean) ** 2 for x in xs)
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, values, strict=True))
    slope = slope / denominator if denominator else 0
    intercept = y_mean - slope * x_mean
    predictions = [intercept + slope * x for x in xs]
    residual = sum(
        (actual - predicted) ** 2 for actual, predicted in zip(values, predictions, strict=True)
    )
    total = sum((actual - y_mean) ** 2 for actual in values)
    r_squared = 1 - residual / total if total else 1
    return slope, intercept, max(0, r_squared)


def _anomalies(
    trend: list[ChannelTrendPoint], metric: str, threshold: float
) -> list[ChannelAnomaly]:
    values = [float(getattr(item, metric)) for item in trend]
    if len(values) < 7:
        return []
    slope, intercept, _ = _linear_regression(values)
    expected_values = [intercept + slope * index for index in range(len(values))]
    residuals = [
        value - expected
        for value, expected in zip(values, expected_values, strict=True)
    ]
    deviation = pstdev(residuals)
    if deviation == 0:
        return []
    results = []
    for item, value, expected in zip(trend, values, expected_values, strict=True):
        score = (value - expected) / deviation
        if abs(score) >= threshold:
            results.append(
                ChannelAnomaly(
                    day=item.day,
                    metric=metric,
                    value=value,
                    expected=expected,
                    z_score=score,
                    direction="above" if score > 0 else "below",
                )
            )
    return results


def _growth_recommendations(
    *,
    current: ChannelSummary,
    comparison: list[MetricDelta],
    videos: list[VideoAnalytics],
    traffic: list[SegmentPerformance],
    top: list[VideoAnalytics],
    converters: list[VideoAnalytics],
) -> list[GrowthRecommendation]:
    recommendations: list[GrowthRecommendation] = []
    views_change = next((item for item in comparison if item.metric == "views"), None)
    if views_change and views_change.percent_change is not None:
        direction = "grew" if views_change.percent_change >= 0 else "declined"
        recommendations.append(
            GrowthRecommendation(
                priority=1,
                category="momentum",
                title="Repeat the formats driving the current momentum"
                if views_change.percent_change >= 0
                else "Reverse the current view decline with proven formats",
                rationale=(
                    f"Channel views {direction} {abs(views_change.percent_change):.1%} "
                    "against the preceding equal-length period."
                ),
                evidence=[
                    f"Current views: {current.views:,}",
                    f"Previous views: {views_change.previous:,.0f}",
                    *[f"Top video: {item.title} ({item.views:,} views)" for item in top[:3]],
                ],
                actions=[
                    "Extract the recurring topic, promise, and format from the top three videos.",
                    "Publish two controlled follow-ups that vary only one creative element.",
                ],
                impact="high",
                confidence="high",
                effort="medium",
            )
        )

    total_views = sum(item.views for item in videos)
    concentration = sum(item.views for item in top[:3]) / total_views if total_views else 0
    recommendations.append(
        GrowthRecommendation(
            priority=2,
            category="portfolio",
            title="Build repeatable content clusters around proven winners",
            rationale=(
                f"The top three videos produced {concentration:.1%} of measured video views. "
                "A cluster strategy can turn isolated hits into repeatable discovery."
            ),
            evidence=[f"{item.title}: {item.views:,} views" for item in top[:3]],
            actions=[
                "Create one direct sequel and one adjacent beginner-friendly video "
                "per winning topic.",
                "Link the cluster with playlists, end screens, and pinned comments.",
            ],
            impact="high",
            confidence="high" if total_views else "low",
            effort="medium",
        )
    )

    if converters:
        best = converters[0]
        recommendations.append(
            GrowthRecommendation(
                priority=3,
                category="subscriber_conversion",
                title="Reuse the value proposition that converts viewers into subscribers",
                rationale=(
                    f"{best.title!r} generated {best.subscribers_per_1000_views:.2f} subscribers "
                    "per 1,000 views, the strongest rate among videos with at least 100 views."
                ),
                evidence=[
                    f"{item.title}: {item.subscribers_per_1000_views:.2f} subscribers/1K views"
                    for item in converters[:3]
                ],
                actions=[
                    "Identify the audience promise made by the highest-converting video.",
                    "Use a specific subscription invitation immediately after delivering "
                    "that value.",
                ],
                impact="medium",
                confidence="high",
                effort="low",
            )
        )

    shorts = [item for item in videos if item.content_type == ContentType.shorts]
    if shorts:
        average_ratio = mean(item.engaged_view_ratio or 0 for item in shorts)
        recommendations.append(
            GrowthRecommendation(
                priority=4,
                category="shorts_hook",
                title="Test stronger first-second hooks on Shorts",
                rationale=(
                    f"Confirmed vertical Shorts averaged a {average_ratio:.1%} engaged-view ratio. "
                    "The ratio is a proxy for continuing past the initial seconds, not Studio's "
                    "exact stayed-to-watch rate."
                ),
                evidence=[
                    f"{item.title}: {(item.engaged_view_ratio or 0):.1%} engaged/view ratio"
                    for item in sorted(
                        shorts, key=lambda item: item.engaged_view_ratio or 0, reverse=True
                    )[:3]
                ],
                actions=[
                    "Open with the result or conflict before adding context.",
                    "Test two hook variants while keeping topic and duration comparable.",
                ],
                impact="high",
                confidence="medium",
                effort="low",
            )
        )

    if traffic:
        source = traffic[0]
        recommendations.append(
            GrowthRecommendation(
                priority=5,
                category="distribution",
                title=f"Design explicitly for the leading {source.segment} traffic source",
                rationale=(
                    f"{source.segment} supplied {source.view_share:.1%} of attributed views and "
                    f"{source.watch_time_share:.1%} of attributed watch time."
                ),
                evidence=[
                    f"{item.segment}: {item.view_share:.1%} of views" for item in traffic[:3]
                ],
                actions=[
                    "Match titles, openings, and follow-up paths to the leading discovery context.",
                    "Review source mix after each upload to distinguish content from "
                    "distribution gains.",
                ],
                impact="medium",
                confidence="high",
                effort="low",
            )
        )
    return recommendations
