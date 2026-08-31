import {
  api,
  classIdFromPath,
  dashboardSort,
  displayName,
  escapeHtml,
  formatCountdown,
  formatPoints,
  lockRoundDeadline,
  remainingUntilMs,
  hideError,
  showError,
  sortStudents,
} from "./common.js";

const classId = classIdFromPath();
const nameSort = dashboardSort(classId);
const STUDENT_AMOUNTS = [1, 5, 10, -1];
const TEAM_AMOUNTS = [1, 5, 10];
const VIEW_KEY = `mgs-student-view-${classId}`;
let studentView = localStorage.getItem(VIEW_KEY) === "1";
const RULES = [
  { id: "each_member", label: "Each member" },
  { id: "split_members", label: "Split" },
  { id: "team_only", label: "Small Team Bonus" },
];

let lastStamp = "";
let latestState = null;
let pendingTeam = null;
let activeTeamId = null;
let roundEndsAtMs = 0;

/**
 * +/- buttons for an individual student (negatives allowed).
 * Future TODO: students awarding points to one another. Teacher-only for now.
 * @param {number} id
 */
function studentButtons(id) {
  return STUDENT_AMOUNTS.map(
    (n) =>
      `<button type="button" data-kind="student" data-id="${id}" data-amount="${n}">${n > 0 ? "+" : ""}${n}</button>`
  ).join("");
}

/**
 * Positive team-amount buttons, or the rule picker after one is chosen.
 * @param {number} teamId
 */
function teamControls(teamId) {
  if (pendingTeam && pendingTeam.id === teamId) {
    const amount = pendingTeam.amount;
    const choices = RULES.map(
      (rule) =>
        `<button type="button" data-kind="team" data-id="${teamId}" data-amount="${amount}" data-rule="${rule.id}">${escapeHtml(rule.label)}</button>`
    ).join("");
    return `<div class="rule-pick">
      <span>Apply +${amount} as:</span>
      ${choices}
      <button type="button" class="secondary" data-cancel-rule="1">Cancel</button>
    </div>`;
  }
  return `<div class="pm">${TEAM_AMOUNTS.map(
    (n) =>
      `<button type="button" class="team-amt" data-team-amt="1" data-id="${teamId}" data-amount="${n}">+${n}</button>`
  ).join("")}<button type="button" data-kind="team" data-id="${teamId}" data-amount="-5" data-rule="team_only">−5</button></div>`;
}

/**
 * Career total minus this game's credited points (prior strength).
 * @param {{career_total?: number, session_points?: number}} row
 */
function priorPoints(row) {
  return formatPoints((Number(row.career_total) || 0) - (Number(row.session_points) || 0));
}

/**
 * Sum of members' prior strength for the team header row.
 * @param {Array<{career_total?: number, session_points?: number}>} members
 */
function teamPriorPoints(members) {
  const sum = (members || []).reduce(
    (total, row) =>
      total + (Number(row.career_total) || 0) - (Number(row.session_points) || 0),
    0
  );
  return formatPoints(sum);
}

/**
 * Name + prior/now scores on one row (buttons live on the next row).
 * @param {"team"|"player"} kind
 * @param {string} prior
 * @param {string} name
 * @param {string} now
 */
function scoreRow(kind, prior, name, now) {
  return `<tr class="${kind}-line">
    <td class="prior">${prior}</td>
    <td class="who">${name}</td>
    <td class="now">${now}</td>
  </tr>`;
}

/**
 * Running Now total plus a read-only R1 · R2 · R3 line.
 * Awards still hit the lesson sum; the current round is emphasized.
 * @param {{session_points?: number, points_r1?: number, points_r2?: number, points_r3?: number}} row
 * @param {number} round
 * @returns {string}
 */
function nowScoreHtml(row, round) {
  const total = escapeHtml(formatPoints(row.session_points));
  const n = Number(round) || 1;
  const parts = [1, 2, 3].map((index) => {
    const value = escapeHtml(formatPoints(row[`points_r${index}`]));
    const on = index === n ? " on" : "";
    return `<span class="now-r${on}">${value}</span>`;
  });
  return `<div class="now-total">${total}</div><div class="now-rounds">${parts.join('<span class="now-dot">·</span>')}</div>`;
}

/**
 * Scoring controls in a row under the name/scores line.
 * @param {"team"|"player"} kind
 * @param {string} controls
 */
