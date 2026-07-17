from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DateRange(BaseModel):
    model_config = ConfigDict(frozen=True)

    start: date
    end: date

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


class VideoPerformance(BaseModel):
    video_id: str
    title: str | None = None
    views: int = 0
    watch_time_minutes: float = 0
    average_view_duration_seconds: float = 0
    subscribers_gained: int = 0


class AudienceRetentionPoint(BaseModel):
    elapsed_video_time_ratio: float
    audience_watch_ratio: float


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
