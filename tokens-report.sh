#!/bin/bash
# tokens-report.sh — Отчёт: потрачено токенов, SVG-диаграммы по моделям и пользователям
set -euo pipefail

HTML_FILE="/tmp/tokens.html"
DATA_FILE="/tmp/tokens-data.json"

# Job ID → Пользователь
declare -A JOB_USER
JOB_USER=(
  ["94228ca5-290b-47c2-906e-be658e0ff49b"]="Катя"
  ["b4f0e3ed-affb-4449-ab73-c547f0876079"]="Лена"
  ["e001daa1-ec86-4acf-8830-a5204df21a03"]="Данил"
  ["ef30162f-05de-4521-b91f-0044baf34a64"]="Данил"
  ["04ed00c5-d59c-4ae2-afbb-03720a93dec2"]="Лена"
  ["6f3b5037-c174-424d-94a1-dc5413031bb7"]="Бэкапы"
  ["a7ec1604-6bd8-428d-ba09-dbc894956f5b"]="Бэкапы"
  ["0d49cb67-c918-4123-9441-4ed146282b10"]="Ирина"
  ["8df8451b-1cf7-4999-ba2b-353fcd7e65ae"]="Роза"
  ["dd880535-864a-4720-bc61-edde8476478c"]="Система"
)

JOBS=(
  "94228ca5-290b-47c2-906e-be658e0ff49b"
  "b4f0e3ed-affb-4449-ab73-c547f0876079"
  "e001daa1-ec86-4acf-8830-a5204df21a03"
  "ef30162f-05de-4521-b91f-0044baf34a64"
  "04ed00c5-d59c-4ae2-afbb-03720a93dec2"
  "6f3b5037-c174-424d-94a1-dc5413031bb7"
  "a7ec1604-6bd8-428d-ba09-dbc894956f5b"
  "0d49cb67-c918-4123-9441-4ed146282b10"
  "8df8451b-1cf7-4999-ba2b-353fcd7e65ae"
  "dd880535-864a-4720-bc61-edde8476478c"
)

SSH_KEY="$HOME/…eweb"
SSH_HOST="cq832843@87.249.38.179"
REMOTE_DIR="~/public_html"

NOW_MS=$(date +%s%3N)
CUTOFF_MS=$((NOW_MS - 86400000))
TODAY=$(TZ=Europe/Moscow date +%Y-%m-%d)

# Скачать tokens-data.json
echo "📥 Скачиваю tokens-data.json..."
ssh -i "$SSH_KEY" "$SSH_HOST" "cat $REMOTE_DIR/tokens-data.json 2>/dev/null" > "$DATA_FILE" 2>/dev/null || true
if [ ! -s "$DATA_FILE" ] || ! jq empty "$DATA_FILE" 2>/dev/null; then
  echo '[]' > "$DATA_FILE"
fi

# Собираем runs за 24ч
echo "📊 Собираю..."
DEEP_IN=0; DEEP_OUT=0; DEEP_TOTAL=0
GLM_IN=0; GLM_OUT=0; GLM_TOTAL=0

declare -A USER_TOKENS

