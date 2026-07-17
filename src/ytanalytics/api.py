from __future__ import annotations

import re
from typing import Any

import httpx
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from .errors import APIError
from .models import ResultTable, VideoDetails

YOUTUBE_DURATION_PATTERN = re.compile(
    r"^PT(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?$"
)


class GoogleAPIClient:
    ANALYTICS_URL = "https://youtubeanalytics.googleapis.com/v2/reports"
    YOUTUBE_URL = "https://www.googleapis.com/youtube/v3"

    def __init__(self, credentials: Credentials, *, timeout: float = 30) -> None:
        self.credentials = credentials
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        if not self.credentials.valid:
            self.credentials.refresh(Request())
        return {"Authorization": f"Bearer {self.credentials.token}"}

    def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            response = httpx.get(url, params=params, headers=self._headers(), timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            try:
                detail = exc.response.json().get("error", {}).get("message")
            except (ValueError, AttributeError):
                detail = None
            message = detail or f"Google API returned HTTP {exc.response.status_code}"
            raise APIError(message) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise APIError(f"Google API request failed: {exc}") from exc

    def analytics_report(self, **params: Any) -> ResultTable:
        payload = self._get(self.ANALYTICS_URL, params)
        return ResultTable.from_api(payload)

    def my_channel(self) -> dict[str, str]:
        payload = self._get(f"{self.YOUTUBE_URL}/channels", {"part": "id,snippet", "mine": "true"})
        items = payload.get("items", [])
        if not items:
            raise APIError("the signed-in Google account does not have a YouTube channel")
        return {"id": items[0]["id"], "title": items[0]["snippet"]["title"]}

    def video_titles(self, video_ids: list[str]) -> dict[str, str]:
        titles: dict[str, str] = {}
        for offset in range(0, len(video_ids), 50):
            batch = video_ids[offset : offset + 50]
            payload = self._get(
                f"{self.YOUTUBE_URL}/videos", {"part": "snippet", "id": ",".join(batch)}
            )
            titles.update(
                {item["id"]: item["snippet"]["title"] for item in payload.get("items", [])}
            )
        return titles

    def video_details(self, video_id: str) -> VideoDetails:
        payload = self._get(
            f"{self.YOUTUBE_URL}/videos",
            {"part": "snippet,contentDetails", "id": video_id},
        )
        items = payload.get("items", [])
        if not items:
            raise APIError(f"video {video_id!r} was not found or is not accessible")
        item = items[0]
        return VideoDetails(
            video_id=item["id"],
            title=item["snippet"]["title"],
            duration_seconds=parse_youtube_duration(item["contentDetails"]["duration"]),
        )


def parse_youtube_duration(value: str) -> int:
    match = YOUTUBE_DURATION_PATTERN.fullmatch(value)
    if not match:
        raise APIError(f"unsupported YouTube video duration: {value!r}")
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    return hours * 3600 + minutes * 60 + seconds
