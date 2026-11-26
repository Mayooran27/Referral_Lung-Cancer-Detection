// Starts the Flask backend (Backend/app.py) and the Vite dev server together,
// so `npm run dev` brings up the whole app. Ctrl+C stops both.
import { spawn } from "node:child_process";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const frontendDir = path.resolve(here, "..");
const backendDir = path.resolve(frontendDir, "..", "Backend");
// Use BACKEND_PYTHON to override (not PYTHON, which some Windows setups point at pip).
const python = process.env.BACKEND_PYTHON || (process.platform === "win32" ? "python" : "python3");
const backendPort = Number(process.env.PORT || 5000);

const children = [];

function run(name, cmd, args, cwd) {
  const child = spawn(cmd, args, { cwd, stdio: "inherit" });
  child.on("exit", (code) => {
    console.log(`[${name}] exited with code ${code}`);
    shutdown(code ?? 0);
  });
  children.push(child);
  return child;
}

function shutdown(code) {
  for (const c of children) if (!c.killed) c.kill();
  process.exit(code);
}
process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

function portInUse(port) {
  return new Promise((resolve) => {
    const sock = net.connect(port, "127.0.0.1");
    sock.once("connect", () => { sock.destroy(); resolve(true); });
    sock.once("error", () => resolve(false));
  });
}

async function waitForPort(port, timeoutMs) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (await portInUse(port)) return true;
    await new Promise((r) => setTimeout(r, 500));
  }
  return false;
}

if (await portInUse(backendPort)) {
  console.log(`[backend] already running on port ${backendPort}, reusing it`);
} else {
  console.log(`[backend] starting: ${python} app.py (in ${backendDir})`);
  run("backend", python, ["app.py"], backendDir);
  // Models can take a while to load; wait so the first page load doesn't hit proxy errors.
  if (!(await waitForPort(backendPort, 120000))) {
    console.warn(`[backend] not listening on port ${backendPort} after 120s, starting frontend anyway`);
  }
}

run("frontend", process.execPath, [path.join(frontendDir, "node_modules", "vite", "bin", "vite.js")], frontendDir);
