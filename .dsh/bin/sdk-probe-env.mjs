// 模拟 DSH_HOME=harness 环境（用户通过 DSH Desktop wrapper 启动的场景）
import { spawn } from "node:child_process";
import readline from "node:readline";

const SDK_BIN = "C:\\Users\\xingk\\.dsh\\profiles\\node_modules\\@deepseek-ai\\dsh\\lib\\bin.js";
const DSH_HOME_OVERRIDE = process.argv[2] || "";

console.log("DSH_HOME = [" + DSH_HOME_OVERRIDE + "]");
const env = { ...process.env };
if (DSH_HOME_OVERRIDE) env.DSH_HOME = DSH_HOME_OVERRIDE;
else delete env.DSH_HOME;

const child = spawn("node", [SDK_BIN, "--profile", "dsh-lark-sdk"], {
  stdio: ["pipe", "pipe", "inherit"],
  env
});

let nextId = 1;
const pending = new Map();
const events = [];
const rl = readline.createInterface({ input: child.stdout });

rl.on("line", (line) => {
  if (!line.trim()) return;
  try {
    const frame = JSON.parse(line);
    if (frame.id !== undefined && pending.has(frame.id)) {
      const { resolve, reject } = pending.get(frame.id);
      pending.delete(frame.id);
      if (frame.error) reject(new Error(JSON.stringify(frame.error)));
      else resolve(frame.result);
    } else if (frame.method) {
      events.push(frame);
    }
  } catch {
    events.push({ raw: line });
  }
});

function request(method, params, timeoutMs = 60000) {
  return new Promise((resolve, reject) => {
    const id = String(nextId++);
    pending.set(id, { resolve, reject });
    child.stdin.write(JSON.stringify({ id, method, params }) + "\n");
    setTimeout(() => {
      if (pending.has(id)) {
        pending.delete(id);
        reject(new Error(`timeout waiting for ${method}`));
      }
    }, timeoutMs);
  });
}

async function main() {
  try {
    console.log("== initialize ==");
    const init = await request("initialize", {
      cwd: "C:\\Users\\xingk\\.dsh-lark\\profiles\\default\\workspace",
      provider: "minimax-cn",
      model: "minimax-m3"
    });
    console.log("init OK:", JSON.stringify(init).slice(0, 200));
    console.log("== session/prompt ==");
    const p = await request("session/prompt", {
      sessionId: "dshenv-probe-" + Date.now(),
      contentBlocks: [{ type: "text", text: "reply: hi" }]
    }, 90000);
    console.log("prompt OK:", JSON.stringify(p).slice(0, 200));
    await new Promise((r) => setTimeout(r, 15000));
    const lastEvents = events.slice(-6);
    for (const e of lastEvents) {
      console.log("EVENT:", JSON.stringify(e).slice(0, 400));
    }
  } catch (e) {
    console.error("=== ERROR ===");
    console.error(e.message);
    process.exitCode = 1;
  } finally {
    try { child.stdin.write(JSON.stringify({ id: "shutdown", method: "shutdown", params: {} }) + "\n"); } catch {}
    setTimeout(() => child.kill(), 1000);
  }
}

main();