/**
 * Client-side filters for the Module 1 question bank page.
 */
(function () {
  "use strict";

  /**
   * Apply search / section / type filters to the bank table rows.
   */
  function applyFilters() {
    const q = (document.getElementById("filter-q").value || "").trim().toLowerCase();
    const section = document.getElementById("filter-section").value;
    const type = document.getElementById("filter-type").value;
    const rows = document.querySelectorAll("#bank-table tbody tr");
    let visible = 0;
    rows.forEach((row) => {
      const hay = [
        row.getAttribute("data-smart-id") || "",
        row.getAttribute("data-section") || "",
        row.getAttribute("data-type") || "",
        row.getAttribute("data-expectations") || "",
        row.getAttribute("data-title") || "",
        row.getAttribute("data-preview") || "",
      ].join(" ");
      const okQ = !q || hay.includes(q);
      const okS = !section || row.getAttribute("data-section") === section;
      const okT = !type || row.getAttribute("data-type") === type;
      const show = okQ && okS && okT;
      row.classList.toggle("is-hidden", !show);
      if (show) visible += 1;
    });
    const count = document.getElementById("bank-count");
    if (count) {
      count.textContent = visible + " question" + (visible === 1 ? "" : "s");
    }
  }

  /**
   * Bind filter controls once the DOM is ready.
   */
  function init() {
    ["filter-q", "filter-section", "filter-type"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener("input", applyFilters);
        el.addEventListener("change", applyFilters);
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
