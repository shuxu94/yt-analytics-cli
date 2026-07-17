from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv
from rich.console import Console

from .api import GoogleAPIClient
from .auth import CredentialStore, authorize
from .errors import AuthenticationError, YTAnalyticsError
from .models import DateRange, Profile
from .output import OutputFormat, render, render_file
from .service import AnalyticsService

load_dotenv()

app = typer.Typer(no_args_is_help=True, help="YouTube Analytics from your terminal.")
auth_app = typer.Typer(no_args_is_help=True, help="Manage OAuth profiles.")
channel_app = typer.Typer(no_args_is_help=True, help="Inspect channel performance.")
videos_app = typer.Typer(no_args_is_help=True, help="Inspect video performance.")
app.add_typer(auth_app, name="auth")
app.add_typer(channel_app, name="channel")
app.add_typer(videos_app, name="videos")

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


def main() -> None:
    try:
        app(standalone_mode=False)
    except (YTAnalyticsError, ValueError) as exc:
        stderr.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc


if __name__ == "__main__":
    main()
