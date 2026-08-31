import zstandard as zstd, json, sys
dctx = zstd.ZstdDecompressor()
with open(sys.argv[1],'rb') as f:
    raw = dctx.stream_reader(f).read()
text = raw.decode('utf-8','replace')
print(text)