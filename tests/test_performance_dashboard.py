import json
from threading import Thread
from urllib.request import urlopen

from ytanalytics.models import AudienceRetentionPoint, VideoDetails, VideoPerformance
from ytanalytics.performance_dashboard import (
    PerformanceDashboardVideo,
    build_performance_dashboard,
    create_performance_dashboard_server,
    performance_dashboard_payload,
)


def test_build_performance_dashboard_embeds_top_and_bottom_videos() -> None:
    top = PerformanceDashboardVideo(
        group="top",
        rank=1,
        details=VideoDetails(video_id="top1", title="Top video", duration_seconds=28),
        performance=VideoPerformance(video_id="top1", title="Top video", views=1000),
        retention=[AudienceRetentionPoint(elapsed_video_time_ratio=1, audience_watch_ratio=0.5)],
    )
    bottom = PerformanceDashboardVideo(
        group="bottom",
        rank=1,
        details=VideoDetails(video_id="bottom1", title="Bottom video", duration_seconds=30),
        performance=VideoPerformance(video_id="bottom1", title="Bottom video", views=2),
        retention=[],
    )

    page = build_performance_dashboard()
    payload = performance_dashboard_payload([top, bottom], "28d")

    assert payload["period"] == "28d"
    assert payload["videos"][0]["group"] == "top"
    assert payload["videos"][1]["group"] == "bottom"
    assert payload["videos"][0]["videoId"] == "top1"
    assert payload["videos"][1]["videoId"] == "bottom1"
    assert '<link rel="stylesheet" href="/assets/styles.css">' in page
    assert '<script src="/assets/app.js"></script>' in page
    assert "Top 5 and Bottom 5" in page


def test_performance_frontend_assets_and_data_endpoint() -> None:
    video = PerformanceDashboardVideo(
        group="top",
        rank=1,
        details=VideoDetails(video_id="top1", title="Top video", duration_seconds=28),
        performance=VideoPerformance(video_id="top1", title="Top video", views=1000),
        retention=[],
    )
    server, url = create_performance_dashboard_server([video], "28d")
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urlopen(f"{url}api/dashboard", timeout=2) as response:  # noqa: S310
            payload = json.load(response)
        with urlopen(f"{url}assets/app.js", timeout=2) as response:  # noqa: S310
            javascript = response.read().decode()
        with urlopen(f"{url}assets/styles.css", timeout=2) as response:  # noqa: S310
            stylesheet = response.read().decode()
        assert payload["videos"][0]["videoId"] == "top1"
        assert "player.cueVideoById" in javascript
        assert ".video-choice" in stylesheet
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
