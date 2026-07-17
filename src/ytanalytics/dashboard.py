# ruff: noqa: E501
from __future__ import annotations

import json
import webbrowser
from collections.abc import Callable, Mapping, Sequence
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .models import AudienceRetentionPoint, VideoDetails

DATA_PLACEHOLDER = "__YTANALYTICS_DASHBOARD_DATA__"


def build_retention_dashboard(
    video: VideoDetails,
    retention: Sequence[AudienceRetentionPoint],
) -> str:
    if video.duration_seconds < 1:
        raise ValueError("video duration must be at least one second")
    if not retention:
        raise ValueError("YouTube returned no audience-retention data for this video")
    payload = {
        "videoId": video.video_id,
        "title": video.title,
        "durationSeconds": video.duration_seconds,
        "retention": [
            {
                "elapsedRatio": point.elapsed_video_time_ratio,
                "watchRatio": point.audience_watch_ratio,
            }
            for point in retention
        ],
    }
    encoded = json.dumps(payload, separators=(",", ":")).replace("<", "\\u003c")
    return DASHBOARD_HTML.replace(DATA_PLACEHOLDER, encoded)


def create_dashboard_server(
    video: VideoDetails,
    retention: Sequence[AudienceRetentionPoint],
    *,
    host: str = "127.0.0.1",
    port: int = 0,
) -> tuple[ThreadingHTTPServer, str]:
    return create_local_server(
        build_retention_dashboard(video, retention),
        host=host,
        port=port,
    )


def create_local_server(
    html: str,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    assets: Mapping[str, tuple[bytes, str]] | None = None,
) -> tuple[ThreadingHTTPServer, str]:
    page = html.encode()
    static_assets = dict(assets or {})

    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            path = self.path.partition("?")[0]
            if path == "/healthz":
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"ok")
                return
            if path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return
            if path in static_assets:
                body, content_type = static_assets[path]
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(body)
                return
            if path != "/":
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; "
                "frame-src https://www.youtube.com https://www.youtube-nocookie.com; "
                "script-src 'self' 'unsafe-inline' https://www.youtube.com; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https://i.ytimg.com; "
                "connect-src 'self' https://www.youtube.com https://www.youtube-nocookie.com;",
            )
            self.end_headers()
            self.wfile.write(page)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer((host, port), DashboardHandler)
    actual_port = server.server_address[1]
    return server, f"http://{host}:{actual_port}/"


