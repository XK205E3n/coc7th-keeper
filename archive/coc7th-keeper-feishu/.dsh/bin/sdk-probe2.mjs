// 直接驱动 dsh-lark-sdk 进程，用 JSON-RPC 调用，捕获完整错误
// 用法: node sdk-probe2.mjs
import { spawn } from "node:child_process";
import readline from "node:readline";

const SDK_BIN = "C:\\Users\\xingk\\.dsh\\profiles\\node_modules\\@deepseek-ai\\dsh\\lib\\bin.js";

console.log("Starting SDK process...");
const cleanEnv = { ...process.env };
delete cleanEnv.DSH_HOME; // 清除 DSH Desktop 注入的污染，让 SDK 用默认 ~/.dsh
const child = spawn("node", [SDK_BIN, "--profile", "dsh-lark-sdk"], {
  stdio: ["pipe", "pipe", "inherit"],
  env: cleanEnv
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

function request(method, params, timeoutMs = 180000) {
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
    console.log("init OK:", JSON.stringify(init).slice(0, 400));

    console.log("== session/prompt ==");
    const p = await request("session/prompt", {
      sessionId: "sdk-probe-test",
      contentBlocks: [{ type: "text", text: "只回复两个字：你好" }]
    }, 180000);
    console.log("prompt OK:", JSON.stringify(p).slice(0, 400));
    console.log("events so far:", events.length);
    for (const e of events) {
      console.log("EVENT:", JSON.stringify(e).slice(0, 600));
    }
    // 等待 agent 完成
    console.log("== waiting 20s for agent events ==");
    await new Promise((r) => setTimeout(r, 20000));
    console.log("events after wait:", events.length);
    for (const e of events.slice(-10)) {
      console.log("EVENT:", JSON.stringify(e).slice(0, 800));
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