import { api, classIdFromPath, displayName, escapeHtml, hideError, showError } from "./common.js";

const classId = classIdFromPath();
const sortKey = `mgs-sort-${classId}`;
let sort = localStorage.getItem(sortKey) === "first" ? "first" : "last";

/**
 * Load and paint the class spreadsheet.
 */
async function refresh() {
  hideError("#error");
  const data = await api(`/api/classes/${classId}/dashboard?sort=${sort}`);
  const cls = data.class;
  document.getElementById("title").textContent = `${cls.course_code} · ${cls.year}`;
  document.getElementById("meta").textContent =
    `${cls.semester} · ${cls.days} · ${cls.time}`;
  document.getElementById("sort-toggle").textContent =
    sort === "first" ? "Sort: First Last" : "Sort: Last, First";
  renderSheet(data);
}

/**
 * Build the Excel-like table: names, one-or-more date columns, frozen TOTAL.
 * Future TODO: add/remove student rows; add/delete session columns by hand.
 * Future TODO: freeze TOTAL as a subtotal and start a fresh count afterward.
 * @param {any} data
 */
function renderSheet(data) {
  const table = document.getElementById("sheet");
  const sessions = data.sessions || [];
  const students = data.students || [];
  let html = "<thead><tr><th class='name'>Student</th>";
  for (const session of sessions) {
    html += `<th>${escapeHtml(session.header_label)}`;
    if (session.status === "ended" && session.log_path) {
      html += `<a class="log-link" href="/api/sessions/${session.id}/log" target="_blank" rel="noopener">log</a>`;
    }
    html += "</th>";
  }
  html += "<th class='total'>TOTAL SCORE</th></tr></thead><tbody>";
  for (const student of students) {
    html += `<tr><td class="name">${escapeHtml(displayName(student, sort))}</td>`;
    for (const session of sessions) {
      const cell = data.cells[`${session.id}:${student.id}`] || { present: false, points: 0 };
      const kind = cell.present ? "present" : "absent";
      html += `<td class="cell ${kind}">${escapeHtml(cell.points)}</td>`;
    }
    const total = data.totals[String(student.id)] ?? 0;
    html += `<td class="total">${escapeHtml(total)}</td></tr>`;
  }
  html += "</tbody>";
  table.innerHTML = html;
}

document.getElementById("sort-toggle").addEventListener("click", () => {
  sort = sort === "first" ? "last" : "first";
  localStorage.setItem(sortKey, sort);
  refresh().catch((err) => showError("#error", err));
});

document.getElementById("begin").addEventListener("click", async () => {
  hideError("#error");
  try {
    const state = await api(`/api/classes/${classId}/begin`, {
      method: "POST",
      body: "{}",
    });
    const status = state.game && state.game.status;
    if (status === "live") {
      location.href = `/class/${classId}/game?openscoreboard=1`;
      return;
    }
    location.href = `/class/${classId}/setup`;
  } catch (err) {
    showError("#error", err);
  }
});

refresh().catch((err) => showError("#error", err));
