import { hideError, showError } from "/static/common.js";

let bootstrap = { offerings: [], classes: [], time_options: [], semester: null };
let stepKeys = [];
let step = 0;

const $ = (id) => document.getElementById(id);

/**
 * JSON fetch with {ok:false} handling.
 * @param {string} url
 * @param {RequestInit} [options]
 */
async function api(url, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
  const response = await fetch(url, { ...options, headers });
  const data = await response.json();
  if (!response.ok || data.ok === false) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

/**
 * Show the two-button picker.
 */
function showPicker() {
  $("mode-pick").classList.remove("hidden");
  $("wizard").classList.add("hidden");
  $("existing").classList.add("hidden");
  hideError("#error");
}

/**
 * Wizard keys skip year/semester/course; offering pick only if several courses.
 */
function wizardKeys() {
  const keys = [];
  if ((bootstrap.offerings || []).length !== 1) keys.push("offering");
  keys.push("codenames", "days", "time");
  return keys;
}

/**
 * Render the current populate step.
 */
function renderStep() {
  const key = stepKeys[step];
  $("wiz-progress").textContent = `Step ${step + 1} of ${stepKeys.length}`;
  const titles = {
    offering: "Assigned course",
    codenames: "Codenames",
    days: "Days",
    time: "Time",
  };
  $("wiz-title").textContent = titles[key] || "Populate Class";
  for (const name of ["offering", "codenames", "days", "time"]) {
    const el = $(`step-${name}`);
    if (el) el.classList.toggle("hidden", name !== key);
  }
  $("wiz-back").textContent = step === 0 ? "Cancel" : "Back";
  $("wiz-next").textContent = step === stepKeys.length - 1 ? "Populate class" : "Next";
}

/**
 * Validate the current wizard step.
 * @returns {boolean}
 */
function validateStep() {
  hideError("#error");
  const key = stepKeys[step];
  if (key === "offering" && !$("offering").value) {
    showError("#error", "Select an assigned course.");
    return false;
  }
  if (key === "codenames") {
    const names = $("codenames").value.split("\n").map((s) => s.trim()).filter(Boolean);
    if (!names.length) {
      showError("#error", "Enter at least one Codename.");
      return false;
    }
    $("code-status").textContent = `${names.length} Codename(s).`;
  }
  return true;
}

/**
 * Create the class from wizard fields.
 */
async function submitClass() {
  const offerings = bootstrap.offerings || [];
  const offeringId = offerings.length === 1
    ? offerings[0].id
    : Number($("offering").value);
  const payload = {
    offering_id: offeringId,
    days: $("days").value,
    time: $("time").value,
    codenames: $("codenames").value.split("\n").map((s) => s.trim()).filter(Boolean),
  };
  const data = await api("/api/staff/classes", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  location.href = `/staff/classes/${data.class.id}`;
}

/**
 * Fill offering + time selects from bootstrap.
 */
function fillControls() {
  const sem = bootstrap.semester;
  $("meta").textContent = sem
    ? `${sem.label} · inherited from IT`
    : "IT has not activated a semester yet.";
  const codes = [...new Set((bootstrap.offerings || []).map((o) => o.live_access_code))];
  $("access").textContent = codes.length
    ? `Student live-game code(s): ${codes.join(" · ")}`
    : "No courses assigned yet — ask IT.";
  $("offering").innerHTML = (bootstrap.offerings || [])
    .map((o) => `<option value="${o.id}">${o.ontario_code} · ${o.live_access_code}</option>`)
    .join("");
  $("time").innerHTML = (bootstrap.time_options || [])
    .map((t) => `<option value="${t}">${t}</option>`)
    .join("");
  $("time").value = "2:00pm";
}

/**
 * List this teacher's classes.
 */
function loadExisting() {
  hideError("#error");
  const list = $("class-list");
  list.innerHTML = "";
  const classes = bootstrap.classes || [];
  if (!classes.length) {
    list.textContent = "No populated classes yet.";
    return;
  }
  for (const cls of classes) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = `${cls.course_code} · ${cls.days} · ${cls.time}`;
    btn.addEventListener("click", () => {
      location.href = `/staff/classes/${cls.id}`;
    });
    list.appendChild(btn);
  }
}

$("btn-create").addEventListener("click", () => {
  if (!(bootstrap.offerings || []).length) {
    showError("#error", "IT has not assigned you a course yet.");
    return;
  }
  $("mode-pick").classList.add("hidden");
  $("wizard").classList.remove("hidden");
  stepKeys = wizardKeys();
  step = 0;
  renderStep();
});

$("btn-existing").addEventListener("click", () => {
  $("mode-pick").classList.add("hidden");
  $("existing").classList.remove("hidden");
  loadExisting();
});

$("exist-back").addEventListener("click", showPicker);
$("wiz-back").addEventListener("click", () => {
  if (step === 0) {
    showPicker();
    return;
  }
  step -= 1;
  renderStep();
});
$("wiz-next").addEventListener("click", async () => {
  if (!validateStep()) return;
  if (step === stepKeys.length - 1) {
    try {
      await submitClass();
    } catch (err) {
      showError("#error", err);
    }
    return;
  }
  step += 1;
  renderStep();
});

api("/api/staff/bootstrap")
  .then((data) => {
    bootstrap = data;
    fillControls();
  })
  .catch((err) => showError("#error", err));
