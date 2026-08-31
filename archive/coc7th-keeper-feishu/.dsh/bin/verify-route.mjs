// 验证 dsh-lark-bot 的 DshProviderManager 能否解析 minimax-cn/minimax-m3
// 模拟 buildAgentAdapter 里 resolveAdapterRoute 的调用路径
import { homedir } from "node:os";
import { join } from "node:path";

// 直接读取 dsh-lark-bot 内部导出（dist/cli.js 不导出，需要找导出面）
// 方案：用 createRequire 加载 SDK 侧暴露的 provider manager
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);

async function main() {
  // 从 dsh-lark-bot 包找 DshProviderManager 可用的导出
  const pkgRoot = "C:/Users/xingk/.dsh/profiles/dsh-lark/node_modules/dsh-lark-bot";
  const files = [
    join(pkgRoot, "dist", "cli.js"),
    join(pkgRoot, "dist", "sdk-server.js"),
    join(pkgRoot, "dist", "index.js"),
    join(pkgRoot, "dist", "plugin.js")
  ];
  for (const f of files) {
    try {
      const mod = await import("file://" + f.replace(/\\/g, "/"));
      const names = Object.keys(mod).filter(n => /Provider|Model|Route|resolve/i.test(n));
      console.log("EXPORT from", f.split("/").pop(), ":", names.slice(0, 20));
    } catch (e) {
      console.log("FAIL", f.split("/").pop(), e.message.slice(0, 120));
    }
  }
}
main();