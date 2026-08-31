import { formatPoints } from "./common.js";

if (new URLSearchParams(location.search).get("overlay") === "1") {
  document.body.classList.add("overlay");
}
let lastSeq = 0;
let lastGameId = null;
let phase = "idle";
let tickBusy = false;
let rosterTimer = 0;

const stage = document.querySelector(".board-stage");
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
 * Teams with the highest score (ties included).
 * @param {Array<{score?: number}>} teams
 * @returns {Array<any>}
 */
function winningTeams(teams) {
  if (!teams.length) return [];
  const top = Math.max(...teams.map((team) => Number(team.score) || 0));
  return teams.filter((team) => (Number(team.score) || 0) === top);
}

/**
 * Ranked Final Score. After 10s, winner names cover the other teams.
 * @param {any} data
 */
function showFinal(data) {
  idle.hidden = true;
  finalBoard.hidden = false;
  finalBoard.removeAttribute("hidden");
  finalBoard.classList.remove("hidden");
  document.body.classList.add("is-final");
  if (stage) stage.classList.add("is-final");
  window.clearTimeout(rosterTimer);
  finalHeader.textContent = data.header || "";
  const ranked = [...(data.teams || [])].sort((a, b) => {
    const diff = Number(b.score) - Number(a.score);
    if (diff !== 0) return diff;
    return Number(a.id) - Number(b.id);
  });
  finalList.innerHTML = ranked
    .map((team) => {
      const place = 1 + ranked.filter((other) => Number(other.score) > Number(team.score)).length;
      const win = (Number(team.score) || 0) === (Number(ranked[0]?.score) || 0);
      return `<li class="${win ? "winner" : "runner"}" style="--team:${escapeText(team.color)}">
        <span class="final-place">${place}</span>
        <span class="final-name">${escapeText(team.name)}</span>
        ${win ? `<span class="final-crown">Winner</span>` : ""}
        <span class="final-score">${escapeText(formatPoints(team.score))}</span>
      </li>`;
    })
    .join("");
  const winners = winningTeams(ranked);
  const names = winners.flatMap((team) =>
    (team.players || [])
      .map((player) => String(player.first_name || "").trim())
      .filter(Boolean)
      .map((first) => ({ first, team: team.name, color: team.color }))
  );
  rosterTimer = window.setTimeout(() => {
    revealRosterOverRunners(names, winners);
  }, 10000);
}

/**
 * Cover non-winning team cards with the winning roster.
 * @param {Array<{first: string, team: string, color: string}>} names
 * @param {Array<{name: string}>} winners
 */
function revealRosterOverRunners(names, winners) {
  if (!finalList || !names.length) return;
  const runners = [...finalList.querySelectorAll("li.runner")];
  if (!runners.length) return;
  finalList.querySelector(".final-roster-overlay")?.remove();
  const overlay = document.createElement("div");
  overlay.className = "final-roster-overlay";
  const title = winners.length
    ? `Winning team${winners.length > 1 ? "s" : ""} · ${winners.map((team) => team.name).join(" · ")}`
    : "Winning team";
  overlay.innerHTML = `<p class="final-roster-kicker">${escapeText(title)}</p>
    <ul class="final-roster-names">${names
      .map(
        (row) => `<li style="--team:${escapeText(row.color)}">
          <span class="final-player">${escapeText(row.first)}</span>
          ${winners.length > 1 ? `<span class="final-player-team">${escapeText(row.team)}</span>` : ""}
        </li>`
      )
      .join("")}</ul>`;
  finalList.appendChild(overlay);
  const listBox = finalList.getBoundingClientRect();
  const first = runners[0].getBoundingClientRect();
  const last = runners[runners.length - 1].getBoundingClientRect();
  overlay.style.left = `${Math.max(0, first.left - listBox.left)}px`;
  overlay.style.width = `${Math.max(80, last.right - first.left)}px`;
}

/**
 * Hide the Final Score overlay for a new live game or idle board.
 */
