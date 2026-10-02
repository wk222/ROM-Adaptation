import struct, sys, re
def sig_blob(p):
    d = open(p, "rb").read()
    M = b"~Module signature appended~\n"
    if not d.endswith(M): return None
    body = d[:-len(M)]
    sig_len = struct.unpack(">I", body[-4:])[0]
    info = body[-12:]
    sig = body[-12 - sig_len:-12]
    return info, sig
for p in sys.argv[1:]:
    r = sig_blob(p)
    if not r: print(p, "UNSIGNED"); continue
    info, sig = r
    print(p, "algo/hash/id_type", info[0], info[1], info[2], "sig_len", len(sig))
    strs = re.findall(rb"[ -~]{6,}", sig)
    print("   strings:", [s.decode() for s in strs][:12])
    print("   sig head:", sig[:64].hex())
    print("   serial/issuer region:", sig[20:120].hex())
