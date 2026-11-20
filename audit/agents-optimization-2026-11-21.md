# Аудит ИИ-агентов OpenClaw — 2026-11-21

Источники: ~/.openclaw/openclaw.json, automations list/get (33 jobs), ls каталогов, живой вызов web_search, bootstrap-контекст сессии.

## Инвентарь (11 агентов, 4 binding)

| Агент | Модель | Прямой вход | Sandbox | tools allow/deny |
|---|---|---|---|---|
| main | flash | Кирилл, Аркадий (534779071), Алиса (5216111644), 254785028 | нет | наследует profile=coding |
| katya-agent | flash | 932052526 | нет | нет |
| maria | pro | 1431548892 | docker, scope=agent | да |
| lesya | pro | 496061091 | docker, scope=agent | да |
| kirill-family-advocate | flash | триггер из main | нет | нет |
| advocate-verifier | flash | только sessions_send | нет | нет |
| ba-controller/questioner/compiler/verifier | flash | только sessions_send | нет | нет |
| barbershop-verifier | flash | только sessions_send | нет | нет |

allowFrom: 7 uid, dmPolicy=allowlist. Без binding в main попадают 534779071, 5216111644, 254785028.

## Находки

### P0
1. Три внешних человека работают в main — агенте владельца. tools.sessions.visibility="all", memory_search доступен: технически их сессии могут читать память и переписки владельца/других людей. Изоляция есть только у maria/lesya.
2. 9 из 11 агентов без sandbox и без allow/deny → полный доступ к ФС пользователя user1 и полный профиль инструментов (включая exec, browser, image/video). В т.ч. katya-agent.
3. web_search заявлен включённым (tools.web.search.enabled=true, плагины duckduckgo+searxng), но живой вызов: "web_search is disabled or no provider is available". Джобы, полагающиеся на поиск, деградируют молча.

### P1
4. Heartbeat каждые 30 мин = 48 запусков/сутки, все skipped: "empty-heartbeat-file" — файла /workspace/HEARTBEAT.md нет. Ноль пользы, шум в статусах. Если включить — полный промпт 48×/день.
5. AGENTS.md 20 656 символов; bootstrap обрезает его (warning в контексте). Часть правил не доезжает до модели. MEMORY.md 14 751 символ грузится в main-сессиях, включая сессии внешних людей.
6. 20 навыков продублированы в workspace/skills (31) и workshop-skills (29): два источника правды, расходятся незаметно.
7. Конвейеры на фиксированных задержках без проверки предыдущего шага: lena 02:00→02:10→02:20, жалобы 07:45→07:55→08:00. При задержке шага следующий читает stale/пусто.
8. lena-сбор: fallbacks=["deepseek-v4-pro"] при flash. Pro в 12,4× дороже (1.74/3.48 vs 0.14/0.28 за 1M) — тихое удорожание без уведомления.
9. stats/ideas/skill-review джобы: timeout 600–1200 c, у skill-review timeout не задан.

### P2
10. 33 автоматизации: 7 выключены, 4 падали по таймауту на фазе model-call-started; 10 еженедельных skill-collection-review (по одной на агента) — можно свести в одну.
11. ~20 легаси-каталогов агентов (fz425, social-*, medhelp, auditor и др.) и 20+ бэкапов openclaw.json — риск перепутать актуальное.
12. pro у maria/lesya не измерен: качество vs flash не сравнивалось, а цена ×12,4.
13. ASV-мониторы: lastDeliveryStatus=not-requested — проверить, доставка не нужна или потеряна.

## План (по эффекту)

1. Вынести Аркадия, Алису и 254785028 в отдельные agent entries + bindings. Алисе: deny memory_*, sessions_*, exec; sandbox.
2. Дать katya и verifier-агентам явные allow/deny (минимум deny sessions_*, memory_*, gateway) и sandbox.
3. HEARTBEAT.md на 10 строк либо отключить heartbeat.
4. Разрезать AGENTS.md: ядро ≤6k символов + references/ (маршрутизация, инфраструктура, медиа). Убрать дубль TOOLS.md.
5. Починить провайдер web_search либо перевести research-джобы на RSS/web_fetch.
6. Сцепить конвейеры: один job на цепочку или gate по mtime входного файла.
7. Убрать fallback на pro или добавить уведомление о срабатывании.
8. Один skill-review вместо 10; один каталог-источник навыков.

## Не проверено
- Агрегированная стоимость LLM: в сессии нет CLI; нужен openclaw gateway usage-cost --json --all-agents --days 30.
- Фактический трафик и доля ошибок по агентам.
- Кто такой 254785028 и уровень доверия.
- Реальное качество pro vs flash на задачах maria/lesya.
