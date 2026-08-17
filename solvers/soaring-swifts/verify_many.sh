#!/bin/bash
# In amd64 container: generate N random checkers and confirm solver recovers each.
cd /build
N=${1:-5}
pass=0
for i in $(seq 1 $N); do
  SECRET=$(python3 -c "import random,string;print(''.join(random.choice(string.ascii_lowercase) for _ in range(32)))")
  SEED=$(python3 -c "import random;print(random.randint(0,2**31-1))")
  printf '%s\n%s\n' "$SECRET" "$SEED" | ./compiler > r.asm 2>/dev/null
  nasm -f elf64 -o r.o r.asm && ld -o r.checker r.o 2>/dev/null
  # sanity: checker accepts secret
  printf '%s' "$SECRET" | ./r.checker; ec=$?
  GUESS=$(python3 /chal/solver.py /build/r.checker 2>/dev/null)
  # verify guess via the checker itself
  printf '%s' "$GUESS" | ./r.checker; gec=$?
  if [ "$GUESS" == "$SECRET" ] && [ "$gec" == "0" ]; then
    echo "[$i] OK  secret=$SECRET"
    pass=$((pass+1))
  else
    echo "[$i] FAIL secret=$SECRET guess=$GUESS checker_on_secret=$ec checker_on_guess=$gec"
  fi
done
echo "PASSED $pass / $N"
