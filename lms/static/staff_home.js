import { api, hideError, showError } from "/static/common.js";

const STEPS = ["roster", "days", "time"];
const TITLES = {
  offering: "Assigned course",
  roster: "Codenames",
  days: "Days",
  time: "Time",
};

let step = 0;
const names = [];

const $ = (id) => document.getElementById(id);

/**
 * Paint the repeatable Codename list and live count.
 */
function renderRoster() {
  const list = $("codename-list");
  if (!list) return;
  list.innerHTML = names
    .map(
      (name, i) =>
        `<div>${escapeText(name)} <button type="button" class="secondary" data-i="${i}">Remove</button></div>`
    )
    .join("");
  const count = $("roster-count");
  if (count) count.textContent = String(names.length);
}

/**
 * Escape text for HTML insertion.
 * @param {string} value
 */
function escapeText(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/**
 * Add one or more Codenames from a field or pasted lines.
 * @param {string} raw
 */
function addNames(raw) {
  const lines = String(raw || "")
    .split(/\n/)
    .map((s) => s.trim())
    .filter(Boolean);
  for (const line of lines) {
    if (line.includes(",")) {
      showError("#error", "Codenames cannot contain commas.");
      return;
    }
    if (line.length < 2 || line.length > 32) {
      showError("#error", "Codenames must be 2–32 characters.");
      return;
    }
    if (names.some((n) => n.toLowerCase() === line.toLowerCase())) {
      showError("#error", `Duplicate Codename: ${line}`);
      return;
    }
    names.push(line);
  }
  hideError("#error");
  renderRoster();
}

/**
 * Show the assigned-course dashboard.
 */
function showPicker() {
  $("course-dash")?.classList.remove("hidden");
  $("wizard")?.classList.add("hidden");
  hideError("#error");
}

/**
 * Start the roster wizard for one IT-assigned course.
 * @param {string} offeringId
 */
function startPopulate(offeringId) {
  const select = $("offering");
  if (select) select.value = String(offeringId);
  const label = select?.selectedOptions?.[0]?.textContent || "";
  const chosen = $("offering-chosen");
  if (chosen) chosen.textContent = label;
  $("course-dash")?.classList.add("hidden");
  $("wizard")?.classList.remove("hidden");
  step = 0;
  names.length = 0;
  renderRoster();
  renderStep();
}

/**
 * Show one wizard step.
 */
function renderStep() {
  const key = STEPS[step];
  $("wiz-progress").textContent = `Step ${step + 1} of ${STEPS.length}`;
  $("wiz-title").textContent = TITLES[key] || "Populate Class";
  for (const name of ["offering", "roster", "days", "time"]) {
    const el = $(`step-${name}`);
    if (!el) continue;
    el.classList.toggle("hidden", name !== key);
  }
  $("wiz-back").textContent = step === 0 ? "Cancel" : "Back";
  $("wiz-next").textContent = step === STEPS.length - 1 ? "Populate class" : "Next";
}

/**
 * Validate the current step.
 * @returns {boolean}
 */
function validateStep() {
  hideError("#error");
  const key = STEPS[step];
  if (key === "offering" && !$("offering")?.value) {
    showError("#error", "Choose an assigned course.");
    return false;
  }
  if (key === "roster" && names.length < 1) {
    showError("#error", "Add at least one Codename.");
    return false;
  }
  return true;
}

/**
 * POST the class and open the course dashboard.
 */
async function submitClass() {
  const offering = $("offering");
  const payload = {
    offering_id: Number(offering?.value),
    days: $("days").value,
    time: $("time").value,
    codenames: names,
  };
  const data = await api("/api/staff/classes", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  location.href = `/staff/class/${data.class.id}`;
}

document.querySelectorAll(".btn-populate").forEach((btn) => {
  btn.addEventListener("click", () => {
    startPopulate(btn.getAttribute("data-offering-id") || "");
  });
});

$("wiz-back")?.addEventListener("click", () => {
  if (step === 0) {
    showPicker();
    return;
  }
  step -= 1;
  renderStep();
});

$("wiz-next")?.addEventListener("click", async () => {
  if (!validateStep()) return;
  if (step === STEPS.length - 1) {
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

$("add-codename")?.addEventListener("click", () => {
  addNames($("codename-input").value);
  $("codename-input").value = "";
});

$("codename-input")?.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    addNames($("codename-input").value);
    $("codename-input").value = "";
  }
});

$("codename-paste")?.addEventListener("change", () => {
  addNames($("codename-paste").value);
  $("codename-paste").value = "";
});

$("codename-list")?.addEventListener("click", (event) => {
  const btn = event.target instanceof Element ? event.target.closest("[data-i]") : null;
  if (!btn) return;
  names.splice(Number(btn.dataset.i), 1);
  renderRoster();
});
