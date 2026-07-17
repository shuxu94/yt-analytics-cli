from threading import Thread
from urllib.request import urlopen

from ytanalytics.dashboard import build_retention_dashboard, create_dashboard_server
from ytanalytics.models import AudienceRetentionPoint, VideoDetails


def dashboard_data() -> tuple[VideoDetails, list[AudienceRetentionPoint]]:
    return (
        VideoDetails(video_id="abc123", title="Example </script> video", duration_seconds=28),
        [
            AudienceRetentionPoint(
                elapsed_video_time_ratio=0.01,
                audience_watch_ratio=1.2,
            ),
            AudienceRetentionPoint(
                elapsed_video_time_ratio=1.0,
                audience_watch_ratio=0.45,
            ),
        ],
    )


def test_build_retention_dashboard_embeds_player_and_safe_data() -> None:
    video, retention = dashboard_data()

    page = build_retention_dashboard(video, retention)

    assert 'src="https://www.youtube.com/iframe_api"' in page
    assert '"videoId":"abc123"' in page
    assert '"durationSeconds":28' in page
    assert "Example </script> video" not in page
    assert "Example \\u003c/script> video" in page
    assert "player.seekTo(safe, true)" in page


def test_dashboard_server_serves_page_and_security_policy() -> None:
    video, retention = dashboard_data()
    server, url = create_dashboard_server(video, retention)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urlopen(url, timeout=2) as response:  # noqa: S310
            body = response.read().decode()
            policy = response.headers["Content-Security-Policy"]
        assert response.status == 200
        assert "YouTube retention dashboard" in body
        assert "https://www.youtube.com" in policy
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
