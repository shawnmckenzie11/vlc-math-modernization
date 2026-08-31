import {
  api,
  classIdFromPath,
  dashboardSort,
  displayName,
  escapeHtml,
  formatPoints,
  hideError,
  showError,
  sortStudents,
} from "./common.js";

const classId = classIdFromPath();
const nameSort = dashboardSort(classId);
const STUDENT_AMOUNTS = [1, 5, 10, -1, -5, -10];
const TEAM_AMOUNTS = [1, 5, 10];
const RULES = [
  { id: "each_member", label: "Each member" },
  { id: "split_members", label: "Split" },
  { id: "team_only", label: "Team only" },
];

let lastStamp = "";
let latestState = null;
let pendingTeam = null;

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
  return TEAM_AMOUNTS.map(
    (n) =>
      `<button type="button" class="team-amt" data-team-amt="1" data-id="${teamId}" data-amount="${n}">+${n}</button>`
  ).join("");
}

/**
 * Paint present students grouped by team with live credited scores.
 * @param {any} state
 */
function render(state) {
  latestState = state;
  const stamp = JSON.stringify({
    pending: pendingTeam,
    teams: (state.teams || []).map((t) => [
      t.id,
      t.score,
      t.bucket,
      t.members.map((m) => [m.id, m.session_points]),
    ]),
  });
  if (stamp === lastStamp) return;
  lastStamp = stamp;
  document.getElementById("dash-link").href = `/class/${classId}`;
  document.getElementById("scoreboard-link").href = `/scoreboard/${classId}`;
  document.getElementById("title").textContent = "Teacher Game Dashboard";
  document.getElementById("meta").textContent =
    `${state.class.course_code} · ${state.session.header_label}`;
  const root = document.getElementById("teams");
  root.innerHTML = (state.teams || [])
    .map((team) => {
      const members = sortStudents(team.members, nameSort)
        .map(
          (s) => `<div class="student-row">
            <div>
              <strong>${escapeHtml(displayName(s, nameSort))}</strong>
              <div class="hint">credited ${escapeHtml(formatPoints(s.session_points))}</div>
            </div>
            <div class="pm">${studentButtons(s.id)}</div>
          </div>`
        )
        .join("");
      return `<section class="team-card" style="--team:${escapeHtml(team.color)}">
        <div class="team-head">
          <div>
            <h2>${escapeHtml(team.name)}</h2>
            <div class="hint">credited ${escapeHtml(formatPoints(team.individual_sum))} · team-only ${escapeHtml(formatPoints(team.bucket))}</div>
          </div>
          <div class="score-xl">${escapeHtml(formatPoints(team.score))}</div>
        </div>
        <div class="pm">${teamControls(team.id)}</div>
        ${members}
      </section>`;
    })
    .join("");
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
  window.open(`/scoreboard/${classId}`, "mgs-scoreboard");
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
