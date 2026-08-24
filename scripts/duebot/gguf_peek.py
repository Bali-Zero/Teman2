#!/usr/bin/env python3
"""Minimal dependency-free GGUF header/KV parser — reads only the metadata
section (a few KB), never touches tensor data. Used to verify the ACTUAL
quantization of a GGUF file from its own metadata, not its filename."""
import struct
import sys

GGUF_TYPE_MAP = {
    0: "u8", 1: "i8", 2: "u16", 3: "i16", 4: "u32", 5: "i32",
    6: "f32", 7: "bool", 8: "string", 9: "array", 10: "u64", 11: "i64", 12: "f64",
}

FILE_TYPE_NAMES = {
    0: "ALL_F32", 1: "MOSTLY_F16", 2: "MOSTLY_Q4_0", 3: "MOSTLY_Q4_1",
    7: "MOSTLY_Q8_0", 8: "MOSTLY_Q5_0", 9: "MOSTLY_Q5_1",
    10: "MOSTLY_Q2_K", 11: "MOSTLY_Q3_K_S", 12: "MOSTLY_Q3_K_M", 13: "MOSTLY_Q3_K_L",
    14: "MOSTLY_Q4_K_S", 15: "MOSTLY_Q4_K_M", 16: "MOSTLY_Q5_K_S", 17: "MOSTLY_Q5_K_M",
    18: "MOSTLY_Q6_K", 19: "MOSTLY_IQ2_XXS", 20: "MOSTLY_IQ2_XS", 21: "MOSTLY_Q2_K_S",
    24: "MOSTLY_IQ1_S", 25: "MOSTLY_IQ4_NL", 26: "MOSTLY_IQ3_S", 27: "MOSTLY_IQ2_S",
    28: "MOSTLY_IQ4_XS", 30: "MOSTLY_IQ3_XXS", 31: "MOSTLY_IQ1_M",
    32: "MOSTLY_BF16", 34: "MOSTLY_TQ1_0", 35: "MOSTLY_TQ2_0",
}


def read_str(f):
    (n,) = struct.unpack("<Q", f.read(8))
    return f.read(n).decode("utf-8", errors="replace")


def read_value(f, vtype):
    if vtype == 8:  # string
        return read_str(f)
    if vtype == 9:  # array
        (elem_type,) = struct.unpack("<I", f.read(4))
        (count,) = struct.unpack("<Q", f.read(8))
        return [read_value(f, elem_type) for _ in range(count)]
    fmt, size = {
        0: ("<B", 1), 1: ("<b", 1), 2: ("<H", 2), 3: ("<h", 2),
        4: ("<I", 4), 5: ("<i", 4), 6: ("<f", 4), 7: ("<?", 1),
        10: ("<Q", 8), 11: ("<q", 8), 12: ("<d", 8),
    }[vtype]
    return struct.unpack(fmt, f.read(size))[0]


def main(path):
    with open(path, "rb") as f:
        magic = f.read(4)
        assert magic == b"GGUF", f"not a GGUF file, magic={magic!r}"
        (version,) = struct.unpack("<I", f.read(4))
        (n_tensors,) = struct.unpack("<Q", f.read(8))
        (n_kv,) = struct.unpack("<Q", f.read(8))
        kv = {}
        for _ in range(n_kv):
            key = read_str(f)
            (vtype,) = struct.unpack("<I", f.read(4))
            val = read_value(f, vtype)
            kv[key] = val
        print(f"gguf_version={version}")
        print(f"n_tensors={n_tensors}")
        print(f"n_kv={n_kv}")
        for k in ("general.architecture", "general.name", "general.basename",
                   "general.size_label", "general.quantization_version",
                   "general.file_type", "qwen3.context_length",
                   "qwen3.attention.head_count", "tokenizer.chat_template"):
            if k in kv:
                v = kv[k]
                if k == "general.file_type":
                    print(f"{k}={v} ({FILE_TYPE_NAMES.get(v, 'UNKNOWN')})")
                elif k == "tokenizer.chat_template":
                    print(f"{k}=<present, {len(v)} chars, first 120: {v[:120]!r}>")
                else:
                    print(f"{k}={v!r}")


if __name__ == "__main__":
    main(sys.argv[1])
