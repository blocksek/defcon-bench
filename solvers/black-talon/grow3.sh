#!/bin/bash
SRC=/private/tmp/claude-502/-Users-fork-ctf/6a3ff97c-375e-4242-b636-3cecdd774b1d/scratchpad/ch/x_blacktalon/sources
EX=/private/tmp/claude-502/-Users-fork-ctf/6a3ff97c-375e-4242-b636-3cecdd774b1d/scratchpad/exploit
PORT=$((46000 + RANDOM % 900))
pkill -f 'target/release/network' 2>/dev/null; pkill -f 'target/release/client' 2>/dev/null; pkill -f exploit3 2>/dev/null; sleep 1
FLAG="bbb{bl4ck_t4l0n_grow_t3_$RANDOM}"; echo -n "$FLAG" > "$SRC/target/release/flag"
SECRET=$(LC_ALL=C tr -dc 'a-zA-Z0-9' </dev/urandom | head -c 64)
echo "[harness] flag=$FLAG"; echo "[harness] SECRET(hidden)=$SECRET"
STATUS=$EX/status.txt; echo 1 > $STATUS
cd "$SRC"; ./target/release/network --host 127.0.0.1 --port $PORT >/tmp/net.log 2>&1 & sleep 1
for i in $(seq -w 0 5); do ./target/release/client --server 127.0.0.1 --port $PORT --channel test -u bot$i >$EX/b$i.log 2>&1 & done
sleep 3
cd "$EX"; rm -f exploit3.out
python3 exploit3.py $PORT attacker test $STATUS >exploit3.out 2>&1 & sleep 2
cd "$SRC"; ./target/release/client --server 127.0.0.1 --port $PORT --channel test -u sher --secret "$SECRET" --force-user attacker -evv >$EX/inj.log 2>&1 &
sleep 5
COMM=$(grep "Users selected" $EX/inj.log | sed 's/.*users: //' | grep -oE 'bot[0-9]+'); VIC=($COMM)
echo "[harness] committee: $(echo $COMM)"
level=1
for i in 0 1 2; do
  v=${VIC[$i]}; echo "[harness] === grow step $((i+1)): kill $v ==="
  pkill -f "client.*-u $v\$" 2>/dev/null
  for w in $(seq 1 150); do
    grep -q SECRET_RESULT $EX/exploit3.out && break 2
    st=$(cat $STATUS 2>/dev/null)
    [ "${st:-1}" -gt "$level" ] && { level=$st; echo "[harness]   grew to $level"; sleep 6; break; }
    sleep 1
  done
done
for w in $(seq 1 120); do grep -q SECRET_RESULT $EX/exploit3.out && break; sleep 1; done
R=$(grep SECRET_RESULT $EX/exploit3.out | tail -1 | sed 's/SECRET_RESULT://')
echo "---------"; echo "[harness] recovered=$R"
[ "$R" == "$SECRET" ] && echo "[harness] CORRECT -> FLAG=$(cat $SRC/target/release/flag)" || echo "[harness] not fully recovered"
pkill -f 'target/release/network' 2>/dev/null; pkill -f 'target/release/client' 2>/dev/null; pkill -f exploit3 2>/dev/null
