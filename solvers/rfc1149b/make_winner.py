import sys, struct
init=bytes.fromhex(sys.argv[1])
lo=struct.unpack("<Q",init[:8])[0]; hi=struct.unpack("<Q",init[8:])[0]
print(f'''(module
  (import "env" "gotcha" (func $gotcha (param i32) (result i32)))
  (memory (export "memory") 2)
  (global (export "scratch_ptr") i32 (i32.const 0))
  (global (export "scratch_cap") i32 (i32.const 65536))
  (func (export "mallory_run")
    (i64.store (i32.const 0x10000) (i64.const 0x{lo:016x}))
    (i64.store (i32.const 0x10008) (i64.const 0x{hi:016x}))
    (drop (call $gotcha (i32.const 0x10000)))))''')