function controlsRow(kind, controls) {
  return `<tr class="${kind}-ctrls">
    <td class="btns" colspan="3">${controls}</td>
  </tr>`;
}

/**
 * Paint present students grouped by team with live credited scores.
 * @param {any} state
 */
function render(state) {
  latestState = state;
  paintRound(state);
  const stamp = JSON.stringify({
    pending: pendingTeam,
    round: state.game?.round,
    teams: (state.teams || []).map((t) => [
      t.id,
      t.score,
      t.bucket,
      t.members.map((m) => [
        m.id,
        m.session_points,
        m.points_r1,
        m.points_r2,
        m.points_r3,
        m.career_total,
      ]),
    ]),
  });
  if (stamp === lastStamp) return;
  lastStamp = stamp;
  document.getElementById("dash-link").href = `/class/${classId}`;
  document.getElementById("title").textContent = "Teacher Game Dashboard";
  document.getElementById("meta").textContent =
    `${state.class.course_code} · ${state.session.header_label}`;
  applyStudentView();
  const root = document.getElementById("teams");
  root.innerHTML = (state.teams || [])
    .map((team) => {
      const members = sortStudents(team.members, nameSort);
      const roundN = Number(state.game?.round) || 1;
      const playerBlocks = members
        .map(
          (s) => `<tbody class="player-block">
            ${scoreRow(
              "player",
              escapeHtml(priorPoints(s)),
              escapeHtml(displayName(s, nameSort)),
              nowScoreHtml(s, roundN)
            )}
            ${controlsRow("player", `<div class="pm">${studentButtons(s.id)}</div>`)}
          </tbody>`
        )
        .join("");
      return `<section class="team-card" data-team-id="${team.id}" style="--team:${escapeHtml(team.color)}">
        <table class="roster">
          <tbody class="team-head">
            ${scoreRow(
              "team",
              escapeHtml(teamPriorPoints(members)),
              escapeHtml(team.name),
              escapeHtml(formatPoints(team.score))
            )}
            ${controlsRow("team", teamControls(team.id))}
          </tbody>
          ${playerBlocks}
        </table>
      </section>`;
    })
    .join("");
  if (pendingTeam) activeTeamId = pendingTeam.id;
  requestAnimationFrame(layoutTeams);
}

/**
 * Seconds left until the locked round deadline.
 * @returns {number}
 */
function displayedRemaining() {
  return remainingUntilMs(roundEndsAtMs);
}

/**
 * Paint ROUND N · title, countdown, and the next-round button.
 * @param {any} state
 */
function paintRound(state) {
  const game = state?.game || {};
  const n = Number(game.round) || 1;
  const title = game.round_title || "";
  const label = document.getElementById("round-label");
  if (label) label.textContent = `ROUND ${n} · ${title}`;
  roundEndsAtMs = lockRoundDeadline(roundEndsAtMs, game.round_ends_at_ms);
  paintClock();
  const btn = document.getElementById("start-round");
  if (!btn) return;
  if (n === 1) {
    btn.hidden = false;
    btn.textContent = "Start Round 2";
    btn.dataset.round = "2";
  } else if (n === 2) {
    btn.hidden = false;
    btn.textContent = "Start Round 3";
    btn.dataset.round = "3";
  } else {
    btn.hidden = true;
    delete btn.dataset.round;
  }
}

/**
 * Write the interpolated countdown without rebuilding the team board.
 */
function paintClock() {
  const clock = document.getElementById("round-clock");
  if (clock) clock.textContent = formatCountdown(displayedRemaining());
}

/**
 * Show teams side by side, or as tabs when they do not fit the window.
 */
function layoutTeams() {
  const row = document.getElementById("teams");
  const tabs = document.getElementById("team-tabs");
  if (!row || !tabs) return;
  const cards = [...row.querySelectorAll(".team-card")];
  tabs.replaceChildren();
  tabs.classList.add("hidden");
  row.classList.remove("tabbed");
  cards.forEach((card) => {
    card.hidden = false;
  });
  if (!cards.length) return;
  const overflow = row.scrollWidth > row.clientWidth + 4;
  if (!overflow) {
    activeTeamId = null;
    return;
  }
  const ids = cards.map((card) => Number(card.dataset.teamId));
  if (!ids.includes(activeTeamId)) activeTeamId = ids[0];
  row.classList.add("tabbed");
  tabs.classList.remove("hidden");
  for (const card of cards) {
    const id = Number(card.dataset.teamId);
    const team = (latestState?.teams || []).find((t) => t.id === id);
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "team-tab" + (id === activeTeamId ? " on" : "");
    btn.setAttribute("role", "tab");
    btn.setAttribute("aria-selected", id === activeTeamId ? "true" : "false");
    btn.textContent = team?.name || `Team`;
    btn.style.setProperty("--team", team?.color || "#1c1914");
    btn.addEventListener("click", () => {
      activeTeamId = id;
      layoutTeams();
    });
    tabs.appendChild(btn);
    card.hidden = id !== activeTeamId;
  }
}

