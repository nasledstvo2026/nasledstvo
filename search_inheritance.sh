#!/bin/bash
# SearXNG systematic search for inheritance complaint data

BASE="http://localhost:8888/search"
OUTDIR="/home/user1/.openclaw/workspace/search_results"
mkdir -p "$OUTDIR"

QUERIES=(
  "site:banki.ru наследство Сбербанк жалоба"
  "site:banki.ru наследство ВТБ жалоба"
  "site:banki.ru наследство Т-Банк жалоба"
  "site:banki.ru наследство ПСБ жалоба"
  "site:banki.ru наследство отказ выплат"
  "site:otzovik.com наследство банк вклад"
  "site:pikabu.ru наследство банк вклад"
  "site:sravni.ru наследство вклад отказ"
  "site:vc.ru наследство банк вклад"
  "\"вклад умершего\" жалоба"
  "\"свидетельство о праве на наследство\" отказ банк"
  "наследство вклад умершего банк отказ выплатить"
  "жалоба наследство вклад Сбербанк не выплачивает"
  "наследство вклад отказали выплатить"
)

# Function to URL-encode a string
urlencode() {
    local string="$1"
    local strlen=${#string}
    local encoded=""
    local pos c o

    for (( pos=0 ; pos<strlen ; pos++ )); do
        c=${string:$pos:1}
        case "$c" in
            [-_.~a-zA-Z0-9] ) o="${c}" ;;
            * )               printf -v o '%%%02x' "'$c"
        esac
        encoded+="${o}"
    done
    echo "${encoded}"
}

# Search 2025 (full year)
mkdir -p "$OUTDIR/2025"
for q in "${QUERIES[@]}"; do
    safe_name=$(echo "$q" | tr -c 'a-zA-Z0-9_' '_' | head -c 60)
    encoded=$(urlencode "$q")
    echo "Searching 2025: $q"
    curl -s "$BASE?q=${encoded}+2025&format=json&time_range=year&pageno=1" 2>/dev/null > "$OUTDIR/2025/${safe_name}_p1.json"
    sleep 0.5
    curl -s "$BASE?q=${encoded}+2025&format=json&time_range=year&pageno=2" 2>/dev/null > "$OUTDIR/2025/${safe_name}_p2.json"
    sleep 0.5
done

# Search 2026 (Jan-Jun)
mkdir -p "$OUTDIR/2026"
for q in "${QUERIES[@]}"; do
    safe_name=$(echo "$q" | tr -c 'a-zA-Z0-9_' '_' | head -c 60)
    encoded=$(urlencode "$q")
    echo "Searching 2026: $q"
    curl -s "$BASE?q=${encoded}+2026&format=json&time_range=year&pageno=1" 2>/dev/null > "$OUTDIR/2026/${safe_name}_p1.json"
    sleep 0.5
done

echo "Done collecting data"
