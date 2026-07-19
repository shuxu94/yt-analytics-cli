from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv
from rich.console import Console

from .api import GoogleAPIClient
from .auth import CredentialStore, authorize
from .dashboard import serve_retention_dashboard
from .errors import AuthenticationError, YTAnalyticsError
from .growth_dashboard import serve_growth_dashboard
from .history import HistoryStore
from .models import (
    ContentType,
    DateRange,
    Experiment,
    GrowthAudit,
    Profile,
    RetentionDiagnosis,
    VideoRankMetric,
)
from .output import OutputFormat, render, render_file
from .performance_dashboard import PerformanceDashboardVideo, serve_performance_dashboard
from .service import AnalyticsService

load_dotenv()

app = typer.Typer(no_args_is_help=True, help="YouTube Analytics from your terminal.")
auth_app = typer.Typer(no_args_is_help=True, help="Manage OAuth profiles.")
channel_app = typer.Typer(no_args_is_help=True, help="Inspect channel performance.")
videos_app = typer.Typer(no_args_is_help=True, help="Inspect video performance.")
video_app = typer.Typer(no_args_is_help=True, help="Open reports for one video.")
dashboard_app = typer.Typer(no_args_is_help=True, help="Open local analytics dashboards.")
traffic_app = typer.Typer(no_args_is_help=True, help="Inspect discovery and traffic sources.")
audience_app = typer.Typer(no_args_is_help=True, help="Inspect audience segments.")
shorts_app = typer.Typer(no_args_is_help=True, help="Inspect confirmed vertical Shorts.")
retention_app = typer.Typer(no_args_is_help=True, help="Diagnose audience retention.")
audit_app = typer.Typer(no_args_is_help=True, help="Run evidence-backed channel audits.")
sync_app = typer.Typer(no_args_is_help=True, help="Save analytics to local history.")
history_app = typer.Typer(no_args_is_help=True, help="Inspect local analytics history.")
experiment_app = typer.Typer(no_args_is_help=True, help="Track content experiments.")
reporting_app = typer.Typer(no_args_is_help=True, help="Manage bulk Reporting API jobs.")
app.add_typer(auth_app, name="auth")
app.add_typer(channel_app, name="channel")
app.add_typer(videos_app, name="videos")
app.add_typer(video_app, name="video")
app.add_typer(dashboard_app, name="dashboard")
app.add_typer(traffic_app, name="traffic")
app.add_typer(audience_app, name="audience")
app.add_typer(shorts_app, name="shorts")
app.add_typer(retention_app, name="retention")
app.add_typer(audit_app, name="audit")
app.add_typer(sync_app, name="sync")
app.add_typer(history_app, name="history")
app.add_typer(experiment_app, name="experiment")
app.add_typer(reporting_app, name="reporting")

stdout = Console()
stderr = Console(stderr=True)


def _service(profile: str) -> AnalyticsService:
    credentials = CredentialStore().credentials(profile)
    return AnalyticsService(GoogleAPIClient(credentials))


@auth_app.command("login")
def auth_login(
    profile: Annotated[str, typer.Option(help="Local profile name.")] = "default",
    monetary: Annotated[bool, typer.Option(help="Also request access to revenue metrics.")] = False,
) -> None:
    """Authorize a YouTube channel in the system browser."""
    client_id = os.getenv("YT_CLIENT_ID", "").strip()
    client_secret = os.getenv("YT_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise AuthenticationError(
            "OAuth client configuration is missing; set YT_CLIENT_ID and YT_CLIENT_SECRET in .env"
        )
    credentials = authorize(client_id, client_secret, monetary=monetary)
    client = GoogleAPIClient(credentials)
    channel = client.my_channel()
    data = Profile(
        name=profile,
        channel_id=channel["id"],
        channel_title=channel["title"],
        scopes=list(credentials.scopes or []),
    )
    CredentialStore().save(data, credentials)
    stdout.print(f"Logged in as [bold]{data.channel_title}[/bold] ({data.channel_id})")


