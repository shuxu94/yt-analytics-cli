from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv
from rich.console import Console

from .api import GoogleAPIClient
from .auth import CredentialStore, authorize
from .dashboard import serve_retention_dashboard
from .errors import AuthenticationError, YTAnalyticsError
from .models import DateRange, Profile
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
app.add_typer(auth_app, name="auth")
app.add_typer(channel_app, name="channel")
app.add_typer(videos_app, name="videos")
app.add_typer(video_app, name="video")
app.add_typer(dashboard_app, name="dashboard")

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
            "OAuth client configuration is missing; set YT_CLIENT_ID and "
            "YT_CLIENT_SECRET in .env"
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
        item
        for item in service.bottom_videos(date_range, limit=10)
        if item.video_id not in top_ids
    ][:5]
    ranked = [
        ("top", rank, item) for rank, item in enumerate(top, start=1)
    ] + [
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


def main() -> None:
    try:
        app(standalone_mode=False)
    except (YTAnalyticsError, ValueError) as exc:
        stderr.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc


if __name__ == "__main__":
    main()
