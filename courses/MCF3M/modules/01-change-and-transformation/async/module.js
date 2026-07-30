/**
 * Client-side formative checking for Module 1 async page.
 * Feedback is revealed only after the student submits an attempt.
 */
(function () {
  "use strict";

  /**
   * Bind submit / reset handlers for every formative block on the page.
   */
  function initFormatives() {
    document.querySelectorAll("[data-formative]").forEach((block) => {
      const form = block.querySelector("form");
      const feedback = block.querySelector(".feedback");
      const submitBtn = block.querySelector('[data-action="submit"]');
      const resetBtn = block.querySelector('[data-action="reset"]');
      if (!form || !feedback || !submitBtn) return;

      form.addEventListener("submit", (event) => {
        event.preventDefault();
        const selected = form.querySelector('input[name="choice"]:checked');
        if (!selected) {
          feedback.className = "feedback visible incorrect";
          feedback.innerHTML =
            "<strong>Pick an option first.</strong> Then submit to see feedback.";
          return;
        }
        const correct = selected.getAttribute("data-correct") === "true";
        const msg = correct
          ? block.getAttribute("data-feedback-correct") || "Correct."
          : block.getAttribute("data-feedback-incorrect") || "Not quite.";
        feedback.className =
          "feedback visible " + (correct ? "correct" : "incorrect");
        feedback.innerHTML =
          "<strong>" +
          (correct ? "Correct." : "Not yet.") +
          "</strong> " +
          msg;
        submitBtn.disabled = true;
        form
          .querySelectorAll('input[name="choice"]')
          .forEach((el) => (el.disabled = true));
      });

      if (resetBtn) {
        resetBtn.addEventListener("click", () => {
          form.reset();
          form
            .querySelectorAll('input[name="choice"]')
            .forEach((el) => (el.disabled = false));
          submitBtn.disabled = false;
          feedback.className = "feedback";
          feedback.innerHTML = "";
        });
      }
    });
  }

  /**
   * Tab switching for same-content Explore media groups only.
   */
  function initExploreTabs() {
    document.querySelectorAll("[data-explore-tabs]").forEach((block) => {
      const tabs = block.querySelectorAll('[role="tab"]');
      tabs.forEach((tab) => {
        tab.addEventListener("click", () => {
          const panelId = tab.getAttribute("data-tab-panel");
          tabs.forEach((t) => t.setAttribute("aria-selected", "false"));
          tab.setAttribute("aria-selected", "true");
          block.querySelectorAll('[role="tabpanel"]').forEach((panel) => {
            if (panel.id === panelId) panel.removeAttribute("hidden");
            else panel.setAttribute("hidden", "");
          });
        });
      });
    });
  }

  function initAll() {
    initFormatives();
    initExploreTabs();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAll);
  } else {
    initAll();
  }
})();