@auth_app.command("status")
def auth_status(
    profile: Annotated[str, typer.Option(help="Local profile name.")] = "default",
    format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.table,
) -> None:
    """Show the selected profile and validate its stored credentials."""
    store = CredentialStore()
    data = store.profile(profile)
    store.credentials(profile)
    render(data, format, console=stdout)


@channel_app.command("summary")
def channel_summary(
    period: Annotated[str, typer.Option(help="Date window, such as 28d or lifetime.")] = "28d",
    profile: Annotated[str, typer.Option(help="Local profile name.")] = "default",
    format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.table,
) -> None:
    """Show aggregate channel performance."""
    result = _service(profile).channel_summary(DateRange.from_period(period))
    render(result, format, console=stdout)


@videos_app.command("top")
def videos_top(
    period: Annotated[str, typer.Option(help="Date window, such as 28d or lifetime.")] = "28d",
    limit: Annotated[int, typer.Option(min=1, max=200)] = 10,
    profile: Annotated[str, typer.Option(help="Local profile name.")] = "default",
    format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.table,
) -> None:
    """List top videos ranked by views."""
    result = _service(profile).top_videos(DateRange.from_period(period), limit=limit)
    render(result, format, console=stdout)


@videos_app.command("retention")
def videos_retention(
    video_id: Annotated[str, typer.Argument(help="YouTube video ID.")],
    period: Annotated[str, typer.Option(help="Date window, such as 28d or lifetime.")] = "lifetime",
    profile: Annotated[str, typer.Option(help="Local profile name.")] = "default",
    format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.csv,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Write the retention data to this file."),
    ] = None,
) -> None:
    """Download a video's audience-retention curve."""
    result = _service(profile).audience_retention(video_id, DateRange.from_period(period))
    if output is None:
        render(result, format, console=stdout)
        return
    render_file(result, format, output)
    stderr.print(f"Saved {len(result)} retention points to {output}")


@video_app.command("retention")
def video_retention_dashboard(
    video_id: Annotated[str, typer.Argument(help="YouTube video ID.")],
    period: Annotated[str, typer.Option(help="Date window, such as 28d or lifetime.")] = "lifetime",
    profile: Annotated[str, typer.Option(help="Local profile name.")] = "default",
    open_browser: Annotated[
        bool,
        typer.Option("--open/--no-open", help="Open the dashboard in the default browser."),
    ] = True,
    port: Annotated[
        int,
        typer.Option(min=0, max=65535, help="Local port; use 0 to select an available port."),
    ] = 0,
) -> None:
    """Open a local video player synchronized with audience retention."""
    service = _service(profile)
    video = service.video_details(video_id)
    retention = service.audience_retention(video_id, DateRange.from_period(period))

    def ready(url: str) -> None:
        stdout.print(f"Dashboard for [bold]{video.title}[/bold]: {url}")
        stdout.print("Press Ctrl+C to stop the local dashboard.")

    serve_retention_dashboard(
        video,
        retention,
        port=port,
        open_browser=open_browser,
        on_ready=ready,
    )


@dashboard_app.command("videos")
def videos_performance_dashboard(
    period: Annotated[str, typer.Option(help="Date window, such as 28d or lifetime.")] = "28d",
    profile: Annotated[str, typer.Option(help="Local profile name.")] = "default",
    open_browser: Annotated[
        bool,
        typer.Option("--open/--no-open", help="Open the dashboard in the default browser."),
    ] = True,
    port: Annotated[
        int,
        typer.Option(min=0, max=65535, help="Local port; use 0 to select an available port."),
    ] = 0,
) -> None:
    """Open Top 5 and Bottom 5 videos with synchronized retention."""
    service = _service(profile)
    date_range = DateRange.from_period(period)
    top = service.top_videos(date_range, limit=5)
    top_ids = {item.video_id for item in top}
    bottom = [
        item for item in service.bottom_videos(date_range, limit=10) if item.video_id not in top_ids
    ][:5]
    ranked = [("top", rank, item) for rank, item in enumerate(top, start=1)] + [
        ("bottom", rank, item) for rank, item in enumerate(bottom, start=1)
    ]
    videos = [
        PerformanceDashboardVideo(
            group=group,
            rank=rank,
            details=service.video_details(item.video_id),
            performance=item,
            retention=service.audience_retention(item.video_id, date_range),
        )
        for group, rank, item in ranked
    ]

    def ready(url: str) -> None:
        stdout.print(f"Top 5 / Bottom 5 dashboard: {url}")
        stdout.print("Press Ctrl+C to stop the local dashboard.")

    serve_performance_dashboard(
        videos,
        period,
        port=port,
        open_browser=open_browser,
        on_ready=ready,
    )


