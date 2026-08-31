import { classIdFromPath, formatPoints } from "./common.js";

const classId = classIdFromPath();
let lastSeq = 0;
let lastPaint = "";

const bar = document.getElementById("bar");
const toast = document.getElementById("toast");
const idle = document.getElementById("idle");

/**
 * Paint the ESPN-style bottom bar. No roster, no IDs.
 * @param {any} data
 */
function render(data) {
  const live = data.live && data.teams && data.teams.length;
  idle.hidden = Boolean(live);
  if (!live) {
    lastPaint = "";
    bar.innerHTML = "";
    return;
  }
  const stamp = JSON.stringify(
    data.teams.map((team) => [team.id, team.name, team.color, team.score])
  );
  if (stamp === lastPaint) return;
  lastPaint = stamp;
  bar.innerHTML = data.teams
    .map((team) => {
      return `<div class="espn-team" data-team-id="${team.id}">
        <div class="espn-swatch" style="background:${team.color}"></div>
        <div class="espn-meta">
          <div class="espn-name">${escapeText(team.name)}</div>
          <div class="espn-score">${escapeText(formatPoints(team.score))}</div>
        </div>
      </div>`;
    })
    .join("");
}

/**
 * Minimal text escape for scoreboard labels.
 * @param {unknown} value
 */
function escapeText(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/"/g, "&quot;");
}

/**
 * Pulse a team when it or one of its players earns points.
 * Deductions update the number with no celebration.
 * @param {any} event
 */
function celebrate(event) {
  if (!event || !event.celebrate || event.amount <= 0) return;
  const node = bar.querySelector(`[data-team-id="${event.team_id}"]`);
  if (!node) return;
  node.classList.remove("pulse");
  void node.offsetWidth;
  node.classList.add("pulse");
  const floater = document.createElement("div");
  floater.className = "float-plus";
  floater.textContent = `+${event.amount}`;
  node.appendChild(floater);
  setTimeout(() => floater.remove(), 900);
  toast.hidden = false;
  toast.textContent = event.label || `${event.team_name} +${event.amount}`;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 1600);
}

/**
 * Poll live scores about every 400ms.
 */
async function tick() {
  const response = await fetch(`/api/classes/${classId}/scoreboard`);
  const data = await response.json();
  render(data);
  const seq = Number(data.event_seq || 0);
  if (seq > lastSeq) {
    lastSeq = seq;
    celebrate(data.last_event);
  }
}

tick().catch(() => {});
setInterval(() => {
  tick().catch(() => {});
}, 400);
