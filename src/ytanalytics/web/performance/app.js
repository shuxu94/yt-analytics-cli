const ns = "http://www.w3.org/2000/svg";
const queue = document.getElementById("queue");
const period = document.getElementById("period");
const selectedLabel = document.getElementById("selected-label");
const selectedTitle = document.getElementById("selected-title");
const metrics = document.getElementById("metrics");
const svg = document.getElementById("chart");
const tooltip = document.getElementById("tooltip");
const playButton = document.getElementById("play");
const timeline = document.getElementById("timeline");
const clock = document.getElementById("clock");
const current = document.getElementById("current");
const live = document.getElementById("live");
const status = document.getElementById("status");
const fatalError = document.getElementById("fatal-error");
const W = 760;
const H = 390;
const margin = { top: 16, right: 20, bottom: 48, left: 56 };
const innerWidth = W - margin.left - margin.right;
const innerHeight = H - margin.top - margin.bottom;

let dashboardData = null;
let videos = [];
let selectedIndex = 0;
let player = null;
let playerReady = false;
let animationFrame = 0;
let chartState = null;

function selected() {
  return videos[selectedIndex];
}

function formatNumber(value) {
  return new Intl.NumberFormat().format(Math.round(value || 0));
}

function escapeHtml(value) {
  return String(value).replace(
    /[&<>"']/g,
    (character) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        character
      ],
  );
}

function formatTime(value) {
  const safe = Number.isFinite(value) ? Math.max(0, value) : 0;
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const seconds = Math.floor(safe % 60).toString().padStart(2, "0");
  return hours
    ? `${hours}:${minutes.toString().padStart(2, "0")}:${seconds}`
    : `${minutes}:${seconds}`;
}

function add(tag, attrs) {
  const element = document.createElementNS(ns, tag);
  Object.entries(attrs).forEach(([key, value]) => element.setAttribute(key, value));
  svg.appendChild(element);
  return element;
}

function pointsFor(video) {
  return video.retention
    .map((point) => [point.elapsedRatio * video.durationSeconds, point.watchRatio * 100])
    .sort((a, b) => a[0] - b[0]);
}

function retentionAt(second) {
  const state = chartState;
  if (!state || !state.points.length) return null;
  const safe = Number.isFinite(second) ? Math.max(0, Math.min(state.duration, second)) : 0;
  if (safe <= state.points[0][0]) return state.points[0][1];
  if (safe >= state.points.at(-1)[0]) return state.points.at(-1)[1];
  let high = 1;
  while (high < state.points.length && state.points[high][0] < safe) high += 1;
  const low = high - 1;
  const span = state.points[high][0] - state.points[low][0];
  const mix = span ? (safe - state.points[low][0]) / span : 0;
  return state.points[low][1] + (state.points[high][1] - state.points[low][1]) * mix;
}

function buildQueue() {
  queue.replaceChildren();
  ["top", "bottom"].forEach((group) => {
    const items = videos
      .map((video, index) => ({ video, index }))
      .filter((item) => item.video.group === group);
    if (!items.length) return;

    const section = document.createElement("section");
    section.className = "queue-section";
    section.innerHTML = `
      <div class="queue-heading">
        <h2>${group === "top" ? "Top 5" : "Bottom 5"}</h2>
        <span>by views</span>
      </div>`;

    items.forEach(({ video, index }) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "video-choice";
      button.dataset.index = String(index);
      button.setAttribute("aria-pressed", String(index === selectedIndex));
      button.innerHTML = `
        <span class="rank">${video.rank}</span>
        <span class="choice-copy">
          <span class="choice-title">${escapeHtml(video.title)}</span>
          <span class="choice-detail">
            ${video.durationSeconds}s · ${formatNumber(video.subscribersGained)} subscribers
          </span>
        </span>
        <span class="choice-views">${formatNumber(video.views)}</span>`;
      button.addEventListener("click", () => selectVideo(index));
      section.appendChild(button);
    });
    queue.appendChild(section);
  });
}

function updateHeader() {
  const video = selected();
  selectedLabel.textContent = `${video.group === "top" ? "Top" : "Bottom"} #${video.rank} by views`;
  selectedTitle.textContent = video.title;
  metrics.innerHTML = `
    <div class="metric"><strong>${formatNumber(video.views)}</strong> <span>views</span></div>
    <div class="metric"><strong>${formatNumber(video.watchTimeMinutes)}</strong> <span>watch min</span></div>
    <div class="metric"><strong>${formatNumber(video.subscribersGained)}</strong> <span>subscribers</span></div>`;
  document.title = `${video.title} · retention dashboard`;
}