@channel_app.command("trend")
def channel_trend(
    period: Annotated[str, typer.Option(help="Date window, such as 90d.")] = "90d",
    interval: Annotated[str, typer.Option(help="Aggregation interval; currently day.")] = "day",
    profile: Annotated[str, typer.Option(help="Local profile name.")] = "default",
    format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.table,
) -> None:
    """Show daily channel momentum."""
    if interval != "day":
        raise ValueError("the supported trend interval is 'day'")
    render(
        _service(profile).channel_trend(DateRange.from_period(period)),
        format,
        console=stdout,
    )


@channel_app.command("compare")
def channel_compare(
    current: Annotated[
        str,
        typer.Option("--current", help="Current window compared with its preceding window."),
    ] = "28d",
    profile: Annotated[str, typer.Option(help="Local profile name.")] = "default",
    format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.table,
) -> None:
    """Compare one period with the immediately preceding equal-length period."""
    render(
        _service(profile).channel_comparison(DateRange.from_period(current)),
        format,
        console=stdout,
    )


@channel_app.command("forecast")
def channel_forecast(
    history: Annotated[
        str, typer.Option(help="Historical window used by the trend model.")
    ] = "90d",
    days: Annotated[int, typer.Option(min=1, max=365)] = 28,
    profile: Annotated[str, typer.Option(help="Local profile name.")] = "default",
    format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.table,
) -> None:
    """Project views and net subscribers with a transparent linear trend model."""
    render(
        _service(profile).channel_forecast(DateRange.from_period(history), forecast_days=days),
        format,
        console=stdout,
    )


@channel_app.command("anomalies")
def channel_anomalies(
    period: Annotated[str, typer.Option(help="Historical window to scan.")] = "90d",
    threshold: Annotated[float, typer.Option(min=1.0, max=10.0)] = 2.0,
    profile: Annotated[str, typer.Option(help="Local profile name.")] = "default",
    format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.table,
) -> None:
    """Find unusually high or low daily views and subscriber changes."""
    render(
        _service(profile).channel_anomalies(DateRange.from_period(period), threshold=threshold),
        format,
        console=stdout,
    )


@videos_app.command("rank")
def videos_rank(
    metric: Annotated[VideoRankMetric, typer.Option(help="Metric used for ranking.")] = (
        VideoRankMetric.views
    ),
    period: Annotated[str, typer.Option(help="Date window, such as 90d.")] = "90d",
    limit: Annotated[int, typer.Option(min=1, max=200)] = 10,
    content_type: Annotated[
        ContentType | None,
        typer.Option(help="Restrict to shorts, long_form, or unknown."),
    ] = None,
    ascending: Annotated[bool, typer.Option(help="Show the lowest values first.")] = False,
    profile: Annotated[str, typer.Option(help="Local profile name.")] = "default",
    format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.table,
) -> None:
    """Rank videos with normalized growth and conversion metrics."""
    render(
        _service(profile).rank_videos(
            DateRange.from_period(period),
            metric=metric,
            limit=limit,
            content_type=content_type,
            descending=not ascending,
        ),
        format,
        console=stdout,
    )


@videos_app.command("compare")
def videos_compare(
    video_ids: Annotated[list[str], typer.Argument(help="Two or more YouTube video IDs.")],
    period: Annotated[str, typer.Option(help="Date window, such as 90d.")] = "90d",
    profile: Annotated[str, typer.Option(help="Local profile name.")] = "default",
    format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.table,
) -> None:
    """Compare normalized performance for multiple videos."""
    render(
        _service(profile).compare_videos(video_ids, DateRange.from_period(period)),
        format,
        console=stdout,
    )


