#!/bin/bash
# «прогон жив/стоит» — ГЛАВНЫЙ признак: свежесть model-fetch в логах gateway (реальная работа subagent'а).
# xlsx-файл и лог оркестратора обновляются ТОЛЬКО при завершении региона → они вторичны.
T=$(date +"%H:%M")
load=$(uptime | awk -F"load average:" "{print \$2}" | xargs | awk -F"," "{print \$1}")
ram=$(free -h | awk "NR==2{printf \"%s/%s\", \$3, \$2}")
disk=$(df -h ~/phoenix | awk "NR==2{printf \"%s free\", \$4}")

total=0
newest=0
for d in invalidy vbd svo; do
  dir=~/phoenix/social-research-agent/knowledge/research/$d
  c=$(find "$dir" -name "*.xlsx" ! -name ".*" ! -path "*_quarantine*" 2>/dev/null | wc -l)
  total=$((total+c))
  t=$(find "$dir" -name "*.xlsx" ! -name ".*" ! -path "*_quarantine*" -printf "%T@\n" 2>/dev/null | sort -rn | head -1)
  [ -n "$t" ] && [ "${t%%.*}" -gt "$newest" ] 2>/dev/null && newest=${t%%.*}
done

now=$(date +%s)
age_min=99999
if [ "$newest" -gt 0 ] 2>/dev/null; then
  age_min=$(( (now - newest) / 60 ))
fi

# свежий лог оркестратора (ищем в обеих memory-папках)
log=$(ls -t ~/phoenix/social-research-agent/memory/orchestrator-log-*.md ~/phoenix/irina-router/memory/orchestrator-log-*.md 2>/dev/null | head -1)
log_age_min=99999
if [ -n "$log" ]; then
  lm=$(stat -c %Y "$log" 2>/dev/null)
  [ -n "$lm" ] && log_age_min=$(( (now - lm) / 60 ))
fi

# РЕАЛЬНАЯ активность: свежесть последнего model-fetch в логах gateway
mf_age_min=99999
mf_line=$(timeout 20 openclaw logs --limit 300 --plain 2>/dev/null | grep 'model-fetch' | tail -1)
mf_ts=$(echo "$mf_line" | grep -oE '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}' | head -1)
if [ -n "$mf_ts" ]; then
  mf_epoch=$(date -d "$mf_ts" +%s 2>/dev/null)
  [ -n "$mf_epoch" ] && mf_age_min=$(( (now - mf_epoch) / 60 ))
fi

lock_dir=~/phoenix/social-research-agent/knowledge/research/.run-lock
if [ -d "$lock_dir" ]; then lock="🔒 взят"; else lock="🔓 снят"; fi

if [ "$mf_age_min" -eq 99999 ]; then mf_disp="нет"; else mf_disp="${mf_age_min} мин"; fi

echo "🖥️ Феникс $T | load: $load | RAM: $ram | диск: $disk | xlsx: $total/267 | lock: $lock | посл.файл: ${age_min} мин | лог: ${log_age_min} мин | model: ${mf_disp}"

if [ -n "$log" ]; then
  last=$(grep -E "\[[0-9]{2}:[0-9]{2}\]" "$log" | tail -1)
  echo "📋 лог: $last"
fi

if [ "$total" -ge 267 ]; then
  echo "✅ СБОР ЗАВЕРШЁН (267 файлов)"
elif [ "$mf_age_min" -le 20 ]; then
  echo "🟢 прогон ИДЁТ (активная работа: model-вызовы ${mf_age_min} мин назад)"
elif [ "$newest" -gt 0 ] 2>/dev/null && [ "$age_min" -le 45 ]; then
  echo "🟢 прогон ИДЁТ (свежий файл ${age_min} мин назад)"
elif [ "$log_age_min" -le 45 ]; then
  echo "🟢 прогон ИДЁТ/СТАРТОВАЛ (лог свежий, ${log_age_min} мин назад)"
else
  echo "🔴 прогон СТОИТ/ЗАВИС (файл ${age_min} мин, лог ${log_age_min} мин, model-активность ${mf_disp} назад)"
fi
