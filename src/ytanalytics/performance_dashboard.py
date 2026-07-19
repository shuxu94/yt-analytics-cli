from __future__ import annotations

import json
import webbrowser
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from importlib.resources import files

from .dashboard import create_local_server
from .models import AudienceRetentionPoint, VideoDetails, VideoPerformance

WEB_ROOT = files("ytanalytics").joinpath("web", "performance")


@dataclass(frozen=True)
class PerformanceDashboardVideo:
    group: str
    rank: int
    details: VideoDetails
    performance: VideoPerformance
    retention: Sequence[AudienceRetentionPoint]


def performance_dashboard_payload(videos: Sequence[PerformanceDashboardVideo], period: str) -> dict:
    if not videos:
        raise ValueError("the dashboard requires at least one video")
    return {
        "period": period,
        "videos": [
            {
                "group": item.group,
                "rank": item.rank,
                "videoId": item.details.video_id,
                "title": item.details.title,
                "durationSeconds": item.details.duration_seconds,
                "views": item.performance.views,
                "watchTimeMinutes": item.performance.watch_time_minutes,
                "averageViewDurationSeconds": item.performance.average_view_duration_seconds,
                "subscribersGained": item.performance.subscribers_gained,
                "retention": [
                    {
                        "elapsedRatio": point.elapsed_video_time_ratio,
                        "watchRatio": point.audience_watch_ratio,
                    }
                    for point in item.retention
                ],
            }
            for item in videos
        ],
    }


def build_performance_dashboard() -> str:
    return WEB_ROOT.joinpath("index.html").read_text(encoding="utf-8")


def create_performance_dashboard_server(
    videos: Sequence[PerformanceDashboardVideo],
    period: str,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
):
    payload = json.dumps(
        performance_dashboard_payload(videos, period),
        separators=(",", ":"),
    ).encode()
    assets = {
        "/assets/styles.css": (
            WEB_ROOT.joinpath("styles.css").read_bytes(),
            "text/css; charset=utf-8",
        ),
        "/assets/app.js": (
            WEB_ROOT.joinpath("app.js").read_bytes(),
            "text/javascript; charset=utf-8",
        ),
        "/api/dashboard": (payload, "application/json; charset=utf-8"),
    }
    return create_local_server(
        build_performance_dashboard(),
        host=host,
        port=port,
        assets=assets,
    )


def serve_performance_dashboard(
    videos: Sequence[PerformanceDashboardVideo],
    period: str,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    open_browser: bool = True,
    on_ready: Callable[[str], None] | None = None,
) -> None:
    server, url = create_performance_dashboard_server(
        videos,
        period,
        host=host,
        port=port,
    )
    if on_ready is not None:
        on_ready(url)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
