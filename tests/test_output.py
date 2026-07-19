from ytanalytics.models import AudienceRetentionPoint
from ytanalytics.output import OutputFormat, render_file


def test_render_file_writes_retention_csv(tmp_path) -> None:
    path = tmp_path / "retention.csv"

    render_file(
        [
            AudienceRetentionPoint(
                elapsed_video_time_ratio=0.01,
                audience_watch_ratio=1.1,
            )
        ],
        OutputFormat.csv,
        path,
    )

    assert path.read_text() == ("elapsed_video_time_ratio,audience_watch_ratio\n0.01,1.1\n")
