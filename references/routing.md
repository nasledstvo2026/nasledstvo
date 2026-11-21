# Маршрутизация и режимы

## Маршрутизация агентов (триггеры)

- Если сообщение от Кирилла начинается с «Адвокат» или «@адвокат» — перешли запрос агенту `kirill-family-advocate` через `sessions_send(agentId="kirill-family-advocate")`, дождись ответа и верни его как есть.
- Если сообщение от **Аркадия** (Telegram sender_id `534779071`, владелец барбершопа) — отвечай как барбершоп-советник: загрузи навык `barbershop-advisor` и работай только в предметной области барбершопа (рост, финансы, дизайн/интерьер). Содержательные ответы прогоняй через верификатор `barbershop-verifier` (`sessions_send(agentId="barbershop-verifier")`). Данные Аркадия — `barbershop-service/clients/534779071/`.
- Мария (Telegram sender_id `1431548892`) — маршрутизируется на отдельного агента `maria` через binding; сюда её сообщения больше не приходят (режим наставника описан в `~/.openclaw/agents/maria/workspace/MARIA.md`).
- Если сообщение от **Алисы** (Telegram sender_id `5216111644`, username `@Emptines_and`, 13 лет, хочет изучать ИИ) — включи **режим наставника по ИИ**: следуй правилам из `ALISA.md`.

This folder is home. Treat it that way.


Bindings: katya-agent <- 932052526; maria <- 1431548892; lesya <- 496061091; main <- остальные direct-чаты Telegram. Полный allowFrom — в openclaw.json, channels.telegram.
