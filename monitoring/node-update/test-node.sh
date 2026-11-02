#!/usr/bin/env bash
# Тесты до/после обновления Node.js на vm-f13581
set -u
PASS=0; FAIL=0; SKIP=0
ok(){ PASS=$((PASS+1)); echo "PASS  $1"; }
bad(){ FAIL=$((FAIL+1)); echo "FAIL  $1  (${2:-})"; }
chk(){ if [ "$1" = "0" ]; then ok "$2"; else bad "$2" "${3:-rc=$1}"; fi }

echo "=== ENV ==="
echo "date: $(date -Is)"
echo "node: $(node -v)"
echo "npm:  $(npm -v)"
echo "node path: $(readlink -f /usr/bin/node)"
echo "pkg: $(dpkg-query -W -f='${Version}' nodejs 2>/dev/null)"

V=$(node -v | sed 's/^v//'); MAJ=${V%%.*}; REST=${V#*.}; MIN=${REST%%.*}
if { [ "$MAJ" -eq 24 ] && [ "$MIN" -ge 16 ]; } || { [ "$MAJ" -ge 26 ] && [ "$MIN" -ge 1 ]; }; then
  ok "версия в диапазоне engines OpenClaw (>=24.16 <25 || >=26.1)"
else bad "версия в диапазоне engines OpenClaw" "получено $V"; fi

echo "=== RUNTIME ==="
timeout 10 node -e 'const c=require("crypto"); if(!c.randomUUID()) process.exit(1)' >/dev/null 2>&1; chk $? "crypto"
timeout 10 node -e 'require("zlib").gzipSync(Buffer.from("x")).length>0' >/dev/null 2>&1; chk $? "zlib"
timeout 10 node -e 'require("fs").readFileSync("/etc/hostname")' >/dev/null 2>&1; chk $? "fs"
timeout 15 node -e 'const {Worker}=require("worker_threads"); const w=new Worker("require(\"worker_threads\").parentPort.postMessage(1)",{eval:true}); w.on("message",()=>{w.terminate();process.exit(0)}); setTimeout(()=>process.exit(1),3000)' >/dev/null 2>&1; chk $? "worker_threads"
timeout 10 node -e 'try{const {DatabaseSync}=require("node:sqlite"); const db=new DatabaseSync(":memory:"); db.exec("create table t(a)"); process.exit(0)}catch(e){process.exit(2)}' >/dev/null 2>&1; chk $? "node:sqlite"
timeout 15 node -e 'fetch("https://nodejs.org/dist/latest-v24.x/",{signal:AbortSignal.timeout(8000)}).then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))' >/dev/null 2>&1; chk $? "fetch + TLS (nodejs.org)"
timeout 15 node -e 'fetch("https://www.asv.org.ru/api/v1/",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"search.getList",q:"АСВ",lang:"ru"}),signal:AbortSignal.timeout(8000)}).then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))' >/dev/null 2>&1; chk $? "fetch POST к API АСВ"

echo "=== NPM ==="
timeout 20 npm -v >/dev/null 2>&1; chk $? "npm запускается"
G=$(timeout 30 npm ls -g --depth=0 2>/dev/null | grep -c "openclaw"); [ "$G" -ge 1 ]; chk $? "глобальный пакет openclaw виден npm"
echo "global pkgs: $(timeout 30 npm ls -g --depth=0 2>/dev/null | grep -c '^[├└]──')"

echo "=== OPENCLAW CLI ==="
OUT=$(timeout 40 openclaw --version 2>&1); RC=$?; echo "  $OUT"
[ $RC -eq 0 ] && echo "$OUT" | grep -q "OpenClaw"; chk $? "openclaw --version"
echo "SKIP  openclaw --help (в этой среде CLI ждёт stdin; достаточно --version)"; SKIP=$((SKIP+1))

echo "=== GATEWAY (текущий процесс) ==="
CODE=$(curl -s -m 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:18789/health)
[ "$CODE" = "200" ]; chk $? "health endpoint 200 (получено: $CODE)"
systemctl --user is-active --quiet openclaw-gateway.service; chk $? "unit openclaw-gateway active"
echo "  MainPID: $(systemctl --user show openclaw-gateway.service -p MainPID --value)"

echo "=== ПРИКЛАДНЫЕ СКРИПТЫ ==="
cp /home/user1/.openclaw/workspace/monitoring/asv-agent/seen.json /tmp/asv-test-state.json
ASV=$(ASV_STATE=/tmp/asv-test-state.json timeout 60 python3 /home/user1/.openclaw/workspace/monitoring/asv-agent/check.py 2>&1)
echo "  asv check: $ASV"
[ "$ASV" = "CLEAN" ]; chk $? "asv-agent check.py → CLEAN"
timeout 10 python3 -c "import json;json.load(open('/tmp/asv-test-state.json'))" >/dev/null 2>&1; chk $? "seen.json валиден после прогона"

echo "=== DISK ==="
df -h / | tail -1

echo "=== ИТОГ: PASS=$PASS FAIL=$FAIL SKIP=$SKIP ==="
[ "$FAIL" -eq 0 ]
