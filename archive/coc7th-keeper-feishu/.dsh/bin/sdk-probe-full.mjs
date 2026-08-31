// 完整模拟 dsh-lark-bot spawn SDK 的场景（含 DSH_LARK_* 环境变量）
import { spawn } from "node:child_process";
import readline from "node:readline";

const SDK_BIN = "C:\\Users\\xingk\\.dsh\\profiles\\node_modules\\@deepseek-ai\\dsh\\lib\\bin.js";

// 模拟 dsh-lark-bot engine 模式设置的完整环境
const env = { ...process.env };
env.DSH_HOME = process.env.USERPROFILE + "\\.dsh"; // wrapper 固定的值
env.DSH_LARK_NOTIFY_URL = "http://127.0.0.1:5140/notify";
env.DSH_LARK_ASK_URL = "http://127.0.0.1:5140/ask";
env.DSH_LARK_PLAN_URL = "http://127.0.0.1:5140/plan";
env.DSH_LARK_APPROVAL_URL = "http://127.0.0.1:5140/approval";
env.DSH_LARK_FILE_URL = "http://127.0.0.1:5140/file";
env.DSH_LARK_SECRET_URL = "http://127.0.0.1:5140/secret";
env.DSH_LARK_NOTIFY_TOKEN = "probe-token";
env.DSH_LARK_PLAN_GATE = "off";

console.log("DSH_HOME =", env.DSH_HOME);

const child = spawn("node", [SDK_BIN, "--profile", "dsh-lark-sdk"], {
  stdio: ["pipe", "pipe", "pipe"],
  env
});

let stderrBuf = "";
child.stderr.on("data", (d) => { stderrBuf += d.toString(); });

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
    } else if (frame.method) events.push(frame);
  } catch { events.push({ raw: line.slice(0, 200) }); }
});

function request(method, params, timeoutMs = 90000) {
  return new Promise((resolve, reject) => {
    const id = String(nextId++);
    pending.set(id, { resolve, reject });
    child.stdin.write(JSON.stringify({ id, method, params }) + "\n");
    setTimeout(() => pending.has(id) && (pending.delete(id), reject(new Error("timeout: " + method))), timeoutMs);
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
    console.log("init OK:", JSON.stringify(init).slice(0, 150));

    console.log("== session/prompt（模拟 dsh-lark-bot 的完整场景）==");
    await request("session/prompt", {
      sessionId: "full-probe-" + Date.now(),
      contentBlocks: [{ type: "text", text: "Current user message:\n你好" }]
    }, 90000);
    console.log("prompt accepted, waiting for agent events...");
    await new Promise((r) => setTimeout(r, 25000));
    const interesting = events.filter((e) => {
      const s = JSON.stringify(e);
      return /error|failed|assistant\/message|turn\/end|step\/end/i.test(s);
    });
    console.log("interesting events:", interesting.length);
    for (const e of interesting.slice(-8)) console.log("EVENT:", JSON.stringify(e).slice(0, 500));
    if (stderrBuf) { console.log("=== SDK STDERR ==="); console.log(stderrBuf.slice(-3000)); }
  } catch (e) {
    console.error("=== REQUEST ERROR ===");
    console.error(e.message);
    if (stderrBuf) { console.log("=== SDK STDERR ==="); console.log(stderrBuf.slice(-3000)); }
    process.exitCode = 1;
  } finally {
    try { child.stdin.write(JSON.stringify({ id: "s", method: "shutdown", params: {} }) + "\n"); } catch {}
    setTimeout(() => child.kill(), 1500);
  }
}

main();