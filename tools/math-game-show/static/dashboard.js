import { api, classIdFromPath, displayName, escapeHtml, formatPoints, hideError, showError } from "./common.js";

const classId = classIdFromPath();
const sortKey = `mgs-sort-${classId}`;
let sort = localStorage.getItem(sortKey) === "first" ? "first" : "last";
let latest = null;

/**
 * Load and paint the class spreadsheet.
 */
async function refresh() {
  hideError("#error");
  const data = await api(`/api/classes/${classId}/dashboard?sort=${sort}`);
  paint(data);
}

/**
 * Apply a dashboard payload to the page.
 * @param {any} data
 */
function paint(data) {
  latest = data;
  const cls = data.class;
  document.getElementById("title").textContent = `${cls.course_code} · ${cls.year}`;
  document.getElementById("meta").textContent =
    `${cls.semester} · ${cls.days} · ${cls.time}`;
  document.getElementById("sort-toggle").textContent =
    sort === "first" ? "Sort: First Last" : "Sort: Last, First";
  renderSheet(data);
}

/**
 * Build the spreadsheet: class columns, frozen subtotals, live SUBTOTAL, TOTAL.
 * @param {any} data
 */
function renderSheet(data) {
  const table = document.getElementById("sheet");
  const columns = data.columns || (data.sessions || []).map((session) => ({
    kind: "session",
    ...session,
  }));
  const students = data.students || [];
  let html = "<thead><tr><th class='name'>Student</th>";
  for (const column of columns) {
    if (column.kind === "subtotal") {
      html += `<th class="subtotal-col">${escapeHtml(column.name || column.header_label)}</th>`;
      continue;
    }
    html += `<th>${escapeHtml(column.header_label)}`;
    if (column.status === "ended" && column.log_path) {
      html += `<a class="log-link" href="/api/sessions/${column.id}/log" target="_blank" rel="noopener">log</a>`;
    }
    html += `<button type="button" class="icon-btn" data-del-session="${column.id}" title="Delete column">×</button>`;
    html += "</th>";
  }
  html += "<th class='live-sub'>SUBTOTAL</th><th class='total'>TOTAL SCORE</th></tr></thead><tbody>";
  for (const student of students) {
    html += `<tr><td class="name">${escapeHtml(displayName(student, sort))}
      <button type="button" class="icon-btn" data-del-student="${student.id}" title="Remove student">×</button>
    </td>`;
    for (const column of columns) {
      if (column.kind === "subtotal") {
        const frozen = data.cells[`sub:${column.id}:${student.id}`] || { points: 0 };
        html += `<td class="cell frozen">${escapeHtml(formatPoints(frozen.points))}</td>`;
        continue;
      }
      const cell = data.cells[`${column.id}:${student.id}`] || { present: false, points: 0 };
      const kind = cell.present ? "present" : "absent";
      html += `<td class="cell ${kind}">${escapeHtml(formatPoints(cell.points))}</td>`;
    }
    const live = data.live_subtotals?.[String(student.id)] ?? 0;
    const total = data.totals[String(student.id)] ?? 0;
    html += `<td class="live-sub">${escapeHtml(formatPoints(live))}</td>`;
    html += `<td class="total">${escapeHtml(formatPoints(total))}</td></tr>`;
  }
  html += "</tbody>";
  table.innerHTML = html;
}

/**
 * POST a dashboard mutation and repaint.
 * @param {string} url
 * @param {object} extra
 */
async function mutate(url, extra) {
  hideError("#error");
  const data = await api(url, {
    method: "POST",
    body: JSON.stringify({ sort, ...extra }),
  });
  paint(data);
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

document.getElementById("add-student").addEventListener("submit", (event) => {
  event.preventDefault();
  const last = document.getElementById("new-last").value;
  const first = document.getElementById("new-first").value;
  mutate(`/api/classes/${classId}/students`, {
    first_name: first,
    last_display: last,
  })
    .then(() => {
      document.getElementById("new-last").value = "";
      document.getElementById("new-first").value = "";
    })
    .catch((err) => showError("#error", err));
});

document.getElementById("freeze-sub").addEventListener("submit", (event) => {
  event.preventDefault();
  const name = document.getElementById("sub-name").value;
  mutate(`/api/classes/${classId}/subtotals`, { name }).catch((err) =>
    showError("#error", err)
  );
});

/**
 * Ask the teacher to confirm a destructive delete.
 * @param {string} message
 * @returns {Promise<boolean>}
 */
function askToDelete(message) {
  const dialog = document.getElementById("confirm-dialog");
  const text = document.getElementById("confirm-message");
  if (!dialog || typeof dialog.showModal !== "function") {
    return Promise.resolve(window.confirm(message));
  }
  text.textContent = message;
  dialog.returnValue = "cancel";
  dialog.showModal();
  return new Promise((resolve) => {
    const finish = () => {
      dialog.removeEventListener("close", finish);
      resolve(dialog.returnValue === "ok");
    };
    dialog.addEventListener("close", finish);
  });
}

document.getElementById("confirm-dialog")?.addEventListener("click", (event) => {
  if (event.target === event.currentTarget) {
    event.currentTarget.close("cancel");
  }
});

document.getElementById("sheet").addEventListener("click", (event) => {
  const target = event.target instanceof Element ? event.target : event.target.parentElement;
  if (!target) return;
  const delStudent = target.closest("[data-del-student]");
  if (delStudent) {
    event.preventDefault();
    const id = Number(delStudent.dataset.delStudent);
    const student = (latest?.students || []).find((s) => s.id === id);
    const label = student ? displayName(student, sort) : "this student";
    askToDelete(`Delete student “${label}” from this class?\n\nThis cannot be undone.`).then(
      (ok) => {
        if (!ok) return;
        mutate(`/api/classes/${classId}/students/delete`, { student_id: id }).catch((err) =>
          showError("#error", err)
        );
      }
    );
    return;
  }
  const delSession = target.closest("[data-del-session]");
  if (delSession) {
    event.preventDefault();
    const id = Number(delSession.dataset.delSession);
    const column = (latest?.columns || latest?.sessions || []).find((c) => Number(c.id) === id);
    const header = column?.header_label || "this class column";
    askToDelete(
      `Delete class column “${header}” and all scores in it?\n\nThis cannot be undone.`
    ).then((ok) => {
      if (!ok) return;
      mutate(`/api/classes/${classId}/sessions/delete`, { session_id: id }).catch((err) =>
        showError("#error", err)
      );
    });
  }
});

refresh().catch((err) => showError("#error", err));
