# ТЗ: FastAPI-обёртка для embedding-поиска

## Проблема
CLI-вариант грузит модель при каждом вызове → **28 сек**. Надо чтобы модель жила в памяти постоянно.

## Шаг 1. Установка
```bash
cd /home/user1/phoenix
./venv/bin/pip install fastapi uvicorn
```

## Шаг 2. API-сервер

Создать `search_server.py`:

```python
from fastapi import FastAPI, Query
from sentence_transformers import SentenceTransformer
import faiss, json, numpy as np
from contextlib import asynccontextmanager

MODEL = None
INDEX = None
META = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global MODEL, INDEX, META
    MODEL = SentenceTransformer("intfloat/multilingual-e5-small")
    INDEX = faiss.read_index("fz425_index.faiss")
    with open("fz425_meta.json") as f:
        META = json.load(f)
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/search")
async def search(q: str = Query(...), k: int = 5, threshold: float = 0.83):
    vec = MODEL.encode(f"query: {q}", normalize_embeddings=True)
    scores, ids = INDEX.search(np.array([vec]), k)
    results = []
    for score, idx in zip(scores[0], ids[0]):
        if score < threshold:
            continue
        results.append({**META[idx], "score": float(score)})
    return {"query": q, "results": results}
```

**Порт:** 8765 (свободный, не пересекается с gateway 18789).

## Шаг 3. Тестирование

Запустить вручную:
```bash
cd /home/user1/phoenix
./venv/bin/uvicorn search_server:app --host 127.0.0.1 --port 8765
```

Проверить:
```bash
curl "http://127.0.0.1:8765/search?q=ПНО+срок+обработки+3+часа"
# → JSON: {"query":"...", "results":[{source, article, title, text, score}]}
```

Прогнать те же 6 тестов через `curl` — убедиться что результаты идентичны CLI.

## Шаг 4. systemd unit

Файл `~/.config/systemd/user/law-search.service`:
```ini
[Unit]
Description=Law Embedding Search API (e5-small)
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/user1/phoenix
ExecStart=/home/user1/phoenix/venv/bin/uvicorn search_server:app --host 127.0.0.1 --port 8765
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now law-search.service
```

Проверить: `systemctl --user status law-search.service` — должен быть активен, RAM ~600-700 MB (модель в памяти).

## Шаг 5. Интеграция в fz425-agent

В AGENTS.md fz425-agent добавить:
```
## Поиск по законам
Вместо FTS — вызов API:
curl -s "http://127.0.0.1:8765/search?q=$(python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))' "$QUERY")"
→ JSON с топ-5 статей и метаданными
```

Время поиска: **< 50 мс** вместо 28 сек. Модель загружена постоянно.

## Ожидаемый результат
- Модель в памяти, поиск < 50 мс
- systemd unit, автозапуск после ребута
- 6/6 тестов проходят идентично CLI
- fz425-agent получает статьи через `curl localhost:8765`