/**
 * Award points then refresh the teacher view.
 * @param {"student"|"team"} kind
 * @param {number} id
 * @param {number} amount
 * @param {string|null} [teamRule]
 */
async function award(kind, id, amount, teamRule = null) {
  hideError("#error");
  const payload = { kind, id, amount };
  if (kind === "team") payload.team_rule = teamRule;
  const state = await api(`/api/classes/${classId}/game/score`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  pendingTeam = null;
  lastStamp = "";
  render(state);
}

document.getElementById("teams").addEventListener("click", (event) => {
  const cancel = event.target.closest("[data-cancel-rule]");
  if (cancel) {
    pendingTeam = null;
    lastStamp = "";
    if (latestState) render(latestState);
    return;
  }
  const amtBtn = event.target.closest("[data-team-amt]");
  if (amtBtn) {
    pendingTeam = { id: Number(amtBtn.dataset.id), amount: Number(amtBtn.dataset.amount) };
    lastStamp = "";
    if (latestState) render(latestState);
    return;
  }
  const btn = event.target.closest("button[data-kind]");
  if (!btn) return;
  const kind = btn.dataset.kind;
  const rule = btn.dataset.rule || null;
  award(kind, Number(btn.dataset.id), Number(btn.dataset.amount), rule).catch((err) =>
    showError("#error", err)
  );
});

/**
 * Hide or show prior-strength columns for a student-facing layout.
 */
function applyStudentView() {
  document.body.classList.toggle("student-view", studentView);
  const btn = document.getElementById("student-view");
  if (btn) btn.textContent = studentView ? "Show strength" : "Student View";
}

document.getElementById("student-view").addEventListener("click", () => {
  studentView = !studentView;
  localStorage.setItem(VIEW_KEY, studentView ? "1" : "0");
  applyStudentView();
});

document.getElementById("start-round").addEventListener("click", async () => {
  const btn = document.getElementById("start-round");
  const next = Number(btn?.dataset.round);
  if (!next) return;
  hideError("#error");
  try {
    const state = await api(`/api/classes/${classId}/game/round`, {
      method: "POST",
      body: JSON.stringify({ round: next }),
    });
    lastStamp = "";
    render(state);
  } catch (err) {
    showError("#error", err);
  }
});

document.getElementById("quit-game").addEventListener("click", async () => {
  hideError("#error");
  try {
    await api(`/api/classes/${classId}/game/cancel`, { method: "POST", body: "{}" });
    location.href = `/class/${classId}`;
  } catch (err) {
    showError("#error", err);
  }
});

document.getElementById("end-game").addEventListener("click", async () => {
  hideError("#error");
  try {
    await api(`/api/classes/${classId}/game/end`, { method: "POST", body: "{}" });
    location.href = `/class/${classId}`;
  } catch (err) {
    showError("#error", err);
  }
});

/**
 * Open the scoreboard window once after Create Teams.
 */
function maybeOpenScoreboard() {
  const params = new URLSearchParams(location.search);
  if (params.get("openscoreboard") !== "1") return;
  window.open("/scoreboard", "mgs-scoreboard");
  params.delete("openscoreboard");
  const qs = params.toString();
  history.replaceState({}, "", `/class/${classId}/game${qs ? `?${qs}` : ""}`);
}

maybeOpenScoreboard();

/**
 * Poll so a second teacher window stays in sync with scoring.
 */
async function tick() {
  try {
    const state = await api(`/api/classes/${classId}/game`);
    if (state.game.status !== "live") {
      location.replace(`/class/${classId}`);
      return;
    }
    render(state);
  } catch (err) {
    showError("#error", err);
  }
}

tick();
setInterval(tick, 400);
setInterval(paintClock, 200);
window.addEventListener("resize", layoutTeams);
