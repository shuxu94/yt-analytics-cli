from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DateRange(BaseModel):
    model_config = ConfigDict(frozen=True)

    start: date
    end: date

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def previous(self) -> DateRange:
        return DateRange(
            start=self.start - timedelta(days=self.days),
            end=self.start - timedelta(days=1),
        )

    @classmethod
    def from_period(cls, period: str, *, today: date | None = None) -> DateRange:
        today = today or date.today()
        if period == "lifetime":
            return cls(start=date(2005, 4, 23), end=today - timedelta(days=1))
        if not period.endswith("d") or not period[:-1].isdigit():
            raise ValueError(
                "period must be a positive number of days (for example 28d) or lifetime"
            )
        days = int(period[:-1])
        if days < 1:
            raise ValueError("period must be at least 1d")
        end = today - timedelta(days=1)
        return cls(start=end - timedelta(days=days - 1), end=end)


class ChannelSummary(BaseModel):
    start_date: date
    end_date: date
    views: int = 0
    watch_time_minutes: float = 0
    average_view_duration_seconds: float = 0
    subscribers_gained: int = 0
    subscribers_lost: int = 0

    @property
    def net_subscribers(self) -> int:
        return self.subscribers_gained - self.subscribers_lost


class ChannelTrendPoint(BaseModel):
    day: date
    views: int = 0
    engaged_views: int = 0
    watch_time_minutes: float = 0
    average_view_duration_seconds: float = 0
    subscribers_gained: int = 0
    subscribers_lost: int = 0
    net_subscribers: int = 0


class MetricDelta(BaseModel):
    metric: str
    current: float
    previous: float
    absolute_change: float
    percent_change: float | None = None


class ContentType(StrEnum):
    shorts = "shorts"
    long_form = "long_form"
    unknown = "unknown"


class VideoRankMetric(StrEnum):
    views = "views"
    views_per_day = "views_per_day"
    watch_time = "watch_time"
    average_view_percentage = "average_view_percentage"
    subscribers_gained = "subscribers_gained"
    subscribers_per_1000_views = "subscribers_per_1000_views"
    engaged_view_ratio = "engaged_view_ratio"
    engagement_per_1000_views = "engagement_per_1000_views"


class VideoPerformance(BaseModel):
    video_id: str
    title: str | None = None
    views: int = 0
    watch_time_minutes: float = 0
    average_view_duration_seconds: float = 0
    subscribers_gained: int = 0


class VideoMetadata(BaseModel):
    video_id: str
    title: str
    published_at: datetime | None = None
    duration_seconds: int = 0
    aspect_ratio: float | None = None
    content_type: ContentType = ContentType.unknown


class VideoAnalytics(BaseModel):
    video_id: str
    title: str | None = None
    published_at: datetime | None = None
    duration_seconds: int = 0
    aspect_ratio: float | None = None
    content_type: ContentType = ContentType.unknown
    views: int = 0
    engaged_views: int = 0
    watch_time_minutes: float = 0
    average_view_duration_seconds: float = 0
    average_view_percentage: float = 0
    subscribers_gained: int = 0
    subscribers_lost: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    views_per_day: float = 0
    subscribers_per_1000_views: float = 0
    engagement_per_1000_views: float = 0
    engaged_view_ratio: float | None = None


class SegmentPerformance(BaseModel):
    segment: str
    segment_code: str
    views: int = 0
    engaged_views: int = 0
    watch_time_minutes: float = 0
    view_share: float = 0
    watch_time_share: float = 0


class VideoDetails(BaseModel):
    video_id: str
    title: str
    duration_seconds: int


class AudienceRetentionPoint(BaseModel):
    elapsed_video_time_ratio: float
    audience_watch_ratio: float


class RetentionCheckpoint(BaseModel):
    label: str
    elapsed_seconds: float
    elapsed_ratio: float
    audience_watch_ratio: float


class RetentionEvent(BaseModel):
    event_type: str
    elapsed_seconds: float
    elapsed_ratio: float
    change: float
    audience_watch_ratio: float


class RetentionDiagnosis(BaseModel):
    video_id: str
    title: str
    duration_seconds: int
    curve_area: float
    ending_retention: float
    checkpoints: list[RetentionCheckpoint] = Field(default_factory=list)
    events: list[RetentionEvent] = Field(default_factory=list)


class GrowthRecommendation(BaseModel):
    priority: int
    category: str
    title: str
    rationale: str
    evidence: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    impact: str
    confidence: str
    effort: str


class GrowthAudit(BaseModel):
    generated_at: datetime
    current_period: DateRange
    previous_period: DateRange
    current_summary: ChannelSummary
    comparison: list[MetricDelta]
    videos: list[VideoAnalytics] = Field(default_factory=list)
    top_videos: list[VideoAnalytics]
    top_subscriber_converters: list[VideoAnalytics]
    traffic_sources: list[SegmentPerformance]
    recommendations: list[GrowthRecommendation]


class ChannelForecast(BaseModel):
    history_days: int
    forecast_days: int
    projected_views: int
    projected_net_subscribers: int
    daily_views_slope: float
    confidence: str


class ChannelAnomaly(BaseModel):
    day: date
    metric: str
    value: float
    expected: float
    z_score: float
    direction: str


class ReportingJob(BaseModel):
    job_id: str
    name: str
    report_type_id: str
    create_time: datetime | None = None


class ReportingType(BaseModel):
    report_type_id: str
    name: str
    system_managed: bool = False


class ReportingFile(BaseModel):
    report_id: str
    job_id: str
    start_time: datetime | None = None
    end_time: datetime | None = None
    create_time: datetime | None = None
    download_url: str | None = None


class HistorySnapshotInfo(BaseModel):
    snapshot_id: int
    profile: str
    captured_at: datetime
    period_start: date
    period_end: date
    views: int
    net_subscribers: int


class Experiment(BaseModel):
    experiment_id: int | None = None
    profile: str
    name: str
    hypothesis: str
    start_date: date
    end_date: date | None = None
    status: str = "active"
    video_ids: list[str] = Field(default_factory=list)
    result_notes: str | None = None
    created_at: datetime | None = None


class Profile(BaseModel):
    name: str
    channel_id: str
    channel_title: str
    scopes: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class ResultTable:
    headers: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> ResultTable:
        headers = tuple(item["name"] for item in payload.get("columnHeaders", []))
        rows = tuple(dict(zip(headers, values, strict=False)) for values in payload.get("rows", []))
        return cls(headers=headers, rows=rows)
