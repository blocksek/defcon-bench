#!/bin/bash
SRC=/private/tmp/claude-502/-Users-fork-ctf/6a3ff97c-375e-4242-b636-3cecdd774b1d/scratchpad/ch/x_blacktalon/sources
EX=/private/tmp/claude-502/-Users-fork-ctf/6a3ff97c-375e-4242-b636-3cecdd774b1d/scratchpad/exploit
PORT=$((41000 + RANDOM % 1000))
pkill -f 'target/release/network' 2>/dev/null; pkill -f 'target/release/client' 2>/dev/null; pkill -f exploit.py 2>/dev/null; sleep 1

# ---- plant the flag (as the orchestrator would read ./flag) ----
FLAG="bbb{th3_bl4ck_t4l0n_r3sh4r3_duplic4t3_$RANDOM}"
echo -n "$FLAG" > "$SRC/target/release/flag"
echo "[harness] planted flag: $FLAG"

# ---- generate a RANDOM 64-char secret, exactly like orchestrator (unknown to exploit) ----
SECRET=$(LC_ALL=C tr -dc 'a-zA-Z0-9' </dev/urandom | head -c 64)
echo "[harness] planted RANDOM secret (hidden from exploit): $SECRET"

cd "$SRC"
./target/release/network --host 127.0.0.1 --port $PORT >/tmp/net.log 2>&1 &
sleep 1
for i in $(seq -w 0 4); do
  ./target/release/client --server 127.0.0.1 --port $PORT --channel test -u bot$i >$EX/bot$i.log 2>&1 &
done
sleep 2
cd "$EX"
python3 exploit.py $PORT attacker test >exploit.out 2>&1 &
sleep 2
cd "$SRC"
./target/release/client --server 127.0.0.1 --port $PORT --channel test -u sher --secret "$SECRET" --force-user attacker -evv >$EX/inj.log 2>&1 &
sleep 5
COMMITTEE=$(grep "Users selected" $EX/inj.log | sed 's/.*users: //')
echo "[harness] committee: $COMMITTEE"
# pick a committee bot (not attacker) to kill -> trigger reshares
VICTIM=$(echo "$COMMITTEE" | grep -oE 'bot[0-9]+' | head -1)
echo "[harness] killing committee member $VICTIM to trigger reshare churn"
pkill -f "client.*-u $VICTIM" ; true
# wait for exploit to recover
for t in $(seq 1 200); do
  if grep -q SECRET_RESULT $EX/exploit.out; then break; fi
  sleep 1
done
RECOVERED=$(grep SECRET_RESULT $EX/exploit.out | tail -1 | sed 's/SECRET_RESULT://')
echo "[harness] exploit recovered secret: $RECOVERED"
echo "----------------------------------------------------------------"
if [ "$RECOVERED" == "$SECRET" ]; then
  echo "[harness] GUESS CORRECT -> orchestrator would reveal the flag:"
  echo "[harness] FLAG = $(cat $SRC/target/release/flag)"
else
  echo "[harness] MISMATCH: recovered != secret"
fi
pkill -f 'target/release/network' 2>/dev/null; pkill -f 'target/release/client' 2>/dev/null; pkill -f exploit.py 2>/dev/null
