#!/bin/bash
# BRD Pipeline Logger
# Usage: ./brd-log.sh <event> <data>
# Events: start, question_sent, answer_received, controller_status, error, complete

LOG_DIR="/home/user1/.openclaw/workspace/memory/brd-logs"
mkdir -p "$LOG_DIR"

EVENT="${1:-unknown}"
DATA="${2:-}"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S %z')
LOG_FILE="${LOG_DIR}/brd-$(date '+%Y-%m').log"

case "$EVENT" in
  start)
    echo "[${TIMESTAMP}] [START] Сессия BRD запущена. Пользователь: Кирилл (346428630). UUID: ${DATA:-auto-generated}" >> "$LOG_FILE"
    ;;
  question_sent)
    echo "[${TIMESTAMP}] [QUESTION] Вопрос отправлен пользователю. Questioner -> Controller -> Лунт -> Telegram. Сессия: ${DATA}" >> "$LOG_FILE"
    ;;
  answer_received)
    echo "[${TIMESTAMP}] [ANSWER] Ответ получен от пользователя. Telegram -> Лунт -> Controller -> Questioner. Сессия: ${DATA}" >> "$LOG_FILE"
    ;;
  controller_status)
    echo "[${TIMESTAMP}] [STATUS] Controller: ${DATA}" >> "$LOG_FILE"
    ;;
  proxy_question)
    echo "[${TIMESTAMP}] [PROXY->USER] Прокси: <<< ВОПРОС >>> [${DATA}]" >> "$LOG_FILE"
    ;;
  proxy_answer)
    echo "[${TIMESTAMP}] [PROXY->CTRL] Прокси: ответ передан Controller >>> [${DATA}]" >> "$LOG_FILE"
    ;;
  error)
    echo "[${TIMESTAMP}] [ERROR] ОШИБКА: ${DATA}" >> "$LOG_FILE"
    ;;
  complete)
    echo "[${TIMESTAMP}] [COMPLETE] Сессия BRD завершена. Результат: ${DATA}" >> "$LOG_FILE"
    ;;
  *)
    echo "[${TIMESTAMP}] [${EVENT}] ${DATA}" >> "$LOG_FILE"
    ;;
esac
echo "LOGGED: ${EVENT}" > /dev/null
