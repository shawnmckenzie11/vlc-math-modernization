import { api, classIdFromPath, displayName, escapeHtml, hideError, showError } from "./common.js";

const classId = classIdFromPath();
let state = null;

const $ = (id) => document.getElementById(id);

/**
 * Fetch open-game state and show the matching setup step.
 */
async function load() {
  hideError("#error");
  state = await api(`/api/classes/${classId}/game`);
  const status = state.game.status;
  $("meta").textContent = `${state.class.course_code} · ${state.session.header_label}`;
  $("back-dash").href = `/class/${classId}`;
  if (status === "live") {
    location.replace(`/class/${classId}/game`);
    return;
  }
  $("step-attendance").classList.toggle("hidden", status !== "attendance");
  $("step-teams").classList.toggle("hidden", status !== "teams");
  $("step-names").classList.toggle("hidden", status !== "names");
  if (status === "attendance") renderAttendance();
  if (status === "teams") {
    const present = (state.present_ids || []).length;
    $("n-teams").max = String(Math.max(2, present));
    $("n-teams").value = String(Math.min(2, present) || 2);
  }
  if (status === "names") renderNames();
}

/**
 * Draw attendance checkboxes. First game: all unchecked. Later: previous column.
 */
function renderAttendance() {
  const checked = new Set(
    (state.present_ids && state.present_ids.length
      ? state.present_ids
      : state.default_present_ids) || []
  );
  const list = $("att-list");
  list.innerHTML = "";
  for (const student of state.students) {
    const id = `att-${student.id}`;
    const row = document.createElement("label");
    row.innerHTML = `<input type="checkbox" id="${id}" value="${student.id}"> ${escapeHtml(displayName(student, "last"))}`;
    list.appendChild(row);
    row.querySelector("input").checked = checked.has(student.id);
  }
}

/**
 * Collect checked student ids from the attendance list.
 * @returns {number[]}
 */
function selectedPresent() {
  return [...document.querySelectorAll("#att-list input:checked")].map((el) => Number(el.value));
}

/**
 * Team rename inputs, defaulting to Team 1, Team 2, …
 */
function renderNames() {
  const box = $("name-list");
  box.innerHTML = "";
  for (const team of state.teams) {
    const wrap = document.createElement("label");
    wrap.className = "field";
    wrap.style.marginTop = "12px";
    wrap.innerHTML = `Team ${team.sort_order + 1} (${team.members.length} students)<input type="text" data-team-id="${team.id}" value="${escapeHtml(team.name)}">`;
    box.appendChild(wrap);
  }
}

$("att-all").addEventListener("click", () => {
  document.querySelectorAll("#att-list input").forEach((el) => {
    el.checked = true;
  });
});
$("att-none").addEventListener("click", () => {
  document.querySelectorAll("#att-list input").forEach((el) => {
    el.checked = false;
  });
});

$("att-next").addEventListener("click", async () => {
  try {
    state = await api(`/api/classes/${classId}/game/attendance`, {
      method: "POST",
      body: JSON.stringify({ present_ids: selectedPresent() }),
    });
    await load();
  } catch (err) {
    showError("#error", err);
  }
});

$("teams-back").addEventListener("click", async () => {
  try {
    await api(`/api/classes/${classId}/game/step`, {
      method: "POST",
      body: JSON.stringify({ status: "attendance" }),
    });
    await load();
  } catch (err) {
    showError("#error", err);
  }
});

/**
 * Assign present students randomly or balanced, then show rename.
 * @param {"random"|"balanced"} mode
 */
async function assign(mode) {
  hideError("#error");
  try {
    state = await api(`/api/classes/${classId}/game/assign`, {
      method: "POST",
      body: JSON.stringify({ n_teams: Number($("n-teams").value), mode }),
    });
    await load();
  } catch (err) {
    showError("#error", err);
  }
}

$("assign-random").addEventListener("click", () => assign("random"));
$("assign-balanced").addEventListener("click", () => assign("balanced"));

$("names-back").addEventListener("click", async () => {
  try {
    await api(`/api/classes/${classId}/game/step`, {
      method: "POST",
      body: JSON.stringify({ status: "teams" }),
    });
    await load();
  } catch (err) {
    showError("#error", err);
  }
});

$("start-game").addEventListener("click", async () => {
  hideError("#error");
  const teams = [...document.querySelectorAll("#name-list input")].map((el) => ({
    id: Number(el.dataset.teamId),
    name: el.value,
  }));
  try {
    await api(`/api/classes/${classId}/game/rename`, {
      method: "POST",
      body: JSON.stringify({ teams }),
    });
    location.href = `/class/${classId}/game?openscoreboard=1`;
  } catch (err) {
    showError("#error", err);
  }
});

load().catch((err) => showError("#error", err));
