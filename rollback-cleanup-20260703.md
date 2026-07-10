# План отката: удаление сиротских файлов 03.07.2026

## Если что-то пошло не так

```bash
cd ~/.openclaw/workspace

# Вернуть последний commit (если ничего нового не закоммичено после)
git reset --hard HEAD~1
git push --force origin master

# Или точечно вернуть удалённые файлы из последнего commit
git checkout HEAD~1 -- sber-claims-2026.html
git checkout HEAD~1 -- stats-inheritance-template.html
git checkout HEAD~1 -- data_1.json
git checkout HEAD~1 -- analytical_review_may_2026_social_support.md
git checkout HEAD~1 -- mermaid-config.json
git checkout HEAD~1 -- setup-nginx-proxy.sh
git checkout HEAD~1 -- search_inheritance.sh
git checkout HEAD~1 -- katya-stats-data.md
git checkout HEAD~1 -- scripts/legalmcp-update-v2.py
git checkout HEAD~1 -- scripts/legalmcp-update-v3.py
git checkout HEAD~1 -- scripts/aidj-nginx-live.conf
git checkout HEAD~1 -- scripts/aidj-nginx.conf
git checkout HEAD~1 -- scripts/aidj-nginx.conf.bak
git checkout HEAD~1 -- scripts/dropbox-upload.py
git checkout HEAD~1 -- scripts/dropbox-get-flac.py
git checkout HEAD~1 -- scripts/dropbox-get-folder.py
git checkout HEAD~1 -- knowledge/katrin/product-44fz-223fz.md
git checkout HEAD~1 -- dropbox-tools.md

# Закоммитить возврат
git add -A && git commit -m "rollback: restored deleted files 03.07.2026" && git push
```

## Проверка отката

```bash
# Убедиться что файлы вернулись
ls -la sber-claims-2026.html stats-inheritance-template.html data_1.json

# Убедиться что сайт жив
curl -s https://nasledstvo2026.github.io/nasledstvo/sber-claims-2026.html | head -5
```
