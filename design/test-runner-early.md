# План тестирования Router classifier в GAIA — до/после

## Цель
Сравнить точность multi-agent с классическим Router vs Router с классификацией K/T/H.

## Метод

1. Взять **20 GAIA Level 1 задач** (из validation set)
2. Прогнать на **текущем** коде (Router → Collector → Solver → Verifier) — записать результат
3. Прогнать на новой версии (Router определяет K → Solver сразу, T/H → Collector)
4. Сравнить accuracy

## Файлы
- `gaia-multiagent.py` — текущая версия (backup есть)
- `gaia-multiagent-v2.py` — новая версия с классификатором
- Запуск: `cd scripts/gaia && python3 gaia-multiagent-v2.py --tasks 20 --level 1`

## Критерий успеха
- Точность **выше 40%** (сейчас 11.3%)
- Ни одна T-задача не ушла в Solver напрямую
