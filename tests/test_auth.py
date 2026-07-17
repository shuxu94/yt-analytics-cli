from unittest.mock import Mock, patch

from ytanalytics.auth import ANALYTICS_SCOPE, YOUTUBE_SCOPE, authorize


@patch("ytanalytics.auth.InstalledAppFlow")
def test_authorize_builds_installed_app_config(installed_app_flow: Mock) -> None:
    flow = installed_app_flow.from_client_config.return_value

    authorize("client-id", "client-secret")

    installed_app_flow.from_client_config.assert_called_once_with(
        {
            "installed": {
                "client_id": "client-id",
                "client_secret": "client-secret",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        },
        scopes=[ANALYTICS_SCOPE, YOUTUBE_SCOPE],
    )
    flow.run_local_server.assert_called_once_with(
        host="localhost",
        port=0,
        open_browser=True,
        prompt="select_account",
    )