def serve_retention_dashboard(
    video: VideoDetails,
    retention: Sequence[AudienceRetentionPoint],
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    open_browser: bool = True,
    on_ready: Callable[[str], None] | None = None,
) -> None:
    server, url = create_dashboard_server(video, retention, host=host, port=port)
    if on_ready is not None:
        on_ready(url)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>YouTube retention dashboard</title>
  <style>
    :root {
      color-scheme: dark;
      --background: #0b0d12;
      --surface: #141821;
      --surface-raised: #1b2130;
      --foreground: #f4f6fb;
      --muted: #9da7b8;
      --border: #293142;
      --accent: #ff4e65;
      --accent-soft: rgba(255, 78, 101, 0.16);
      --grid: rgba(157, 167, 184, 0.18);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--background);
      color: var(--foreground);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    button, input { font: inherit; }
    button:focus-visible, input:focus-visible { outline: 2px solid var(--foreground); outline-offset: 3px; }
    .shell { width: min(1440px, 100%); margin: 0 auto; padding: 28px; }
    .header { display: flex; justify-content: space-between; gap: 24px; align-items: end; margin-bottom: 22px; }
    .eyebrow { margin: 0 0 7px; color: var(--accent); font-size: 12px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
    h1 { margin: 0; max-width: 920px; font-size: clamp(24px, 4vw, 42px); line-height: 1.08; letter-spacing: -.03em; }
    .period { flex: 0 0 auto; color: var(--muted); font-size: 14px; }
    .workspace { display: grid; grid-template-columns: minmax(360px, .88fr) minmax(480px, 1.35fr); gap: 20px; align-items: start; }
    .panel { background: var(--surface); border: 1px solid var(--border); border-radius: 18px; overflow: hidden; }
    .player-wrap { background: #000; aspect-ratio: 16 / 9; }
    #player { width: 100%; height: 100%; }
    .player-footer { padding: 15px 17px; display: flex; justify-content: space-between; gap: 16px; align-items: center; }
    .player-status { color: var(--muted); font-size: 13px; }
    .retention-live { color: var(--foreground); font-variant-numeric: tabular-nums; font-weight: 650; }
    .chart-panel { padding: 18px; }
    .chart-header { display: flex; justify-content: space-between; gap: 20px; align-items: baseline; margin-bottom: 6px; }
    .chart-header h2 { margin: 0; font-size: 18px; }
    .current-point { color: var(--muted); font-size: 13px; font-variant-numeric: tabular-nums; }
    .chart-wrap { position: relative; width: 100%; }
    #retention-chart { display: block; width: 100%; height: auto; touch-action: none; }
    .axis, .tick { stroke: var(--border); stroke-width: 1; vector-effect: non-scaling-stroke; }
    .grid { stroke: var(--grid); stroke-width: 1; vector-effect: non-scaling-stroke; }
    .reference { stroke: var(--muted); stroke-width: 1; stroke-dasharray: 5 5; opacity: .7; vector-effect: non-scaling-stroke; }
    .retention-line { fill: none; stroke: var(--accent); stroke-width: 3; stroke-linecap: round; stroke-linejoin: round; vector-effect: non-scaling-stroke; }
    .sample { fill: var(--accent); }
    .playhead { stroke: var(--foreground); stroke-width: 2; vector-effect: non-scaling-stroke; }
    .playhead-dot { fill: var(--accent); stroke: var(--foreground); stroke-width: 2; vector-effect: non-scaling-stroke; }
    .hover-line { stroke: var(--muted); stroke-width: 1; vector-effect: non-scaling-stroke; }
    .axis-text { fill: var(--muted); font-size: 11px; }
    .hit-area { fill: transparent; cursor: crosshair; }
    .tooltip { position: absolute; display: none; pointer-events: none; padding: 8px 10px; background: var(--surface-raised); border: 1px solid var(--border); border-radius: 9px; color: var(--foreground); font-size: 12px; line-height: 1.45; box-shadow: 0 12px 32px rgba(0,0,0,.28); }
    .controls { display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 12px; margin-top: 10px; }
    .play-button { min-width: 76px; border: 0; border-radius: 9px; padding: 9px 14px; background: var(--foreground); color: var(--background); font-weight: 700; cursor: pointer; }
    .timeline { width: 100%; accent-color: var(--accent); cursor: pointer; }
    .clock { min-width: 92px; color: var(--muted); text-align: right; font-size: 13px; font-variant-numeric: tabular-nums; }
    .hint { margin: 11px 0 0; color: var(--muted); font-size: 12px; }
    .loading { height: 100%; display: grid; place-content: center; color: #fff; font-size: 14px; }
    @media (max-width: 960px) {
      .workspace { grid-template-columns: 1fr; }
      .header { align-items: start; flex-direction: column; }
      .period { order: -1; }
    }
    @media (max-width: 560px) {
      .shell { padding: 18px 12px; }
      .chart-panel { padding: 13px; }
      .controls { grid-template-columns: auto 1fr; }
      .clock { grid-column: 1 / -1; text-align: left; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header class="header">
      <div>
        <p class="eyebrow">YouTube retention</p>
        <h1 id="video-title"></h1>
      </div>
      <div class="period">Authenticated channel analytics</div>
    </header>
    <div class="workspace">
      <section class="panel" aria-label="YouTube video player">
        <div class="player-wrap"><div id="player"><div class="loading">Loading YouTube player…</div></div></div>
        <div class="player-footer">
          <span class="player-status" id="player-status">Connecting player…</span>
          <span class="retention-live" id="retention-live">—</span>
        </div>
      </section>
      <section class="panel chart-panel" aria-label="Synchronized audience retention">
        <div class="chart-header">
          <h2>Audience retention</h2>
          <span class="current-point" id="current-point">0:00 · —</span>
        </div>
        <div class="chart-wrap">
          <svg id="retention-chart" viewBox="0 0 760 390" role="img" aria-labelledby="chart-title chart-description">
            <title id="chart-title">Audience retention synchronized with video playback</title>
            <desc id="chart-description">The vertical playhead follows the YouTube player's current time. Click the graph to seek the video.</desc>
          </svg>
          <div class="tooltip" id="tooltip"></div>
        </div>
        <div class="controls">
          <button class="play-button" id="play-button" type="button" disabled>Play</button>
          <input class="timeline" id="timeline" type="range" min="0" step="0.05" value="0" aria-label="Seek video">
          <output class="clock" id="clock">0:00 / 0:00</output>
        </div>
        <p class="hint">Click anywhere on the graph to seek. Retention may exceed 100% when viewers replay a segment.</p>
      </section>
    </div>
  </main>
  <script>
    const dashboardData = __YTANALYTICS_DASHBOARD_DATA__;
    const duration = dashboardData.durationSeconds;
    const timePoints = dashboardData.retention
      .map(point => [point.elapsedRatio * duration, point.watchRatio * 100])
      .sort((a, b) => a[0] - b[0]);
    const title = document.getElementById("video-title");
    const svg = document.getElementById("retention-chart");
    const tooltip = document.getElementById("tooltip");
    const playButton = document.getElementById("play-button");
    const timeline = document.getElementById("timeline");
    const clock = document.getElementById("clock");
    const currentPoint = document.getElementById("current-point");
    const retentionLive = document.getElementById("retention-live");
    const playerStatus = document.getElementById("player-status");
    const ns = "http://www.w3.org/2000/svg";
    const W = 760, H = 390;
    const margin = {top: 16, right: 20, bottom: 48, left: 56};
    const innerWidth = W - margin.left - margin.right;
    const innerHeight = H - margin.top - margin.bottom;
    const maxValue = Math.max(...timePoints.map(point => point[1]), 100);
    const yMax = Math.max(100, Math.ceil(maxValue / 25) * 25);
    const x = second => margin.left + Math.max(0, Math.min(duration, second)) / duration * innerWidth;
    const y = value => margin.top + (1 - value / yMax) * innerHeight;
    let player = null;
    let playerReady = false;
    let animationFrame = 0;

    title.textContent = dashboardData.title;
    timeline.max = String(duration);

    function add(tag, attrs) {
      const element = document.createElementNS(ns, tag);
      Object.entries(attrs).forEach(([key, value]) => element.setAttribute(key, value));
      svg.appendChild(element);
      return element;
    }
    function formatTime(value) {
      const safe = Number.isFinite(value) ? Math.max(0, value) : 0;
      const hours = Math.floor(safe / 3600);
      const minutes = Math.floor((safe % 3600) / 60);
      const seconds = Math.floor(safe % 60).toString().padStart(2, "0");
      return hours ? `${hours}:${minutes.toString().padStart(2, "0")}:${seconds}` : `${minutes}:${seconds}`;
    }
    function retentionAt(second) {
      const safe = Number.isFinite(second) ? Math.max(0, Math.min(duration, second)) : 0;
      if (safe <= timePoints[0][0]) return timePoints[0][1];
      if (safe >= timePoints.at(-1)[0]) return timePoints.at(-1)[1];
      let high = 1;
      while (high < timePoints.length && timePoints[high][0] < safe) high += 1;
      const low = high - 1;
      const span = timePoints[high][0] - timePoints[low][0];
      const mix = span ? (safe - timePoints[low][0]) / span : 0;
      return timePoints[low][1] + (timePoints[high][1] - timePoints[low][1]) * mix;
    }

    const yStep = yMax <= 125 ? 25 : 50;
    for (let value = 0; value <= yMax; value += yStep) {
      add("line", {x1: margin.left, x2: W-margin.right, y1: y(value), y2: y(value), class: value === 100 ? "reference" : "grid"});
      const label = add("text", {x: margin.left-9, y: y(value)+4, "text-anchor": "end", class: "axis-text"});
      label.textContent = `${value}%`;
    }
    const tickStep = duration <= 40 ? 5 : duration <= 180 ? 30 : 60;
    const tickValues = [];
    for (let second = 0; second < duration; second += tickStep) tickValues.push(second);
    tickValues.push(duration);
    tickValues.forEach(second => {
      add("line", {x1: x(second), x2: x(second), y1: margin.top, y2: H-margin.bottom, class: "grid"});
      const label = add("text", {x: x(second), y: H-margin.bottom+21, "text-anchor": "middle", class: "axis-text"});
      label.textContent = formatTime(second);
    });
    add("line", {x1: margin.left, x2: W-margin.right, y1: H-margin.bottom, y2: H-margin.bottom, class: "axis"});
    add("line", {x1: margin.left, x2: margin.left, y1: margin.top, y2: H-margin.bottom, class: "axis"});
    const axisLabel = add("text", {x: margin.left+innerWidth/2, y: H-7, "text-anchor": "middle", class: "axis-text"});
    axisLabel.textContent = "Elapsed video time";
    const path = timePoints.map((point, index) => `${index ? "L" : "M"}${x(point[0]).toFixed(1)},${y(point[1]).toFixed(1)}`).join(" ");
    add("path", {d: path, class: "retention-line"});
    timePoints.forEach(point => add("circle", {cx: x(point[0]), cy: y(point[1]), r: 1.7, class: "sample"}));
    const playhead = add("line", {x1: x(0), x2: x(0), y1: margin.top, y2: H-margin.bottom, class: "playhead"});
    const playheadDot = add("circle", {cx: x(0), cy: y(retentionAt(0)), r: 5, class: "playhead-dot"});
    const hoverLine = add("line", {x1: 0, x2: 0, y1: margin.top, y2: H-margin.bottom, class: "hover-line", visibility: "hidden"});
    const hitArea = add("rect", {x: margin.left, y: margin.top, width: innerWidth, height: innerHeight, class: "hit-area"});

    function renderAt(second) {
      const safe = Number.isFinite(second) ? Math.max(0, Math.min(duration, second)) : 0;
      const retention = retentionAt(safe);
      playhead.setAttribute("x1", x(safe));
      playhead.setAttribute("x2", x(safe));
      playheadDot.setAttribute("cx", x(safe));
      playheadDot.setAttribute("cy", y(retention));
      timeline.value = String(safe);
      clock.textContent = `${formatTime(safe)} / ${formatTime(duration)}`;
      currentPoint.textContent = `${formatTime(safe)} · ${retention.toFixed(1)}%`;
      retentionLive.textContent = `${retention.toFixed(1)}% watching`;
    }
    function playerTime() {
      if (!playerReady || !player || typeof player.getCurrentTime !== "function") return Number(timeline.value) || 0;
      const value = player.getCurrentTime();
      return Number.isFinite(value) ? value : 0;
    }
    function updateLoop() {
      renderAt(playerTime());
      animationFrame = requestAnimationFrame(updateLoop);
    }
    function seekTo(second) {
      const safe = Math.max(0, Math.min(duration, Number(second) || 0));
      if (playerReady && player && typeof player.seekTo === "function") player.seekTo(safe, true);
      renderAt(safe);
    }

    window.onYouTubeIframeAPIReady = function () {
      player = new YT.Player("player", {
        videoId: dashboardData.videoId,
        playerVars: {
          playsinline: 1,
          rel: 0,
          modestbranding: 1,
          origin: window.location.origin
        },
        events: {
          onReady: () => {
            playerReady = true;
            playButton.disabled = false;
            playerStatus.textContent = "Player ready";
            renderAt(player.getCurrentTime());
            cancelAnimationFrame(animationFrame);
            animationFrame = requestAnimationFrame(updateLoop);
          },
          onStateChange: event => {
            const playing = event.data === YT.PlayerState.PLAYING;
            playButton.textContent = playing ? "Pause" : "Play";
            playerStatus.textContent = playing ? "Playing · graph synchronized" : "Paused · graph synchronized";
          },
          onError: event => {
            playerStatus.textContent = `YouTube player error ${event.data}`;
          }
        }
      });
    };
    playButton.addEventListener("click", () => {
      if (!playerReady) return;
      const state = player.getPlayerState();
      if (state === YT.PlayerState.PLAYING) player.pauseVideo();
      else player.playVideo();
    });
    timeline.addEventListener("input", () => seekTo(timeline.value));
    hitArea.addEventListener("click", event => {
      const rect = svg.getBoundingClientRect();
      const localX = (event.clientX-rect.left) * W / rect.width;
      seekTo((localX-margin.left) / innerWidth * duration);
    });
    hitArea.addEventListener("pointermove", event => {
      const rect = svg.getBoundingClientRect();
      if (!rect.width) return;
      const localX = (event.clientX-rect.left) * W / rect.width;
      const second = Math.max(0, Math.min(duration, (localX-margin.left) / innerWidth * duration));
      const retention = retentionAt(second);
      hoverLine.setAttribute("x1", x(second));
      hoverLine.setAttribute("x2", x(second));
      hoverLine.setAttribute("visibility", "visible");
      tooltip.innerHTML = `<strong>${formatTime(second)}</strong><br>${retention.toFixed(1)}% watching`;
      tooltip.style.display = "block";
      const wrap = svg.parentElement.getBoundingClientRect();
      const chartX = x(second) / W * wrap.width;
      const maxLeft = Math.max(8, wrap.width-tooltip.offsetWidth-8);
      tooltip.style.left = `${Math.max(8, Math.min(maxLeft, chartX+10))}px`;
      tooltip.style.top = "14px";
    });
    hitArea.addEventListener("pointerleave", () => {
      hoverLine.setAttribute("visibility", "hidden");
      tooltip.style.display = "none";
    });
    renderAt(0);
  </script>
  <script src="https://www.youtube.com/iframe_api"></script>
</body>
</html>
"""
