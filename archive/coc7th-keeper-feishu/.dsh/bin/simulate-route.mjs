// 完整模拟 dsh-lark-bot 的 provider 解析链路（buildAgentAdapter 的核心逻辑）
// 看它实际用什么 provider/model，以及 SDK 调用是否成功
import { homedir } from "node:os";
import { join } from "node:path";
import { spawn } from "node:child_process";
import readline from "node:readline";

// 1. 模拟 DshProviderManager 的 settings 读取
const BOT_CLI = "C:\\Users\\xingk\\.dsh\\profiles\\dsh-lark\\node_modules\\dsh-lark-bot\\dist\\cli.js";

// 直接 import dsh-lark-bot 的 cli.js 不行（无导出），改为手动实现同样逻辑
const { resolveDshHome } = await import("file:///C:/Users/xingk/AppData/Local/Programs/DSH%20Desktop/resources/app/node_modules/@deepseek-ai/dsh-home-paths/lib/index.js");

console.log("=== 模拟 DshProviderManager ===");
const home = homedir();
console.log("home (homedir()):", home);
const dshHome = resolveDshHome(home, process.env);
console.log("resolveDshHome(homedir(), process.env) =", dshHome);
console.log("DSH_HOME env =", process.env.DSH_HOME ?? "(unset)");

const settingsFile = join(dshHome, "settings.yaml");
const credFile = join(dshHome, ".credentials.yaml");
console.log("settingsFile:", settingsFile, "exists:", (await import("node:fs")).existsSync(settingsFile));
console.log("credFile:", credFile, "exists:", (await import("node:fs")).existsSync(credFile));

// 读 settings（dsh-lark-bot 内部用 js-yaml）
const fs = await import("node:fs");
const yaml = (await import("file:///C:/Users/xingk/.dsh/profiles/dsh-lark/node_modules/.pnpm/yaml@2.9.0/node_modules/yaml/browser/index.js")).default ?? null;
if (!yaml) {
  console.log("yaml not loadable, skip content check");
} else if (fs.existsSync(settingsFile)) {
  const settings = yaml.parse(fs.readFileSync(settingsFile, "utf8"));
  const adm = settings["agent-default-model"];
  console.log("agent-default-model:", JSON.stringify(adm));
  // 模拟 defaultModelSelectionFromSettings
  const route = (typeof adm === "object" && typeof adm.model === "string")
    ? { provider: typeof adm.provider === "string" ? adm.provider : "deepseek-official", model: adm.model }
    : undefined;
  console.log("defaultModelSelection =>", JSON.stringify(route));
}

// 2. 检查 credentials
if (fs.existsSync(credFile)) {
  const creds = yaml.parse(fs.readFileSync(credFile, "utf8"));
  console.log("has MINIMAX_CN_API_KEY:", Boolean(creds?.refs?.["MINIMAX_CN_API_KEY"]));
}

console.log("\n=== 模拟 SDK launch（discoverDshBin）===");
const DS_HARNESS_RELATIVE = "@deepseek-ai" + "/" + "dsh";
const candidates = [
  join(dshHome, "profiles", "node_modules", DS_HARNESS_RELATIVE),
  join(home, ".dsh", "profiles", "node_modules", DS_HARNESS_RELATIVE),
  join(home, ".npm", "_npx", "node_modules", DS_HARNESS_RELATIVE)
];
for (const c of candidates) {
  console.log("candidate:", c, "exists:", fs.existsSync(c));
}
const foundBin = candidates.find((p) => fs.existsSync(p));
console.log("resolved SDK bin:", foundBin ?? "(none -> fallback to PATH dsh)");