function buildChart() {
  const video = selected();
  const points = pointsFor(video);
  const duration = video.durationSeconds;
  svg.replaceChildren();
  tooltip.style.display = "none";
  timeline.max = String(duration);
  timeline.value = "0";

  if (!points.length) {
    const message = add("text", {
      x: W / 2,
      y: H / 2,
      "text-anchor": "middle",
      class: "empty-text",
    });
    message.textContent = "No retention data is available for this video in this period.";
    chartState = { points: [], duration };
    renderAt(0);
    return;
  }

  const maxValue = Math.max(...points.map((point) => point[1]), 100);
  const yMax = Math.max(100, Math.ceil(maxValue / 25) * 25);
  const x = (second) =>
    margin.left + (Math.max(0, Math.min(duration, second)) / duration) * innerWidth;
  const y = (value) => margin.top + (1 - value / yMax) * innerHeight;
  chartState = { points, duration, x, y, playhead: null, playheadDot: null };

  const yStep = yMax <= 125 ? 25 : 50;
  for (let value = 0; value <= yMax; value += yStep) {
    add("line", {
      x1: margin.left,
      x2: W - margin.right,
      y1: y(value),
      y2: y(value),
      class: value === 100 ? "reference" : "grid",
    });
    const label = add("text", {
      x: margin.left - 9,
      y: y(value) + 4,
      "text-anchor": "end",
      class: "axis-text",
    });
    label.textContent = `${value}%`;
  }

  const tickStep = duration <= 40 ? 5 : duration <= 180 ? 30 : 60;
  const ticks = [];
  for (let second = 0; second < duration; second += tickStep) ticks.push(second);
  ticks.push(duration);
  ticks.forEach((second) => {
    add("line", {
      x1: x(second),
      x2: x(second),
      y1: margin.top,
      y2: H - margin.bottom,
      class: "grid",
    });
    const label = add("text", {
      x: x(second),
      y: H - margin.bottom + 21,
      "text-anchor": "middle",
      class: "axis-text",
    });
    label.textContent = formatTime(second);
  });

  add("line", {
    x1: margin.left,
    x2: W - margin.right,
    y1: H - margin.bottom,
    y2: H - margin.bottom,
    class: "axis",
  });
  add("line", {
    x1: margin.left,
    x2: margin.left,
    y1: margin.top,
    y2: H - margin.bottom,
    class: "axis",
  });
  const axisLabel = add("text", {
    x: margin.left + innerWidth / 2,
    y: H - 7,
    "text-anchor": "middle",
    class: "axis-text",
  });
  axisLabel.textContent = "Elapsed video time";

  const path = points
    .map(
      (point, index) =>
        `${index ? "L" : "M"}${x(point[0]).toFixed(1)},${y(point[1]).toFixed(1)}`,
    )
    .join(" ");
  add("path", { d: path, class: "curve" });
  points.forEach((point) =>
    add("circle", { cx: x(point[0]), cy: y(point[1]), r: 1.7, class: "sample" }),
  );

  chartState.playhead = add("line", {
    x1: x(0),
    x2: x(0),
    y1: margin.top,
    y2: H - margin.bottom,
    class: "playhead",
  });
  chartState.playheadDot = add("circle", {
    cx: x(0),
    cy: y(retentionAt(0)),
    r: 5,
    class: "playhead-dot",
  });
  const hoverLine = add("line", {
    x1: 0,
    x2: 0,
    y1: margin.top,
    y2: H - margin.bottom,
    class: "hover-line",
    visibility: "hidden",
  });
  const hit = add("rect", {
    x: margin.left,
    y: margin.top,
    width: innerWidth,
    height: innerHeight,
    class: "hit",
  });

  hit.addEventListener("click", (event) => {
    const rect = svg.getBoundingClientRect();
    if (!rect.width) return;
    const localX = ((event.clientX - rect.left) * W) / rect.width;
    seekTo(((localX - margin.left) / innerWidth) * duration);
  });
  hit.addEventListener("pointermove", (event) => {
    const rect = svg.getBoundingClientRect();
    if (!rect.width) return;
    const localX = ((event.clientX - rect.left) * W) / rect.width;
    const second = Math.max(
      0,
      Math.min(duration, ((localX - margin.left) / innerWidth) * duration),
    );
    const value = retentionAt(second);
    hoverLine.setAttribute("x1", x(second));
    hoverLine.setAttribute("x2", x(second));
    hoverLine.setAttribute("visibility", "visible");
    tooltip.innerHTML = `<strong>${formatTime(second)}</strong><br>${value.toFixed(1)}% watching`;
    tooltip.style.display = "block";
    const wrap = svg.parentElement.getBoundingClientRect();
    const chartX = (x(second) / W) * wrap.width;
    const maxLeft = Math.max(8, wrap.width - tooltip.offsetWidth - 8);
    tooltip.style.left = `${Math.max(8, Math.min(maxLeft, chartX + 10))}px`;
    tooltip.style.top = "14px";
  });
  hit.addEventListener("pointerleave", () => {
    hoverLine.setAttribute("visibility", "hidden");
    tooltip.style.display = "none";
  });
  renderAt(0);
}