@shorts_app.command("performance")
def shorts_performance(
    period: Annotated[str, typer.Option(help="Date window, such as 28d.")] = "28d",
    metric: Annotated[VideoRankMetric, typer.Option(help="Metric used for ranking.")] = (
        VideoRankMetric.engaged_view_ratio
    ),
    limit: Annotated[int, typer.Option(min=1, max=200)] = 25,
    profile: Annotated[str, typer.Option(help="Local profile name.")] = "default",
    format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.table,
) -> None:
    """Rank confirmed vertical Shorts; unclassified videos are excluded."""
    render(
        _service(profile).shorts_performance(
            DateRange.from_period(period), limit=limit, metric=metric
        ),
        format,
        console=stdout,
    )


@traffic_app.command("sources")
def traffic_sources(
    period: Annotated[str, typer.Option(help="Date window, such as 28d.")] = "28d",
    profile: Annotated[str, typer.Option(help="Local profile name.")] = "default",
    format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.table,
) -> None:
    """Show how viewers discovered the channel's videos."""
    render(
        _service(profile).traffic_sources(DateRange.from_period(period)),
        format,
        console=stdout,
    )


@traffic_app.command("search")
def traffic_search(
    period: Annotated[str, typer.Option(help="Date window, such as 90d.")] = "90d",
    limit: Annotated[int, typer.Option(min=1, max=25)] = 25,
    profile: Annotated[str, typer.Option(help="Local profile name.")] = "default",
    format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.table,
) -> None:
    """Show leading YouTube search terms."""
    render(
        _service(profile).traffic_search(DateRange.from_period(period), limit=limit),
        format,
        console=stdout,
    )


@audience_app.command("devices")
def audience_devices(
    period: Annotated[str, typer.Option(help="Date window, such as 28d.")] = "28d",
    profile: Annotated[str, typer.Option(help="Local profile name.")] = "default",
    format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.table,
) -> None:
    """Break performance down by device type."""
    render(
        _service(profile).audience_devices(DateRange.from_period(period)),
        format,
        console=stdout,
    )


@audience_app.command("geography")
def audience_geography(
    period: Annotated[str, typer.Option(help="Date window, such as 90d.")] = "90d",
    limit: Annotated[int, typer.Option(min=1, max=200)] = 25,
    profile: Annotated[str, typer.Option(help="Local profile name.")] = "default",
    format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.table,
) -> None:
    """Break performance down by country."""
    render(
        _service(profile).audience_geography(DateRange.from_period(period), limit=limit),
        format,
        console=stdout,
    )


@audience_app.command("subscribers")
def audience_subscribers(
    period: Annotated[str, typer.Option(help="Date window, such as 28d.")] = "28d",
    profile: Annotated[str, typer.Option(help="Local profile name.")] = "default",
    format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.table,
) -> None:
    """Compare subscribed and unsubscribed viewing."""
    render(
        _service(profile).audience_subscribers(DateRange.from_period(period)),
        format,
        console=stdout,
    )


@retention_app.command("diagnose")
def retention_diagnose(
    video_id: Annotated[str, typer.Argument(help="YouTube video ID.")],
    period: Annotated[str, typer.Option(help="Date window or lifetime.")] = "lifetime",
    profile: Annotated[str, typer.Option(help="Local profile name.")] = "default",
    format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.table,
) -> None:
    """Find hook checkpoints, drop-offs, and rewatch spikes."""
    diagnosis = _service(profile).retention_diagnosis(video_id, DateRange.from_period(period))
    _render_retention_diagnosis(diagnosis, format)


@audit_app.command("grow")
def audit_grow(
    period: Annotated[str, typer.Option(help="Current audit window.")] = "90d",
    compare: Annotated[
        str,
        typer.Option(help="Comparison mode; currently only previous is supported."),
    ] = "previous",
    profile: Annotated[str, typer.Option(help="Local profile name.")] = "default",
    format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.table,
) -> None:
    """Run an evidence-backed channel growth audit."""
    if compare != "previous":
        raise ValueError("the supported comparison mode is 'previous'")
    audit = _service(profile).growth_audit(DateRange.from_period(period))
    _render_growth_audit(audit, format)


