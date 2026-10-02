import struct, sys, hashlib
p = sys.argv[1]
d = open(p, "rb").read()
M = b"~Module signature appended~\n"
if d.endswith(M):
    body = d[:-len(M)]
    # struct module_signature: algo,hash,id_type (u8), signer_len,key_id_len (u8), pad[3], sig_len (be32)
    sig_len = struct.unpack(">I", body[-4:])[0]
    total = 12 + sig_len
    out = body[:-total]
    print("signature stripped:", len(d), "->", len(out), "sig_len", sig_len)
    open(p, "wb").write(out)
else:
    print("no signature")
print(hashlib.md5(open(p, "rb").read()).hexdigest())