function renderAt(second) {
  const video = selected();
  const safe = Number.isFinite(second)
    ? Math.max(0, Math.min(video.durationSeconds, second))
    : 0;
  const value = retentionAt(safe);
  if (chartState?.playhead && value !== null) {
    chartState.playhead.setAttribute("x1", chartState.x(safe));
    chartState.playhead.setAttribute("x2", chartState.x(safe));
    chartState.playheadDot.setAttribute("cx", chartState.x(safe));
    chartState.playheadDot.setAttribute("cy", chartState.y(value));
  }
  timeline.value = String(safe);
  clock.textContent = `${formatTime(safe)} / ${formatTime(video.durationSeconds)}`;
  current.textContent =
    value === null
      ? `${formatTime(safe)} · no retention data`
      : `${formatTime(safe)} · ${value.toFixed(1)}%`;
  live.textContent = value === null ? "No retention data" : `${value.toFixed(1)}% watching`;
}

function playerTime() {
  if (!playerReady || !player || typeof player.getCurrentTime !== "function") {
    return Number(timeline.value) || 0;
  }
  const value = player.getCurrentTime();
  return Number.isFinite(value) ? value : 0;
}

function updateLoop() {
  renderAt(playerTime());
  animationFrame = requestAnimationFrame(updateLoop);
}

function seekTo(second) {
  const safe = Math.max(0, Math.min(selected().durationSeconds, Number(second) || 0));
  if (playerReady && player && typeof player.seekTo === "function") player.seekTo(safe, true);
  renderAt(safe);
}

function selectVideo(index) {
  selectedIndex = index;
  buildQueue();
  updateHeader();
  buildChart();
  if (playerReady) {
    player.cueVideoById({ videoId: selected().videoId, startSeconds: 0 });
    status.textContent = "Video selected · ready to play";
  }
}

window.onYouTubeIframeAPIReady = function onYouTubeIframeAPIReady() {
  player = new YT.Player("player", {
    videoId: selected().videoId,
    playerVars: {
      playsinline: 1,
      rel: 0,
      modestbranding: 1,
      origin: window.location.origin,
    },
    events: {
      onReady: () => {
        playerReady = true;
        playButton.disabled = false;
        status.textContent = "Player ready";
        cancelAnimationFrame(animationFrame);
        animationFrame = requestAnimationFrame(updateLoop);
      },
      onStateChange: (event) => {
        const playing = event.data === YT.PlayerState.PLAYING;
        playButton.textContent = playing ? "Pause" : "Play";
        status.textContent = playing
          ? "Playing · graph synchronized"
          : "Paused · graph synchronized";
      },
      onError: (event) => {
        status.textContent = `YouTube player error ${event.data}`;
      },
    },
  });
};

function loadYouTubePlayer() {
  const script = document.createElement("script");
  script.src = "https://www.youtube.com/iframe_api";
  script.async = true;
  document.body.appendChild(script);
}

playButton.addEventListener("click", () => {
  if (!playerReady) return;
  if (player.getPlayerState() === YT.PlayerState.PLAYING) player.pauseVideo();
  else player.playVideo();
});

timeline.addEventListener("input", () => seekTo(timeline.value));

async function initialize() {
  try {
    const response = await fetch("/api/dashboard", { cache: "no-store" });
    if (!response.ok) throw new Error(`Dashboard data request failed (${response.status})`);
    dashboardData = await response.json();
    videos = dashboardData.videos;
    if (!videos.length) throw new Error("No videos were returned for this dashboard.");
    period.textContent = `${dashboardData.period} · ranked by views`;
    buildQueue();
    updateHeader();
    buildChart();
    loadYouTubePlayer();
  } catch (error) {
    fatalError.textContent = error instanceof Error ? error.message : "Dashboard failed to load.";
    fatalError.hidden = false;
    selectedTitle.textContent = "Dashboard unavailable";
    period.textContent = "Unable to load analytics";
  }
}

initialize();
