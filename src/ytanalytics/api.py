from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import httpx
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from .errors import APIError
from .models import (
    ContentType,
    ReportingFile,
    ReportingJob,
    ReportingType,
    ResultTable,
    VideoDetails,
    VideoMetadata,
)

YOUTUBE_DURATION_PATTERN = re.compile(
    r"^PT(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?$"
)


class GoogleAPIClient:
    ANALYTICS_URL = "https://youtubeanalytics.googleapis.com/v2/reports"
    YOUTUBE_URL = "https://www.googleapis.com/youtube/v3"
    REPORTING_URL = "https://youtubereporting.googleapis.com/v1"

    def __init__(self, credentials: Credentials, *, timeout: float = 30) -> None:
        self.credentials = credentials
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        if not self.credentials.valid:
            self.credentials.refresh(Request())
        return {"Authorization": f"Bearer {self.credentials.token}"}

    def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        return self._request("GET", url, params=params)

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = httpx.request(
                method,
                url,
                params=params,
                json=json,
                headers=self._headers(),
                timeout=self.timeout,
            )
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

    def video_metadata(self, video_ids: list[str]) -> dict[str, VideoMetadata]:
        metadata: dict[str, VideoMetadata] = {}
        for offset in range(0, len(video_ids), 50):
            batch = video_ids[offset : offset + 50]
            payload = self._get(
                f"{self.YOUTUBE_URL}/videos",
                {"part": "snippet,contentDetails", "id": ",".join(batch)},
            )
            file_details: dict[str, dict[str, Any]] = {}
            try:
                details_payload = self._get(
                    f"{self.YOUTUBE_URL}/videos",
                    {"part": "fileDetails", "id": ",".join(batch)},
                )
                file_details = {
                    item["id"]: item.get("fileDetails", {})
                    for item in details_payload.get("items", [])
                }
            except APIError:
                # File metadata is only returned for videos owned by the caller. Core
                # analytics remain useful when Google omits or rejects this optional part.
                file_details = {}

            for item in payload.get("items", []):
                duration = parse_youtube_duration(item["contentDetails"]["duration"])
                aspect_ratio = _aspect_ratio(file_details.get(item["id"], {}))
                metadata[item["id"]] = VideoMetadata(
                    video_id=item["id"],
                    title=item["snippet"]["title"],
                    published_at=_parse_datetime(item["snippet"].get("publishedAt")),
                    duration_seconds=duration,
                    aspect_ratio=aspect_ratio,
                    content_type=_content_type(duration, aspect_ratio),
                )
        return metadata

    def reporting_jobs(self) -> list[ReportingJob]:
        payload = self._get(f"{self.REPORTING_URL}/jobs", {})
        return [_reporting_job(item) for item in payload.get("jobs", [])]

    def reporting_types(self) -> list[ReportingType]:
        payload = self._get(f"{self.REPORTING_URL}/reportTypes", {})
        return [
            ReportingType(
                report_type_id=item["id"],
                name=item.get("name", ""),
                system_managed=item.get("systemManaged", False),
            )
            for item in payload.get("reportTypes", [])
        ]

    def create_reporting_job(self, report_type_id: str, name: str) -> ReportingJob:
        payload = self._request(
            "POST",
            f"{self.REPORTING_URL}/jobs",
            json={"reportTypeId": report_type_id, "name": name},
        )
        return _reporting_job(payload)

    def reporting_files(self, job_id: str) -> list[ReportingFile]:
        payload = self._get(f"{self.REPORTING_URL}/jobs/{job_id}/reports", {})
        return [_reporting_file(item, job_id) for item in payload.get("reports", [])]

    def download_reporting_file(self, download_url: str) -> bytes:
        try:
            response = httpx.get(
                download_url,
                headers=self._headers(),
                timeout=self.timeout,
                follow_redirects=True,
            )
            response.raise_for_status()
            return response.content
        except httpx.HTTPError as exc:
            raise APIError(f"Google Reporting API download failed: {exc}") from exc


def parse_youtube_duration(value: str) -> int:
    match = YOUTUBE_DURATION_PATTERN.fullmatch(value)
    if not match:
        raise APIError(f"unsupported YouTube video duration: {value!r}")
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    return hours * 3600 + minutes * 60 + seconds


def _aspect_ratio(file_details: dict[str, Any]) -> float | None:
    streams = file_details.get("videoStreams", [])
    if not streams:
        return None
    value = streams[0].get("aspectRatio")
    return float(value) if value is not None else None


def _content_type(duration_seconds: int, aspect_ratio: float | None) -> ContentType:
    if duration_seconds > 180:
        return ContentType.long_form
    if aspect_ratio is None:
        return ContentType.unknown
    return ContentType.shorts if aspect_ratio < 1 else ContentType.long_form


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _reporting_job(item: dict[str, Any]) -> ReportingJob:
    return ReportingJob(
        job_id=item["id"],
        name=item.get("name", ""),
        report_type_id=item.get("reportTypeId", ""),
        create_time=_parse_datetime(item.get("createTime")),
    )


def _reporting_file(item: dict[str, Any], job_id: str) -> ReportingFile:
    return ReportingFile(
        report_id=item["id"],
        job_id=item.get("jobId", job_id),
        start_time=_parse_datetime(item.get("startTime")),
        end_time=_parse_datetime(item.get("endTime")),
        create_time=_parse_datetime(item.get("createTime")),
        download_url=item.get("downloadUrl"),
    )
