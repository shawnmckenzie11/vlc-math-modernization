import { classIdFromPath, formatPoints } from "./common.js";

const classId = classIdFromPath();
let lastSeq = 0;
let lastGameId = null;
let phase = "idle";
let tickBusy = false;

const bar = document.getElementById("bar");
const idle = document.getElementById("idle");
const finalBoard = document.getElementById("final");
const finalHeader = document.getElementById("final-header");
const finalList = document.getElementById("final-list");

/**
 * True when the ESPN bar's team nodes no longer match the payload.
 * @param {Array<{id: number}>} teams
 */
function barNeedsRebuild(teams) {
  const nodes = [...bar.querySelectorAll(":scope > .espn-team")];
  if (nodes.length !== teams.length) return true;
  return nodes.some((node, i) => node.dataset.teamId !== String(teams[i].id));
}

/**
 * Paint the ESPN-style bottom bar. No roster, no IDs.
 * Updates score text in place so pulse animations are not wiped.
 * @param {any} data
 */
function paintBar(data) {
  const teams = data.teams || [];
  if (barNeedsRebuild(teams)) {
    bar.innerHTML = teams
      .map(
        (team) => `<div class="espn-team" data-team-id="${team.id}">
        <div class="espn-swatch" style="background:${team.color}"></div>
        <div class="espn-meta">
          <div class="espn-name">${escapeText(team.name)}</div>
          <div class="espn-score" data-score="${escapeText(team.score)}">${escapeText(formatPoints(team.score))}</div>
        </div>
      </div>`
      )
      .join("");
    return;
  }
  for (const team of teams) {
    const node = bar.querySelector(`:scope > [data-team-id="${team.id}"]`);
    if (!node) continue;
    const nameEl = node.querySelector(".espn-name");
    const scoreEl = node.querySelector(".espn-score");
    if (nameEl && nameEl.textContent !== team.name) nameEl.textContent = team.name;
    const scoreKey = String(team.score);
    if (scoreEl && scoreEl.dataset.score !== scoreKey) {
      scoreEl.dataset.score = scoreKey;
      scoreEl.textContent = formatPoints(team.score);
    }
    const swatch = node.querySelector(".espn-swatch");
    if (swatch) swatch.style.background = team.color;
  }
}

/**
 * Ranked Final Score overlay. Rebuilt once when the game ends.
 * @param {any} data
 */
function showFinal(data) {
  idle.hidden = true;
  finalBoard.hidden = false;
  finalBoard.removeAttribute("hidden");
  finalBoard.classList.remove("hidden");
  finalHeader.textContent = data.header || "";
  const ranked = [...(data.teams || [])].sort((a, b) => {
    const diff = Number(b.score) - Number(a.score);
    if (diff !== 0) return diff;
    return Number(a.id) - Number(b.id);
  });
  finalList.innerHTML = ranked
    .map(
      (team, index) => `<li style="--team:${escapeText(team.color)}">
        <span class="final-place">${index + 1}</span>
        <span class="final-name">${escapeText(team.name)}</span>
        <span class="final-score">${escapeText(formatPoints(team.score))}</span>
      </li>`
    )
    .join("");
}

/**
 * Hide the Final Score overlay for a new live game or idle board.
 */
function hideFinal() {
  finalBoard.hidden = true;
  finalBoard.classList.add("hidden");
  finalList.innerHTML = "";
}

/**
 * Route idle / live / final from a scoreboard payload.
 * @param {any} data
 */
function render(data) {
  const teams = data.teams || [];
  const isLive = Boolean(data.live) && teams.length > 0;
  const isFinal =
    !isLive &&
    teams.length > 0 &&
    (Boolean(data.final) || data.status === "ended");

  if (isLive) {
    idle.hidden = true;
    if (phase !== "live") {
      hideFinal();
      phase = "live";
    }
    paintBar(data);
    return;
  }
  if (isFinal) {
    idle.hidden = true;
    paintBar(data);
    if (phase !== "final") {
      phase = "final";
      showFinal(data);
    }
    return;
  }
  if (phase === "final") {
    idle.hidden = true;
    return;
  }
  phase = "idle";
  hideFinal();
  idle.hidden = false;
  bar.innerHTML = "";
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
 * Pulse a team and float a caption up from the numeric score.
 * Small Team Bonus and player first names use the event caption.
 * @param {any} event
 */
function celebrate(event) {
  if (!event) return;
  const amount = Number(event.amount);
  if (!amount) return;
  const node = bar.querySelector(`:scope > [data-team-id="${event.team_id}"]`);
  if (!node) return;
  const first = String(event.first_name || "").trim();
  let text = String(event.caption || event.label || "").trim();
  if (!text) {
    if (event.team_rule === "team_only" && amount > 0) {
      text = `Small Team Bonus +${amount}`;
    } else if (first) {
      text = amount > 0 ? `${first} +${amount}` : `${first} ${amount}`;
    } else {
      text = amount > 0 ? `+${amount}` : String(amount);
    }
  }
  if (amount > 0) {
    node.classList.remove("pulse");
    void node.offsetWidth;
    node.classList.add("pulse");
    window.setTimeout(() => node.classList.remove("pulse"), 1300);
  }
  const floater = document.createElement("div");
  floater.className = amount > 0 ? "float-plus" : "float-plus float-minus";
  floater.textContent = text;
  const scoreEl = node.querySelector(".espn-score");
  (scoreEl || node).appendChild(floater);
  floater.addEventListener("animationend", () => floater.remove(), { once: true });
  setTimeout(() => floater.remove(), 1600);
}

/**
 * Poll live scores about every 400ms.
 */
async function tick() {
  if (tickBusy) return;
  tickBusy = true;
  try {
    const response = await fetch(`/api/classes/${classId}/scoreboard`);
    if (!response.ok) return;
    const data = await response.json();
    const gameId = data.game_id ?? null;
    if (gameId !== lastGameId) {
      lastGameId = gameId;
      lastSeq = Number(data.event_seq || 0);
      if (data.live) phase = "idle";
    }
    render(data);
    const seq = Number(data.event_seq || 0);
    if (data.live && seq > lastSeq) {
      lastSeq = seq;
      celebrate(data.last_event);
    } else if (seq > lastSeq) {
      lastSeq = seq;
    }
  } finally {
    tickBusy = false;
  }
}

tick().catch(() => {});
setInterval(() => {
  tick().catch(() => {});
}, 400);
