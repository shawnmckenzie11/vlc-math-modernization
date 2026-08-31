/**
 * Always-on-top strip that loads the existing localhost scoreboard page.
 *
 * Usage (server already running):
 *   npm start -- --class=1
 *   npm start -- --class=1 --port=8766
 */
const { app, BrowserWindow, screen } = require("electron");

/**
 * Parse ``--name=value`` or ``--name value`` from process.argv.
 * @param {string} name
 * @param {string} fallback
 * @returns {string}
 */
function arg(name, fallback) {
  const flag = `--${name}`;
  const eq = process.argv.find((item) => item.startsWith(`${flag}=`));
  if (eq) return eq.slice(flag.length + 1);
  const index = process.argv.indexOf(flag);
  if (index >= 0 && process.argv[index + 1] && !process.argv[index + 1].startsWith("-")) {
    return process.argv[index + 1];
  }
  return fallback;
}

/**
 * Open a bottom-docked, always-on-top scoreboard window.
 */
function createWindow() {
  const classId = Number(arg("class", "1"));
  const host = arg("host", "127.0.0.1");
  const port = arg("port", "8766");
  const url = `http://${host}:${port}/scoreboard/${classId}?overlay=1`;
  const display = screen.getPrimaryDisplay().workArea;
  const height = Math.min(180, Math.max(120, Math.round(display.height * 0.16)));
  const win = new BrowserWindow({
    width: display.width,
    height,
    x: display.x,
    y: display.y + display.height - height,
    frame: false,
    transparent: false,
    resizable: true,
    alwaysOnTop: true,
    skipTaskbar: false,
    fullscreenable: false,
    backgroundColor: "#07080a",
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  win.setAlwaysOnTop(true, "screen-saver");
  win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  win.loadURL(url);
}

app.whenReady().then(createWindow);
app.on("window-all-closed", () => app.quit());
