"""Analyze why tsc -b rejects tinyrainbow .d.ts: find non-ASCII / escape bytes."""
p = 'node_modules/vitest/node_modules/tinyrainbow/dist/index-c1cfc5e9.d.ts'
raw = open(p, 'rb').read()
print('n_bytes:', len(raw))
non_ascii = [(i, b) for i, b in enumerate(raw) if b > 127]
print('non-ascii count:', len(non_ascii))
for i, b in non_ascii[:20]:
    ctx = raw[max(0, i-30):i+10]
    print(f'byte@{i}: 0x{b:02x} context={ctx!r}')
lines = raw.split(b'\n')
print('n_lines:', len(lines))
# show first line hexdump-ish
print('first line repr:', lines[0][:80])
# check for BOM
print('BOM:', raw[:3] == b'\xef\xbb\xbf')
