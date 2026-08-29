// 直接驱动 dsh-lark-sdk 进程，用 JSON-RPC 调用 session/prompt，捕获完整错误
// 用法: node sdk-probe.js
import { spawn } from "node:child_process";
import readline from "node:readline";

const SDK_BIN = "C:\\Users\\xingk\\.dsh\\profiles\\node_modules\\@deepseek-ai\\dsh\\lib\\bin.js";
const DSH_HOME = process.env.USERPROFILE + "\\.dsh";

console.log("Starting SDK process with DSH_HOME=" + DSH_HOME);

const child = spawn("node", [SDK_BIN, "--profile", "dsh-lark-sdk"], {
  stdio: ["pipe", "pipe", "inherit"],
  env: { ...process.env, DSH_HOME }
});

let nextId = 1;
const pending = new Map();
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
      // notification
      console.log("NOTIF:", JSON.stringify(frame).slice(0, 300));
    }
  } catch (e) {
    console.log("RAW:", line.slice(0, 300));
  }
});

function request(method, params, timeoutMs = 120000) {
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
    const init = await request("initialize", {});
    console.log("init result:", JSON.stringify(init).slice(0, 500));

    console.log("== session/prompt ==");
    const promptResult = await request("session/prompt", {
      cwd: "C:\\Users\\xingk\\.dsh-lark\\profiles\\default\\workspace",
      prompt: "只回复两个字：你好",
      model: { provider: "minimax-cn", model: "minimax-m3" }
    }, 120000);
    console.log("prompt result:", JSON.stringify(promptResult).slice(0, 2000));
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