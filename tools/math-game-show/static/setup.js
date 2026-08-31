import {
  api,
  classIdFromPath,
  dashboardSort,
  displayName,
  escapeHtml,
  hideError,
  showError,
  sortStudents,
} from "./common.js";

const classId = classIdFromPath();
const nameSort = dashboardSort(classId);
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
  fillTimeOptions(state);
  const dateEl = $("meeting-date");
  if (dateEl && state.session.meeting_date) {
    dateEl.value = state.session.meeting_date;
  }
  const timeEl = $("meeting-time");
  if (timeEl && state.session.time) {
    timeEl.value = state.session.time;
  }
  if (status === "live") {
    location.replace(`/class/${classId}/game`);
    return;
  }
  $("step-attendance").classList.toggle("hidden", status !== "attendance");
  $("step-teams").classList.toggle("hidden", status !== "teams");
  $("step-names").classList.toggle("hidden", status !== "names");
  if (status !== "teams") hideManualAssign();
  if (status === "attendance") renderAttendance();
  if (status === "teams") {
    const present = (state.present_ids || []).length;
    $("n-teams").max = String(Math.max(2, present));
    $("n-teams").value = String(Math.min(2, present) || 2);
  }
  if (status === "names") renderNames();
}

/**
 * Present students in dashboard name order.
 * @returns {Array<{id:number, first_name:string, last_display:string}>}
 */
function presentStudents() {
  const present = new Set(state.present_ids || []);
  return sortStudents(
    (state.students || []).filter((student) => present.has(student.id)),
    nameSort
  );
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
  for (const student of sortStudents(state.students, nameSort)) {
    const id = `att-${student.id}`;
    const row = document.createElement("label");
    row.innerHTML = `<input type="checkbox" id="${id}" value="${student.id}"> ${escapeHtml(displayName(student, nameSort))}`;
    list.appendChild(row);
    row.querySelector("input").checked = checked.has(student.id);
  }
  updateAttCount();
}

/**
 * Live present count beside Mark Attendance.
 */
function updateAttCount() {
  const el = $("att-count");
  if (!el) return;
  el.textContent = `Attendance: ${selectedPresent().length}`;
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

/**
 * Hide the per-student team picker.
 */
function hideManualAssign() {
  const panel = $("manual-assign");
  if (panel) panel.classList.add("hidden");
}

/**
 * Draw a team dropdown for each present student.
 */
function renderManualAssign() {
  const nTeams = Number($("n-teams").value);
  const list = $("manual-list");
  const options = Array.from({ length: Math.max(0, nTeams) }, (_, index) => {
    return `<option value="${index}">Team ${index + 1}</option>`;
  }).join("");
  list.innerHTML = presentStudents()
    .map((student) => {
      return `<label class="manual-row">
        <span>${escapeHtml(displayName(student, nameSort))}</span>
        <select data-student-id="${student.id}">${options}</select>
      </label>`;
    })
    .join("");
  list.querySelectorAll("select").forEach((select, index) => {
    const n = Math.max(1, nTeams);
    select.value = String(index % n);
  });
  $("manual-assign").classList.remove("hidden");
}

/**
 * Read the manual picker into API assignment rows.
 * @returns {{student_id:number, team_index:number}[]}
 */
function manualAssignments() {
  return [...document.querySelectorAll("#manual-list select")].map((el) => ({
    student_id: Number(el.dataset.studentId),
    team_index: Number(el.value),
  }));
}

$("att-all").addEventListener("click", () => {
  document.querySelectorAll("#att-list input").forEach((el) => {
    el.checked = true;
  });
  updateAttCount();
});
$("att-none").addEventListener("click", () => {
  document.querySelectorAll("#att-list input").forEach((el) => {
    el.checked = false;
  });
  updateAttCount();
});
$("att-list").addEventListener("change", updateAttCount);

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
 * Assign present students randomly, balanced, or from the manual picker.
 * @param {"random"|"balanced"|"manual"} mode
 */
async function assign(mode) {
  hideError("#error");
  const payload = { n_teams: Number($("n-teams").value), mode };
  if (mode === "manual") payload.assignments = manualAssignments();
  try {
    state = await api(`/api/classes/${classId}/game/assign`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    hideManualAssign();
    await load();
  } catch (err) {
    showError("#error", err);
  }
}

$("assign-random").addEventListener("click", () => assign("random"));
$("assign-balanced").addEventListener("click", () => assign("balanced"));
$("assign-manual").addEventListener("click", () => {
  hideError("#error");
  renderManualAssign();
});
$("manual-cancel").addEventListener("click", hideManualAssign);
$("manual-confirm").addEventListener("click", () => assign("manual"));
$("n-teams").addEventListener("change", () => {
  if (!$("manual-assign").classList.contains("hidden")) renderManualAssign();
});

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

/**
 * Abort setup and return to the class spreadsheet.
 */
async function cancelSetup() {
  hideError("#error");
  try {
    await api(`/api/classes/${classId}/game/cancel`, { method: "POST", body: "{}" });
    location.href = `/class/${classId}`;
  } catch (err) {
    showError("#error", err);
  }
}

["cancel-setup-att", "cancel-setup-teams", "cancel-setup-names"].forEach((id) => {
  const el = $(id);
  if (el) el.addEventListener("click", cancelSetup);
});

/**
 * Fill the manual time dropdown from the server's wizard times.
 * @param {any} payload
 */
function fillTimeOptions(payload) {
  const select = $("meeting-time");
  const options = payload.time_options || [];
  if (!select || select.dataset.filled === "1") {
    if (select && payload.session && payload.session.time) {
      select.value = payload.session.time;
    }
    return;
  }
  select.innerHTML = options
    .map((t) => `<option value="${escapeHtml(t)}">${escapeHtml(t)}</option>`)
    .join("");
  select.dataset.filled = "1";
  if (payload.session && payload.session.time) {
    select.value = payload.session.time;
  }
}

$("select-manually").addEventListener("click", () => {
  $("manual-picker").classList.remove("hidden");
});

$("close-picker").addEventListener("click", () => {
  $("manual-picker").classList.add("hidden");
});

$("apply-meeting").addEventListener("click", async () => {
  hideError("#error");
  const meetingDate = $("meeting-date").value;
  const time = $("meeting-time").value;
  if (!meetingDate) {
    showError("#error", new Error("Choose a date"));
    return;
  }
  try {
    state = await api(`/api/classes/${classId}/game/meeting`, {
      method: "POST",
      body: JSON.stringify({ meeting_date: meetingDate, time }),
    });
    $("manual-picker").classList.add("hidden");
    await load();
  } catch (err) {
    showError("#error", err);
  }
});

load().catch((err) => showError("#error", err));
