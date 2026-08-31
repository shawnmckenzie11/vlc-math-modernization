import { api, classIdFromPath, displayName, escapeHtml, hideError, showError } from "./common.js";

const classId = classIdFromPath();
const AMOUNTS = [1, 5, 10, -1, -5, -10];

/**
 * +/- buttons for a student or a team bucket.
 * Future TODO: students awarding points to one another. Teacher-only for now.
 * @param {"student"|"team"} kind
 * @param {number} id
 */
function pmButtons(kind, id) {
  return AMOUNTS.map(
    (n) =>
      `<button type="button" data-kind="${kind}" data-id="${id}" data-amount="${n}">${n > 0 ? "+" : ""}${n}</button>`
  ).join("");
}

let lastStamp = "";

/**
 * Paint present students grouped by team with live session points.
 * @param {any} state
 */
function render(state) {
  const stamp = JSON.stringify(
    (state.teams || []).map((t) => [
      t.id,
      t.score,
      t.bucket,
      t.members.map((m) => [m.id, m.session_points]),
    ])
  );
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
      const members = team.members
        .map(
          (s) => `<div class="student-row">
            <div>
              <strong>${escapeHtml(displayName(s, "first"))}</strong>
              <div class="hint">session ${escapeHtml(s.session_points)}</div>
            </div>
            <div class="pm">${pmButtons("student", s.id)}</div>
          </div>`
        )
        .join("");
      return `<section class="team-card" style="--team:${escapeHtml(team.color)}">
        <div class="team-head">
          <div>
            <h2>${escapeHtml(team.name)}</h2>
            <div class="hint">individuals ${team.individual_sum} · team bucket ${team.bucket}</div>
          </div>
          <div class="score-xl">${escapeHtml(team.score)}</div>
        </div>
        <div class="pm">${pmButtons("team", team.id)}</div>
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
 */
async function award(kind, id, amount) {
  hideError("#error");
    const state = await api(`/api/classes/${classId}/game/score`, {
      method: "POST",
      body: JSON.stringify({ kind, id, amount }),
    });
    lastStamp = "";
    render(state);
}

document.getElementById("teams").addEventListener("click", (event) => {
  const btn = event.target.closest("button[data-kind]");
  if (!btn) return;
  award(btn.dataset.kind, Number(btn.dataset.id), Number(btn.dataset.amount)).catch((err) =>
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