@dashboard_app.command("grow")
def growth_dashboard(
    period: Annotated[str, typer.Option(help="Current audit window.")] = "90d",
    profile: Annotated[str, typer.Option(help="Local profile name.")] = "default",
    open_browser: Annotated[
        bool,
        typer.Option("--open/--no-open", help="Open the dashboard in the default browser."),
    ] = True,
    port: Annotated[
        int,
        typer.Option(min=0, max=65535, help="Local port; 0 selects an available port."),
    ] = 0,
) -> None:
    """Open the interactive growth audit dashboard."""
    service = _service(profile)
    date_range = DateRange.from_period(period)
    audit = service.growth_audit(date_range)
    trend = service.channel_trend(date_range)

    def ready(url: str) -> None:
        stdout.print(f"Growth dashboard: {url}")
        stdout.print("Press Ctrl+C to stop the local dashboard.")

    serve_growth_dashboard(
        audit,
        trend,
        port=port,
        open_browser=open_browser,
        on_ready=ready,
    )


@sync_app.command("snapshot")
def sync_snapshot(
    period: Annotated[str, typer.Option(help="Audit window to save.")] = "90d",
    profile: Annotated[str, typer.Option(help="Local profile name.")] = "default",
    format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.table,
) -> None:
    """Save a complete growth-audit snapshot to local SQLite history."""
    audit = _service(profile).growth_audit(DateRange.from_period(period))
    render(HistoryStore().save_snapshot(profile, audit), format, console=stdout)


@history_app.command("list")
def history_list(
    profile: Annotated[str, typer.Option(help="Local profile name.")] = "default",
    limit: Annotated[int, typer.Option(min=1, max=200)] = 25,
    format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.table,
) -> None:
    """List locally saved audit snapshots."""
    render(HistoryStore().list_snapshots(profile, limit=limit), format, console=stdout)


@experiment_app.command("add")
def experiment_add(
    name: Annotated[str, typer.Argument(help="Short experiment name.")],
    hypothesis: Annotated[str, typer.Option(help="Falsifiable expected outcome.")],
    video_ids: Annotated[
        list[str] | None,
        typer.Option("--video", help="Video ID associated with the experiment; repeatable."),
    ] = None,
    start: Annotated[
        str | None,
        typer.Option(help="Start date in YYYY-MM-DD format; defaults to today."),
    ] = None,
    profile: Annotated[str, typer.Option(help="Local profile name.")] = "default",
    format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.table,
) -> None:
    """Record a content experiment before evaluating its result."""
    result = HistoryStore().add_experiment(
        Experiment(
            profile=profile,
            name=name,
            hypothesis=hypothesis,
            start_date=date.fromisoformat(start) if start else date.today(),
            video_ids=video_ids or [],
        )
    )
    render(result, format, console=stdout)


@experiment_app.command("list")
def experiment_list(
    profile: Annotated[str, typer.Option(help="Local profile name.")] = "default",
    status: Annotated[str | None, typer.Option(help="Filter by active or completed.")] = None,
    format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.table,
) -> None:
    """List content experiments."""
    render(
        HistoryStore().list_experiments(profile, status=status),
        format,
        console=stdout,
    )


@experiment_app.command("close")
def experiment_close(
    experiment_id: Annotated[int, typer.Argument(min=1)],
    result_notes: Annotated[str, typer.Option("--result", help="Observed outcome.")],
    format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.table,
) -> None:
    """Close an experiment and record its outcome."""
    render(
        HistoryStore().close_experiment(experiment_id, result_notes),
        format,
        console=stdout,
    )


@reporting_app.command("jobs")
def reporting_jobs(
    profile: Annotated[str, typer.Option(help="Local profile name.")] = "default",
    format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.table,
) -> None:
    """List bulk YouTube Reporting API jobs."""
    render(_service(profile).client.reporting_jobs(), format, console=stdout)