for JOB_ID in "${JOBS[@]}"; do
  RUNS=$(openclaw cron runs --id "$JOB_ID" --limit 50 2>/dev/null || echo '{"entries":[]}')

  D=$(echo "$RUNS" | jq --argjson c "$CUTOFF_MS" '
    [.entries[] | select(.runAtMs > $c) | select(.model == "deepseek-chat")]
    | if length==0 then {i:0,o:0,t:0} else {i:(map(.usage.input_tokens//0)|add),o:(map(.usage.output_tokens//0)|add),t:(map(.usage.total_tokens//0)|add)} end
  ')
  DEEP_IN=$((DEEP_IN + $(echo "$D" | jq '.i')))
  DEEP_OUT=$((DEEP_OUT + $(echo "$D" | jq '.o')))
  DEEP_TOTAL=$((DEEP_TOTAL + $(echo "$D" | jq '.t')))

  G=$(echo "$RUNS" | jq --argjson c "$CUTOFF_MS" '
    [.entries[] | select(.runAtMs > $c) | select(.model != "deepseek-chat")]
    | if length==0 then {i:0,o:0,t:0} else {i:(map(.usage.input_tokens//0)|add),o:(map(.usage.output_tokens//0)|add),t:(map(.usage.total_tokens//0)|add)} end
  ')
  GLM_IN=$((GLM_IN + $(echo "$G" | jq '.i')))
  GLM_OUT=$((GLM_OUT + $(echo "$G" | jq '.o')))
  GLM_TOTAL=$((GLM_TOTAL + $(echo "$G" | jq '.t')))

  USER="${JOB_USER[$JOB_ID]:-Прочее}"
  T=$(echo "$RUNS" | jq --argjson c "$CUTOFF_MS" '
    [.entries[] | select(.runAtMs > $c)] | map(.usage.total_tokens//0) | add // 0
  ')
  EXISTING="${USER_TOKENS[$USER]:-0}"
  USER_TOKENS[$USER]=$((EXISTING + T))
done

ALL_TOTAL=$((DEEP_TOTAL + GLM_TOTAL))
DEEP_COST=$(echo "scale=2; ($DEEP_IN/1000000)*0.27 + ($DEEP_OUT/1000000)*1.10" | bc)
GLM_COST=$(echo "scale=2; ($GLM_IN/1000000)*1.40 + ($GLM_OUT/1000000)*4.40" | bc)
ALL_COST=$(echo "scale=2; $DEEP_COST + $GLM_COST" | bc)

[ "$DEEP_COST" = "0" ] && DEEP_COST="0.00"
[ "$GLM_COST" = "0" ] && GLM_COST="0.00"
[ "$ALL_COST" = "0" ] && ALL_COST="0.00"
DEEP_COST=$(printf "%.2f" "$DEEP_COST")
GLM_COST=$(printf "%.2f" "$GLM_COST")
ALL_COST=$(printf "%.2f" "$ALL_COST")

echo "  DeepSeek: $(printf "%'d" "$DEEP_TOTAL") токенов, \$$DEEP_COST"
echo "  GLM:      $(printf "%'d" "$GLM_TOTAL") токенов, \$$GLM_COST"

# Сохраняем день в tokens-data.json
USER_JSON_PARTS=""
for U in "${!USER_TOKENS[@]}"; do
  T="${USER_TOKENS[$U]}"
  [ -n "$USER_JSON_PARTS" ] && USER_JSON_PARTS="${USER_JSON_PARTS},"
  USER_JSON_PARTS="${USER_JSON_PARTS}\"$U\":$T"
done
USER_JSON="{${USER_JSON_PARTS}}"

DAY_JSON=$(jq -n --arg date "$TODAY" --argjson di "$DEEP_IN" --argjson do "$DEEP_OUT" --argjson dt "$DEEP_TOTAL" --argjson dc "$DEEP_COST" --argjson gi "$GLM_IN" --argjson go "$GLM_OUT" --argjson gt "$GLM_TOTAL" --argjson gc "$GLM_COST" --argjson at "$ALL_TOTAL" --argjson ac "$ALL_COST" --argjson uj "$USER_JSON" '
  {date:$date, deepseek:{input:$di,output:$do,total:$dt,cost:$dc}, glm:{input:$gi,output:$go,total:$gt,cost:$gc}, all:{total:$at,cost:$ac}, users:$uj}
')

UPDATED=$(jq --argjson day "$DAY_JSON" --arg today "$TODAY" '
  map(select(.date != $today)) + [$day] | .[-7:]
' "$DATA_FILE")
echo "$UPDATED" > "$DATA_FILE"

DAYS=$(echo "$UPDATED" | jq 'length')
S_DEEP=$(echo "$UPDATED" | jq '[.[].deepseek.total] | add')
S_GLM=$(echo "$UPDATED" | jq '[.[].glm.total] | add')
S_ALL=$(echo "$UPDATED" | jq '[.[].all.total] | add')
S_DEEP_COST=$(echo "$UPDATED" | jq '[.[].deepseek.cost] | add * 100 | round / 100')
S_GLM_COST=$(echo "$UPDATED" | jq '[.[].glm.cost] | add * 100 | round / 100')
S_ALL_COST=$(echo "$UPDATED" | jq '[.[].all.cost] | add * 100 | round / 100')

# === SVG helper ===
CX=100; CY=100; R=90

make_svg_sector() {
  local ACCUM_DEG="$1" PCT="$2" COLOR="$3" LABEL1="$4" LABEL2="$5" MIN_PCT="$6"
  local DEG END_DEG START_RAD END_RAD X1 Y1 X2 Y2 LARGE OUT=""

  DEG=$(echo "scale=4; $PCT * 360 / 100" | bc)
  END_DEG=$(echo "scale=4; $ACCUM_DEG + $DEG" | bc)

  LARGE=$(echo "if ($DEG > 180) 1 else 0" | bc)

  # Координаты через awk (bc нет sin/cos без -l)
  eval $(awk -v acc="$ACCUM_DEG" -v deg="$DEG" -v cx="$CX" -v cy="$CY" -v r="$R" 'BEGIN{
    pi=3.14159265358979; d2r=pi/180
    sr=acc*d2r-pi/2; er=(acc+deg)*d2r-pi/2
    if(acc+deg>=360) er=359.99*d2r-pi/2
    printf "X1=%.2f Y1=%.2f X2=%.2f Y2=%.2f", cx+r*cos(sr), cy+r*sin(sr), cx+r*cos(er), cy+r*sin(er)
  }')

  if [ "$(echo "$DEG >= 360" | bc)" -eq 1 ]; then
    OUT="<circle cx=\"$CX\" cy=\"$CY\" r=\"$R\" fill=\"$COLOR\"/>"
  elif [ "$(echo "$DEG > 0.5" | bc)" -eq 1 ]; then
    OUT="<path d=\"M$CX,$CY L$X1,$Y1 A$R,$R 0 $LARGE,1 $X2,$Y2 Z\" fill=\"$COLOR\"/>"
  fi

  if [ "$(echo "$PCT > $MIN_PCT" | bc)" -eq 1 ] && [ -n "$LABEL1" ]; then
    local LR LX LY LY2
    eval $(awk -v acc="$ACCUM_DEG" -v deg="$DEG" -v cx="$CX" -v cy="$CY" -v r="$R" 'BEGIN{
      pi=3.14159265358979; d2r=pi/2
      mr=(acc+deg/2)*d2r/90-d2r; lr=r*0.6
      printf "LX=%.2f LY=%.2f LY2=%.2f", cx+lr*cos(mr), cy+lr*sin(mr), cy+lr*sin(mr)+14
    }')
    OUT="${OUT}<text x=\"$LX\" y=\"$LY\" text-anchor=\"middle\" dominant-baseline=\"central\" fill=\"#0d1117\" font-size=\"11\" font-weight=\"700\">$LABEL1</text>"
    [ -n "$LABEL2" ] && OUT="${OUT}<text x=\"$LX\" y=\"$LY2\" text-anchor=\"middle\" dominant-baseline=\"central\" fill=\"#0d1117\" font-size=\"10\">$LABEL2</text>"
  fi

  echo "$OUT"
}

# === SVG-диаграмма по моделям ===
MODEL_SVG=""
MODEL_LEGEND_HTML=""
MODEL_COLORS=("#7ee787" "#58a6ff")
MODEL_DATA=("$DEEP_TOTAL" "$GLM_TOTAL")
MODEL_NAMES=("DeepSeek" "GLM-5.1")
ACCUM=0

for I in 0 1; do
  T="${MODEL_DATA[$I]}"
  NAME="${MODEL_NAMES[$I]}"
  COLOR="${MODEL_COLORS[$I]}"
  if [ "$ALL_TOTAL" -gt 0 ]; then
    PCT=$(echo "scale=4; $T * 100 / $ALL_TOTAL" | bc)
  else
    PCT="0"
  fi
  PCT_FMT=$(printf "%.1f" "$PCT")
  T_FMT=$(printf "%'d" "$T")

  SECTOR=$(make_svg_sector "$ACCUM" "$PCT" "$COLOR" "$NAME" "$PCT_FMT%" "2")
  MODEL_SVG="${MODEL_SVG}${SECTOR}"

  MODEL_LEGEND_HTML="${MODEL_LEGEND_HTML}<div class=\"legend-item\"><span class=\"legend-dot\" style=\"background:${COLOR}\"></span><span class=\"legend-label\">${NAME}</span><span class=\"legend-val\">${T_FMT} <span class=\"legend-pct\">(${PCT_FMT}%)</span></span></div>"
  ACCUM=$(echo "scale=4; $ACCUM + $PCT * 360 / 100" | bc)
done

MODEL_SVG_FULL="<svg viewBox=\"0 0 200 200\" width=\"200\" height=\"200\">${MODEL_SVG}</svg>"

# === SVG-диаграмма по пользователям ===
USER_SVG=""
USER_LEGEND_HTML=""
USER_COLORS=("#58a6ff" "#7ee787" "#ff7b72" "#d2a8ff" "#ffa657" "#79c0ff" "#f0883e" "#a5d6ff")
ACCUM=0
COLOR_IDX=0

SORT_FILE=$(mktemp)
for U in "${!USER_TOKENS[@]}"; do
  echo "${USER_TOKENS[$U]} $U"
done | sort -rn > "$SORT_FILE"

while IFS=' ' read -r T U; do
  COLOR="${USER_COLORS[$COLOR_IDX]}"
  if [ "$ALL_TOTAL" -gt 0 ]; then
    PCT=$(echo "scale=4; $T * 100 / $ALL_TOTAL" | bc)
  else
    PCT="0"
  fi
  PCT_FMT=$(printf "%.1f" "$PCT")
  T_FMT=$(printf "%'d" "$T")

  SECTOR=$(make_svg_sector "$ACCUM" "$PCT" "$COLOR" "$U" "$PCT_FMT%" "5")
  USER_SVG="${USER_SVG}${SECTOR}"

  USER_LEGEND_HTML="${USER_LEGEND_HTML}<div class=\"legend-item\"><span class=\"legend-dot\" style=\"background:${COLOR}\"></span><span class=\"legend-label\">${U}</span><span class=\"legend-val\">${T_FMT} <span class=\"legend-pct\">(${PCT_FMT}%)</span></span></div>"
  ACCUM=$(echo "scale=4; $ACCUM + $PCT * 360 / 100" | bc)
  COLOR_IDX=$((COLOR_IDX + 1))
done < "$SORT_FILE"
rm -f "$SORT_FILE"

USER_SVG_FULL="<svg viewBox=\"0 0 200 200\" width=\"200\" height=\"200\">${USER_SVG}</svg>"

DATETIME=$(TZ=Europe/Moscow date '+%d.%m.%Y %H:%M')

# Генерация HTML
cat > "$HTML_FILE" << HTMLEOF
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>📊 Токены — nasledstvo2026.github.io/nasledstvo</title>
<link rel="stylesheet" href="theme.css">
<style>
.block{margin-bottom:32px}
.block h2{margin-bottom:8px}
.row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #21262d;font-size:15px}
.row:last-child{border:none}
.label{color:#8b949e}
.val{font-weight:700}
.money{color:#7ee787}
.sep{border-top:2px solid #58a6ff;margin:16px 0}
.pie-section{margin:32px 0}
.pie-wrapper{display:flex;align-items:center;gap:32px;flex-wrap:wrap;justify-content:center}
.legend{display:flex;flex-direction:column;gap:10px;min-width:200px}
.legend-item{display:flex;align-items:center;gap:10px}
.legend-dot{width:14px;height:14px;border-radius:3px;flex-shrink:0}
.legend-label{min-width:80px;color:#c9d1d9}
.legend-val{font-weight:700;font-size:14px}
.legend-pct{color:#8b949e;font-weight:400;font-size:13px}
</style>
</head>
<body>
<div class="container">
<a href="index.html" class="back">← Главная</a>
<div class="hero"><h1 class="title">📊 Токены</h1><p class="meta">Потрачено за сегодня</p></div>

<div class="pie-section">
<h2 class="title">По моделям</h2>
<div class="pie-wrapper">
${MODEL_SVG_FULL}
<div class="legend">
${MODEL_LEGEND_HTML}
</div>
</div>
</div>

<div class="sep"></div>

<div class="pie-section">
<h2 class="title">По пользователям</h2>
<div class="pie-wrapper">
${USER_SVG_FULL}
<div class="legend">
${USER_LEGEND_HTML}
</div>
</div>
</div>

<div class="sep"></div>

<div class="block">
<div class="row"><span class="label">DeepSeek</span><span class="val">$(printf "%'d" "$DEEP_TOTAL") · <span class="money">\$$DEEP_COST</span></span></div>
<div class="row"><span class="label">GLM-5.1</span><span class="val">$(printf "%'d" "$GLM_TOTAL") · <span class="money">\$$GLM_COST</span></span></div>
<div class="row"><span class="label">Итого</span><span class="val">$(printf "%'d" "$ALL_TOTAL") · <span class="money">\$$ALL_COST</span></span></div>
</div>

<div class="sep"></div>

<div class="block">
<div class="row"><span class="label">Итого</span><span class="val">$(printf "%'d" "$ALL_TOTAL") токенов</span></div>
<div class="row"><span class="label">Итого</span><span class="val money">\$$ALL_COST</span></div>
</div>

<div class="sep"></div>

<div class="block">
<h2 class="title">За ${DAYS} дней</h2>
<div class="row"><span class="label">DeepSeek</span><span class="val">$(printf "%'d" "$S_DEEP") · <span class="money">\$$S_DEEP_COST</span></span></div>
<div class="row"><span class="label">GLM-5.1</span><span class="val">$(printf "%'d" "$S_GLM") · <span class="money">\$$S_GLM_COST</span></span></div>
<div class="row"><span class="label">Итого</span><span class="val">$(printf "%'d" "$S_ALL") · <span class="money">\$$S_ALL_COST</span></span></div>
</div>

<div class="footer"><p>☽ Лунт · ${DATETIME}</p></div>
</div>
</body>
</html>
HTMLEOF

echo "✅ HTML: $(wc -c < "$HTML_FILE") байт"

if [[ "${1:-}" == "--upload" ]]; then
  echo "📤 Загружаю..."
  MAX_RETRIES=3
  RETRY_DELAY=15
  for ATTEMPT in $(seq 1 $MAX_RETRIES); do
    if scp -i "$SSH_KEY" -o ConnectTimeout=10 "$HTML_FILE" "$DATA_FILE" "$SSH_HOST:$REMOTE_DIR/" 2>/dev/null; then
      echo "✅ Готово (попытка $ATTEMPT)"
      exit 0
    fi
    echo "⚠️ Попытка $ATTEMPT/$MAX_RETRIES не удалась"
    if [ "$ATTEMPT" -lt "$MAX_RETRIES" ]; then
      echo "   Жду ${RETRY_DELAY}с..."
      sleep $RETRY_DELAY
    fi
  done
  echo "❌ Не удалось загрузить после $MAX_RETRIES попыток"
  exit 1
fi
