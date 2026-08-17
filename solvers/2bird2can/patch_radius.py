#!/usr/bin/env python3
# Shorten the flag spawn distance for the local end-to-end capture DEMO (see CAPTURE_TRANSCRIPT.txt).
# Patches two float32 constants in the server's GameAssembly.so:
#   radius = clamp(u16/65535,1)*RANGE + BASE   (world dist ~= radius * ~64)
#   BASE 1900.0 @ 0x8883C8 -> 3.0 ; RANGE 200.0 @ 0x888450 -> 1.0  => chest ~200-270 units from spawn
import struct, sys
p = sys.argv[1] if len(sys.argv)>1 else "GameAssembly.so"
d = bytearray(open(p,"rb").read())
struct.pack_into("<f", d, 0x8883C8, 3.0)
struct.pack_into("<f", d, 0x888450, 1.0)
open(p,"wb").write(d)
print("patched BASE@0x8883C8->3.0 RANGE@0x888450->1.0")
