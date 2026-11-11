import re, struct, math, sys
src = open(sys.argv[1]).read()
body = src[src.index('confgenerator_serialize_mcconf'):]
body = body[:body.index('\n}\n')]
def f32auto(b):
    v = struct.unpack(">I", b)[0]
    if v == 0: return 0.0
    e = ((v >> 23) & 0xFF) - 126; sig = (v & 0x7FFFFF) / (8388608.0 * 2.0) + 0.5
    r = math.ldexp(sig, e); return -r if v & (1 << 31) else r
def decode(blob):
    out = {}; i = 0
    for line in body.split('\n'):
        line = line.strip()
        m = re.match(r'buffer\[ind\+\+\] = (?:\(uint8_t\))?conf->([\w\[\]\.]+)', line)
        if m: out[m.group(1)] = blob[i]; i += 1; continue
        m = re.match(r'buffer_append_float32_auto\(buffer, conf->([\w\[\]\.]+)', line)
        if m: out[m.group(1)] = f32auto(blob[i:i+4]); i += 4; continue
        m = re.match(r'buffer_append_float16\(buffer, conf->([\w\[\]\.]+), ([\d.e]+)', line)
        if m: out[m.group(1)] = struct.unpack(">h", blob[i:i+2])[0] / float(m.group(2)); i += 2; continue
        m = re.match(r'buffer_append_(u?int)(16|32)\(buffer, (?:conf->)?([\w\[\]\.]+)', line)
        if m:
            n = int(m.group(2)) // 8; fmt = {('int',2):'>h',('uint',2):'>H',('int',4):'>i',('uint',4):'>I'}[(m.group(1), n)]
            out[m.group(3)] = struct.unpack(fmt, blob[i:i+n])[0]; i += n; continue
        if 'ind' in line and 'int32_t ind' not in line and 'return' not in line: print('??', line)
    out['_len'] = i; return out
if __name__ == '__main__':
    for p in sys.argv[2:]:
        d = decode(open(p, 'rb').read())
        print(p, d['_len'])