@reporting_app.command("types")
def reporting_types(
    contains: Annotated[
        str | None,
        typer.Option(help="Only show report type IDs or names containing this text."),
    ] = None,
    profile: Annotated[str, typer.Option(help="Local profile name.")] = "default",
    format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.table,
) -> None:
    """List available bulk report types, including channel reach reports."""
    results = _service(profile).client.reporting_types()
    if contains:
        needle = contains.casefold()
        results = [
            item
            for item in results
            if needle in item.report_type_id.casefold() or needle in item.name.casefold()
        ]
    render(results, format, console=stdout)


@reporting_app.command("create")
def reporting_create(
    report_type: Annotated[str, typer.Option(help="Reporting API report type ID.")],
    name: Annotated[str, typer.Option(help="Human-readable job name.")],
    profile: Annotated[str, typer.Option(help="Local profile name.")] = "default",
    format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.table,
) -> None:
    """Create a scheduled bulk Reporting API job."""
    render(
        _service(profile).client.create_reporting_job(report_type, name),
        format,
        console=stdout,
    )


@reporting_app.command("reports")
def reporting_reports(
    job_id: Annotated[str, typer.Argument(help="Reporting API job ID.")],
    profile: Annotated[str, typer.Option(help="Local profile name.")] = "default",
    format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.table,
) -> None:
    """List downloadable reports produced for a job."""
    render(
        _service(profile).client.reporting_files(job_id),
        format,
        console=stdout,
    )


@reporting_app.command("download")
def reporting_download(
    download_url: Annotated[str, typer.Argument(help="Download URL returned by reports.")],
    output: Annotated[Path, typer.Option("--output", "-o", help="Destination CSV or GZip file.")],
    profile: Annotated[str, typer.Option(help="Local profile name.")] = "default",
) -> None:
    """Download one generated bulk report."""
    if not output.parent.exists():
        raise ValueError(f"output directory does not exist: {output.parent}")
    output.write_bytes(_service(profile).client.download_reporting_file(download_url))
    stderr.print(f"Saved Reporting API file to {output}")


def _render_retention_diagnosis(diagnosis: RetentionDiagnosis, format: OutputFormat) -> None:
    if format != OutputFormat.table:
        render(diagnosis, format, console=stdout)
        return
    stdout.print(f"[bold]{diagnosis.title}[/bold]")
    stdout.print(
        f"Curve area: {diagnosis.curve_area:.1%} · Ending retention: "
        f"{diagnosis.ending_retention:.1%}"
    )
    stdout.print("\n[bold]Checkpoints[/bold]")
    render(diagnosis.checkpoints, OutputFormat.table, console=stdout)
    stdout.print("\n[bold]Largest changes[/bold]")
    render(diagnosis.events, OutputFormat.table, console=stdout)


def _render_growth_audit(audit: GrowthAudit, format: OutputFormat) -> None:
    if format != OutputFormat.table:
        render(audit, format, console=stdout)
        return
    summary = audit.current_summary
    stdout.print(
        f"[bold]Growth audit · {audit.current_period.start} to {audit.current_period.end}[/bold]"
    )
    stdout.print(
        f"{summary.views:,} views · {summary.watch_time_minutes / 60:,.1f} watch hours · "
        f"{summary.net_subscribers:+,} net subscribers"
    )
    stdout.print("\n[bold]Period comparison[/bold]")
    render(audit.comparison, OutputFormat.table, console=stdout)
    stdout.print("\n[bold]Recommended next moves[/bold]")
    for item in audit.recommendations:
        stdout.print(f"\n[bold]{item.priority}. {item.title}[/bold]")
        stdout.print(item.rationale)
        for action in item.actions:
            stdout.print(f"  • {action}")
        stdout.print(
            f"[dim]Impact: {item.impact} · Confidence: {item.confidence} · "
            f"Effort: {item.effort}[/dim]"
        )


def main() -> None:
    try:
        app(standalone_mode=False)
    except (YTAnalyticsError, ValueError) as exc:
        stderr.print(f"[red]Error:[/red] {exc}")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
