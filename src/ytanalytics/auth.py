from __future__ import annotations

import json
from pathlib import Path

import keyring
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from .errors import AuthenticationError
from .models import Profile

ANALYTICS_SCOPE = "https://www.googleapis.com/auth/yt-analytics.readonly"
YOUTUBE_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
MONETARY_SCOPE = "https://www.googleapis.com/auth/yt-analytics-monetary.readonly"
DEFAULT_SCOPES = [ANALYTICS_SCOPE, YOUTUBE_SCOPE]
KEYRING_SERVICE = "ytanalytics-cli"


class CredentialStore:
    """Stores refreshable credentials in the OS keychain and non-secret profile metadata on disk."""

    def __init__(self, config_dir: Path | None = None) -> None:
        self.config_dir = config_dir or Path.home() / ".config" / "ytanalytics"
        self.profiles_path = self.config_dir / "profiles.json"

    def save(self, profile: Profile, credentials: Credentials) -> None:
        profiles = self._read_profiles()
        profiles[profile.name] = profile.model_dump(mode="json")
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.profiles_path.write_text(json.dumps(profiles, indent=2) + "\n", encoding="utf-8")
        keyring.set_password(KEYRING_SERVICE, profile.name, credentials.to_json())

    def profile(self, name: str) -> Profile:
        data = self._read_profiles().get(name)
        if data is None:
            raise AuthenticationError(f"profile {name!r} does not exist; run 'yt auth login'")
        return Profile.model_validate(data)

    def credentials(self, name: str) -> Credentials:
        raw = keyring.get_password(KEYRING_SERVICE, name)
        if not raw:
            raise AuthenticationError(f"credentials for profile {name!r} were not found")
        credentials = Credentials.from_authorized_user_info(json.loads(raw))
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            keyring.set_password(KEYRING_SERVICE, name, credentials.to_json())
        if not credentials.valid:
            raise AuthenticationError(f"credentials for profile {name!r} are invalid; log in again")
        return credentials

    def _read_profiles(self) -> dict[str, dict]:
        if not self.profiles_path.exists():
            return {}
        try:
            return json.loads(self.profiles_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise AuthenticationError(f"could not read {self.profiles_path}: {exc}") from exc


def authorize(client_id: str, client_secret: str, *, monetary: bool = False) -> Credentials:
    scopes = [*DEFAULT_SCOPES, *([MONETARY_SCOPE] if monetary else [])]
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, scopes=scopes)
    return flow.run_local_server(
        host="localhost",
        port=0,
        open_browser=True,
        prompt="select_account",
    )
