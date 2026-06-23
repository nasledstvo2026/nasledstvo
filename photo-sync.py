#!/usr/bin/env python3
"""
Photo Sync — проверка Dropbox /photo, конвертация в webp, обновление photo.html.
Вызывается либо напрямую, либо через Flask-эндпоинт photo-server.py.
"""

import json
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

# --- Пути ---
WORKSPACE = Path.home() / '.openclaw' / 'workspace'
PHOTO_HTML = WORKSPACE / 'photo.html'
PHOTO_DIR = WORKSPACE / 'photo_files'
STATE_FILE = WORKSPACE / 'photo-state.json'
DROPBOX_PATH = '/photo'

# --- Подключение Dropbox ---
sys.path.insert(0, str(WORKSPACE / 'scripts'))
from dropbox_utils import _get_dbx, list_files as dbx_list, download_file


def init():
    """Создать нужные директории."""
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)


def load_state():
    """Загрузить список уже опубликованных файлов."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {'published': [], 'last_sync': None}


def save_state(state):
    """Сохранить состояние."""
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    print(f"  📝 Состояние сохранено ({len(state['published'])} файлов)", file=sys.stderr)


def convert_to_webp(src_path):
    """Конвертировать изображение в webp (поддерживает HEIC, JPEG, PNG, и т.д.)."""
    from PIL import Image
    from pillow_heif import register_heif_opener
    register_heif_opener()  # поддержка .heic

    img = Image.open(src_path)
    # Конвертируем RGBA/P в RGB если нужно
    if img.mode in ('RGBA', 'P', 'LA'):
        img = img.convert('RGB')

    stem = Path(src_path).stem
    webp_path = PHOTO_DIR / f'{stem}.webp'

    # Оптимизация: quality=85, метод=6 (best compression)
    img.save(str(webp_path), 'WEBP', quality=85, method=6)
    size_kb = webp_path.stat().st_size / 1024
    print(f"  ✅ {webp_path.name} ({size_kb:.1f} KB)", file=sys.stderr)
    return webp_path


def get_existing_images(html_content):
    """Извлечь имена уже опубликованных webp-файлов из photo.html."""
    import re
    # Ищем <img src="xxx.webp"
    matches = re.findall(r'<img\s+src="([^"]+\.webp)"', html_content)
    return set(m.strip() for m in matches)


def generate_photo_html(webp_files):
    """Сгенерировать HTML-блок .photo-grid."""
    cards = []
    for wf in sorted(webp_files):
        cards.append(f'''    <div class="photo-card">
      <img src="photo_files/{wf}" alt="{Path(wf).stem}">
    </div>''')
    return '\n'.join(cards)


def update_photo_html(webp_files):
    """Обновить photo.html — подменить только блок .photo-grid."""
    if not PHOTO_HTML.exists():
        print("  ❌ photo.html не найден", file=sys.stderr)
        return False

    html = PHOTO_HTML.read_text(encoding='utf-8')
    grid_html = generate_photo_html(webp_files)

    # Заменяем содержимое <div class="photo-grid"> ... </div>
    import re
    new_html = re.sub(
        r'<div class="photo-grid">.*?</div>\s*',
        f'<div class="photo-grid">\n{grid_html}\n  </div>\n',
        html,
        flags=re.DOTALL
    )

    if new_html == html:
        print("  ℹ️  Ничего не изменилось", file=sys.stderr)
        return False

    PHOTO_HTML.write_text(new_html, encoding='utf-8')
    print(f"  ✅ photo.html обновлён ({len(webp_files)} фото)", file=sys.stderr)
    return True


def commit_and_push():
    """Закоммитить и запушить изменения в GitHub."""
    print("  📤 Коммит и пуш...", file=sys.stderr)
    ts = datetime.now().strftime('%d.%m.%Y %H:%M')
    try:
        result = subprocess.run(
            ['git', 'add', '-A'],
            cwd=str(WORKSPACE),
            capture_output=True, text=True, timeout=30
        )
        result = subprocess.run(
            ['git', 'commit', '-m', f'📸 Photo sync — {ts}'],
            cwd=str(WORKSPACE),
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0 and 'nothing to commit' not in result.stdout:
            print(f"  ⚠️  commit: {result.stdout.strip()}", file=sys.stderr)
        result = subprocess.run(
            ['git', 'push'],
            cwd=str(WORKSPACE),
            capture_output=True, text=True, timeout=60
        )
        print(f"  ✅ Git push: {result.stdout.strip()[:200]}", file=sys.stderr)
        return True
    except subprocess.TimeoutExpired:
        print("  ❌ Git timeout", file=sys.stderr)
        return False
    except Exception as e:
        print(f"  ❌ Git error: {e}", file=sys.stderr)
        return False


def sync(new_only=True):
    """
    Основная функция синхронизации.
    new_only=True — только новые файлы
    """
    init()
    state = load_state()
    published = set(state.get('published', []))

    print(f"🔍 Проверка Dropbox: {DROPBOX_PATH}", file=sys.stderr)
    try:
        files = dbx_list(DROPBOX_PATH)
    except Exception as e:
        print(f"  ❌ Ошибка Dropbox: {e}", file=sys.stderr)
        return {'success': False, 'error': str(e)}

    if not files:
        print("  ℹ️  В /photo пусто", file=sys.stderr)
        return {'success': True, 'new': 0, 'total': 0}

    # Фильтруем только изображения
    img_exts = {'.jpg', '.jpeg', '.png', '.heic', '.heif', '.gif', '.bmp', '.tiff', '.webp'}
    images = [f for f in files if Path(f['name']).suffix.lower() in img_exts]
    images.sort(key=lambda x: x['name'])

    print(f"  📸 Найдено {len(images)} изображений в Dropbox", file=sys.stderr)

    new_files = []
    for img in images:
        stem = Path(img['name']).stem
        webp_name = f'{stem}.webp'

        if new_only and webp_name in published:
            continue

        # Скачиваем
        local_path = PHOTO_DIR / img['name']
        try:
            print(f"  ⬇️  {img['name']}...", file=sys.stderr)
            download_file(img['path_display'], str(local_path))
        except Exception as e:
            print(f"  ⚠️  Ошибка скачивания {img['name']}: {e}", file=sys.stderr)
            continue

        # Конвертируем
        try:
            webp_path = convert_to_webp(local_path)
            new_files.append(webp_path.name)
            # Удаляем оригинал
            local_path.unlink(missing_ok=True)
        except Exception as e:
            print(f"  ⚠️  Ошибка конвертации {img['name']}: {e}", file=sys.stderr)
            continue

    if not new_files:
        print("  ℹ️  Новых файлов нет", file=sys.stderr)
        return {'success': True, 'new': 0, 'total': len(images)}

    # Обновляем состояние
    state['published'].extend(new_files)
    state['last_sync'] = datetime.now().isoformat()

    # Перечитываем photo.html и обновляем
    all_webp = sorted(set(
        state['published'] +
        [str(p.name) for p in PHOTO_DIR.glob('*.webp')]
    ))

    updated = update_photo_html(all_webp)

    if updated:
        save_state(state)
        commit_and_push()

    return {
        'success': True,
        'new': len(new_files),
        'new_files': new_files,
        'total': len(images),
        'published_total': len(all_webp),
    }


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='Photo Sync — Dropbox → webp → GitHub Pages')
    ap.add_argument('--all', action='store_true', help='Переобработать ВСЕ файлы (не только новые)')
    args = ap.parse_args()

    result = sync(new_only=not args.all)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if result.get('success') else 1)