function hideFinal() {
  window.clearTimeout(rosterTimer);
  finalBoard.hidden = true;
  finalBoard.classList.add("hidden");
  document.body.classList.remove("is-final");
  if (stage) stage.classList.remove("is-final");
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
 * Bounce a caption inside a team's scoreboard rectangle until it is removed.
 * @param {HTMLElement} floater
 * @param {HTMLElement} host
 */
function bounceFloater(floater, host) {
  const pad = 4;
  let x = pad;
  let y = pad;
  let vx = 90;
  let vy = 55;
  let last = 0;

  /**
   * Clamp space the caption can occupy inside the team section.
   * @returns {{maxX: number, maxY: number}}
   */
  function bounds() {
    const maxX = Math.max(pad, host.clientWidth - floater.offsetWidth - pad);
    const maxY = Math.max(pad, host.clientHeight - floater.offsetHeight - pad);
    return { maxX, maxY };
  }

  /**
   * Reverse one axis and keep speed in a playful range.
   * @param {number} vel
   * @returns {number}
   */
  function bounce(vel) {
    const speed = Math.max(46, Math.abs(vel) * (0.94 + Math.random() * 0.18));
    return -Math.sign(vel || 1) * speed;
  }

  const box = bounds();
  x = pad + Math.random() * Math.max(0, box.maxX - pad);
  y = pad + Math.random() * Math.max(0, box.maxY - pad);
  const speed = 70 + Math.random() * 80;
  const angle = Math.random() * Math.PI * 2;
  vx = Math.cos(angle) * speed;
  vy = Math.sin(angle) * speed;
  if (Math.abs(vx) < 28) vx = 28 * Math.sign(vx || 1);
  if (Math.abs(vy) < 22) vy = 22 * Math.sign(vy || 1);
  floater.style.transform = `translate(${x}px, ${y}px)`;

  /**
   * Advance one bounce frame while the caption is still on the board.
   * @param {number} now
   */
  function frame(now) {
    if (!floater.isConnected) return;
    const dt = last ? Math.min(0.05, (now - last) / 1000) : 0;
    last = now;
    const limit = bounds();
    x += vx * dt;
    y += vy * dt;
    if (x <= pad) {
      x = pad;
      vx = bounce(-Math.abs(vx));
    } else if (x >= limit.maxX) {
      x = limit.maxX;
      vx = bounce(Math.abs(vx));
    }
    if (y <= pad) {
      y = pad;
      vy = bounce(-Math.abs(vy));
    } else if (y >= limit.maxY) {
      y = limit.maxY;
      vy = bounce(Math.abs(vy));
    }
    floater.style.transform = `translate(${x}px, ${y}px)`;
    requestAnimationFrame(frame);
  }

  requestAnimationFrame(frame);
}

/**
 * Pulse a team and bounce a caption inside that team's scoreboard section.
 * Negative individual awards skip the animation. Font stays put for 2s,
 * then fades over 3s. Small Team Bonus and player first names use the
 * event caption.
 * @param {any} event
 */
function celebrate(event) {
  if (!event) return;
  const amount = Number(event.amount);
  if (!amount) return;
  const isStudent = event.kind === "student";
  if (amount < 0 && isStudent) return;
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
  let layer = node.querySelector(":scope > .espn-floaters");
  if (!layer) {
    layer = document.createElement("div");
    layer.className = "espn-floaters";
    node.appendChild(layer);
  }
  const floater = document.createElement("div");
  floater.className = amount > 0 ? "float-plus" : "float-plus float-minus";
  floater.textContent = text;
  layer.appendChild(floater);
  bounceFloater(floater, layer);
  floater.addEventListener("animationend", () => floater.remove(), { once: true });
  setTimeout(() => floater.remove(), 5200);
}

/**
 * Poll live scores about every 400ms.
 */
async function tick() {
  if (tickBusy) return;
  tickBusy = true;
  try {
    const response = await fetch("/api/scoreboard");
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
