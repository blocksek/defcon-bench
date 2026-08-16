#!/usr/bin/env python3
"""Reference solver for omgzip.

omgzip is a custom compressor: a run-length pre-pass followed by an adaptive
*splay-tree* binary coder (the `Deflater`). To decompress we:

  1. Rebuild the identical initial coding tree by instantiating the compressor's
     own `Deflater` (so we inherit its exact node layout and the `_magic` splay).
  2. Walk the bit stream from the root: bit 0 -> successful_firstborn (left),
     bit 1 -> conflicted_stepchild (right). On reaching a leaf, emit its symbol
     and splay it with `_magic`, exactly mirroring the encoder.
  3. Stop at the `None` end-of-stream symbol, then invert the run-length pass.

Run: python3 solve.py omg.zip
"""
import sys
import zipfile
import tarfile
import io
import importlib.util
from importlib.machinery import SourceFileLoader


def load_omgzip(path):
    loader = SourceFileLoader("omgzip_mod", path)
    spec = importlib.util.spec_from_loader("omgzip_mod", loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["omgzip_mod"] = mod  # dataclass forward refs need this
    loader.exec_module(mod)
    return mod


def climb_to_root(node):
    while node.overbearing_parent is not None:
        node = node.overbearing_parent
    return node


def is_leaf(node):
    return node.successful_firstborn is None and node.conflicted_stepchild is None


def bits_msb_first(data: bytes):
    for byte in data:
        for i in range(7, -1, -1):
            yield (byte >> i) & 1


def omg_decompress(mod, blob: bytes) -> bytes:
    assert blob[:6] == bytes([79, 77, 71, 90, 73, 80]), "bad OMGZIP magic"
    payload = blob[6:]

    d = mod.Deflater()
    # Map each terminal node identity -> its symbol (0..255 or None).
    node2sym = {id(v): k for k, v in d.dictionary.items()}
    root = climb_to_root(d.dictionary[1])

    encoded = bytearray()
    node = root
    for bit in bits_msb_first(payload):
        node = node.successful_firstborn if bit == 0 else node.conflicted_stepchild
        if node is None:
            raise ValueError("walked off the tree; bit misalignment")
        if is_leaf(node):
            sym = node2sym.get(id(node))
            if sym is None:
                break  # end-of-stream marker
            encoded.append(sym)
            mod.Deflater._magic(d, node)  # splay, mutating the shared tree
            root = climb_to_root(node)
            node = root

    return rle_decode(bytes(encoded))


def rle_decode(encoded: bytes) -> bytes:
    """Invert omgzip's run-length pre-pass (see compress() in omgzip)."""
    out = bytearray()
    i = 0
    n = len(encoded)
    while i < n:
        b = encoded[i]
        if b != 255:
            out.append(b)
            i += 1
            continue
        # 255 marker
        if i + 1 < n and encoded[i + 1] == 255:
            out.append(255)  # escaped literal 0xff
            i += 2
        else:
            count = encoded[i + 1]
            value = encoded[i + 2]
            run = count + (3 if value != 255 else 2)
            out.extend([value] * run)
            i += 3
    return bytes(out)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "omg.zip"
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        comp_name = next(n for n in names if n.endswith(".omgzip"))
        script_name = next(n for n in names if n == "omgzip" or n.endswith("/omgzip"))
        comp = z.read(comp_name)
        z.extract(script_name, path=".")

    mod = load_omgzip(script_name)
    tar_bytes = omg_decompress(mod, comp)

    with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tf:
        for member in tf.getmembers():
            if member.isfile():
                data = tf.extractfile(member).read()
                text = data.decode("utf-8", "replace").strip()
                if "flag{" in text or member.name.endswith("flag"):
                    print(text)


if __name__ == "__main__":
    main()
