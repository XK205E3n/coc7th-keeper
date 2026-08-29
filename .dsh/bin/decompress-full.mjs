// 完整解压 zstd 文件（读所有 frames）
import zlib from "node:zlib";
import fs from "node:fs";
const path = process.argv[2];
const buf = fs.readFileSync(path);
try {
  const out = zlib.zstdDecompressSync(buf);
  const text = out.toString("utf-8");
  console.log("=== FULL CONTENT (" + text.length + " chars) ===");
  console.log(text);
} catch (e) {
  console.log("zstdDecompressSync failed:", e.message);
  // 尝试逐行读取（NDJSON 每行独立压缩？）
  const lines = buf.toString("utf-8").split("\n");
  console.log("raw lines:", lines.length);
  for (const line of lines.slice(0, 5)) console.log("RAW:", line.slice(0, 200));
}