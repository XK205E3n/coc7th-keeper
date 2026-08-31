// 用 Node.js (DSH 自带) + 内置 zstd native bindings 读 session
const fs = require('fs');
const zstd = require('zlib');
const path = process.argv[2];
const buf = fs.readFileSync(path);
// 尝试 zstd decompress
let text;
try {
  text = zstd.zstdDecompressSync(buf).toString('utf-8');
} catch (e) {
  // 尝试 chunked
  try {
    const dctx = zstd.createZstdDecompress();
    dctx.writeSync && dctx.writeSync(buf);
    const chunks = [];
    dctx.onData = (chunk) => chunks.push(chunk);
    // fallback: brute
    text = buf.toString('utf-8');
  } catch (e2) {
    text = buf.toString('utf-8');
  }
}
console.log(text);