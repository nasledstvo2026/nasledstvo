# Маршрутизация и режимы

- Кирилл: «Адвокат» / «@адвокат» → sessions_send(agentId="kirill-family-advocate"), ответ вернуть как есть.
- Мария (1431548892) → агент maria, binding.
- Лена (254785028) → агент lena-news, binding. Аналитик новостей, владелец продукта «Дайджест по наследству». Дайджест доставляется ей напрямую джобом lena-html.
- Алиса (5216111644, @Emptines_and, 13 лет) → агент alisa-mentor, binding; наставник по ИИ по ALISA.md.
- Остальные direct-чаты → main.

Bindings: katya-agent 932052526, maria 1431548892, lesya 496061091, lena-news 254785028, alisa-mentor 5216111644, main — catch-all.

Аркадий (534779071) удалён из allowFrom и маршрутизации 21.11.2026; барбершоп-джобы выключены.
