/** Shared helpers for the Math Game Show teacher UI. */

/**
 * Escape text for safe insertion into HTML.
 * @param {unknown} value
 * @returns {string}
 */
export function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/**
 * Parse a class id out of paths like /class/3/game or /scoreboard/3.
 * @returns {number}
 */
export function classIdFromPath() {
  const parts = location.pathname.split("/").filter(Boolean);
  const n = Number(parts[1]);
  if (!Number.isFinite(n) || n < 1) {
    throw new Error("Missing class id in URL");
  }
  return n;
}

/**
 * JSON fetch with {ok:false,error} handling.
 * @param {string} url
 * @param {RequestInit} [options]
 * @returns {Promise<any>}
 */
export async function api(url, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(url, { ...options, headers });
  const text = await response.text();
  let data = {};
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      throw new Error(text || `HTTP ${response.status}`);
    }
  }
  if (!response.ok || data.ok === false) {
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data;
}

/**
 * Show an error string on a page-level banner.
 * @param {string} selector
 * @param {unknown} err
 */
export function showError(selector, err) {
  const el = document.querySelector(selector);
  if (!el) return;
  el.hidden = false;
  el.textContent = err instanceof Error ? err.message : String(err);
}

/**
 * Hide a page-level banner.
 * @param {string} selector
 */
export function hideError(selector) {
  const el = document.querySelector(selector);
  if (!el) return;
  el.hidden = true;
  el.textContent = "";
}

/**
 * Student display name.
 * @param {{first_name:string, last_display:string}} student
 * @param {"first"|"last"} sort
 */
export function displayName(student, sort) {
  const first = (student.first_name || "").trim();
  const last = (student.last_display || "").trim();
  if (sort === "first") {
    return [first, last].filter(Boolean).join(" ");
  }
  return first ? `${last}, ${first}` : last;
}
