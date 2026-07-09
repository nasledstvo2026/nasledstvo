#!/usr/bin/env python3
"""
HTML Generator — генерация веб-версии бизнес-требований.

Story 4.2 — Generator: создание веб-версии (FR18, FR21).
Создаёт статическую HTML-страницу, идентичную по содержанию DOCX-версии.
Готова для GitHub Pages: самодостаточный HTML-файл со встроенными CSS.

Acceptance Criteria (FR18, FR21):
- То же содержание, что DOCX
- Современный читаемый дизайн (шрифты, отступы, цвета согласно UX Spec)
- Адаптивная вёрстка для мобильных и десктопа
- Печать (CSS @media print)
- Cover page, TOC, 7 blocks with depth labels, risk section
- GitHub Pages ready

API:
    generate_html(data) — основная функция, возвращает HTML-строку
    main() — CLI-точка входа

Формат входных данных (JSON) — идентичен docx-gen.py:
    {
        "title": "Документ бизнес-требований",
        "createdAt": "2026-07-08T20:00:00.000Z",
        "sessionId": "session_xxx",
        "telegramUserId": 12345,
        "username": "Пользователь",
        "totalBlocks": 7,
        "blocks": [...],
        "risks": {...},
        "completedSubsections": 20,
        "totalSubsections": 21,
        "fullText": "..."
    }
"""

import json
import sys
import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# ==================== Logging ====================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] html-gen: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('html-gen')


# ==================== Constants ====================

# Цветовая палитра — единая с DOCX-версией (Story 4.5 / FR21)
COLOR_PRIMARY = '#1F4E79'      # Тёмно-синий — заголовки (DOCX: RGB(0x1F,0x4E,0x79))
COLOR_ACCENT = '#2E75B6'       # Синий — акценты (DOCX: RGB(0x2E,0x75,0xB6))
COLOR_ACCENT_LIGHT = '#63B3ED' # Светло-синий
COLOR_TEXT = '#2D3748'         # Тёмно-серый — основной текст
COLOR_TEXT_LIGHT = '#718096'   # Серый — второстепенный текст
COLOR_BG = '#FFFFFF'           # Белый фон
COLOR_BG_ALT = '#F7FAFC'       # Светло-серый фон для альтернативных секций
COLOR_BG_TABLE = '#EDF2F7'     # Фон таблиц
COLOR_SUCCESS = '#38A169'      # Зелёный — подтверждение
COLOR_WARNING = '#DD6B20'      # Оранжевый — предупреждение
COLOR_DANGER = '#E53E3E'       # Красный — высокий риск
COLOR_BORDER = '#E2E8F0'       # Светло-серый — границы

# Названия блоков (fallback, если не пришли из данных)
BLOCK_NAMES = {
    1: 'Предпосылки и цели',
    2: 'Заинтересованные стороны',
    3: 'Текущее состояние',
    4: 'Требования',
    5: 'Критерии приёмки',
    6: 'Технические заметки',
    7: 'Риски',
}

# Ярлыки категорий рисков
CATEGORY_LABELS = {
    'technical': 'Технические риски',
    'org': 'Организационные риски',
    'organizational': 'Организационные риски',
    'business': 'Бизнес-риски',
    'adoption': 'Риски внедрения',
    'uncategorized': 'Прочие риски',
}

# Ярлыки глубины
DEPTH_LABELS = {
    'L3': 'Глубокая проработка (L3) — анализ коренных причин',
    'L2': 'Детальная проработка (L2) — с примерами и контекстом',
    'L1': 'Поверхностная проработка (L1) — общее описание',
    'none': 'Не заполнено',
}

DEPTH_COLORS = {
    'L3': COLOR_SUCCESS,
    'L2': COLOR_ACCENT,
    'L1': COLOR_WARNING,
    'none': COLOR_TEXT_LIGHT,
}

DEPTH_ICONS = {
    'L3': '●',
    'L2': '◉',
    'L1': '○',
    'none': '○',
}

# Шрифты
FONT_FAMILY = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
FONT_FAMILY_HEADING = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"


# ==================== CSS ====================

def _build_css() -> str:
    """Строит полный CSS для документа (responsive + print)."""
    return f'''
/* ===== Reset & Base ===== */
*, *::before, *::after {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}}

html {{
    font-size: 16px;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}}

body {{
    font-family: {FONT_FAMILY};
    color: {COLOR_TEXT};
    background-color: {COLOR_BG};
    line-height: 1.6;
    padding: 0;
}}

/* ===== Layout ===== */
.container {{
    max-width: 960px;
    margin: 0 auto;
    padding: 0 24px;
}}

/* ===== Cover Page ===== */
.cover-page {{
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    padding: 80px 24px;
    border-bottom: 1px solid {COLOR_BORDER};
    position: relative;
}}

.cover-page::before {{
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 6px;
    background: linear-gradient(90deg, {COLOR_PRIMARY}, {COLOR_ACCENT}, {COLOR_ACCENT_LIGHT});
}}

.cover-rule {{
    width: 120px;
    height: 4px;
    background: linear-gradient(90deg, {COLOR_PRIMARY}, {COLOR_ACCENT});
    margin: 0 auto 40px;
    border-radius: 2px;
}}

.cover-title {{
    font-size: 2.5rem;
    font-weight: 700;
    color: {COLOR_PRIMARY};
    margin-bottom: 8px;
    line-height: 1.2;
}}

.cover-subtitle {{
    font-size: 1.2rem;
    font-weight: 400;
    color: {COLOR_TEXT_LIGHT};
    margin-bottom: 48px;
}}

.cover-meta {{
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 8px 24px;
    text-align: left;
    font-size: 0.95rem;
}}

.cover-meta dt {{
    font-weight: 600;
    color: {COLOR_PRIMARY};
    white-space: nowrap;
}}

.cover-meta dd {{
    color: {COLOR_TEXT};
}}

/* ===== Navigation / TOC ===== */
.toc-page {{
    padding: 60px 0;
    border-bottom: 1px solid {COLOR_BORDER};
}}

.toc-title {{
    font-size: 1.75rem;
    font-weight: 700;
    color: {COLOR_PRIMARY};
    margin-bottom: 32px;
}}

.toc-block {{
    margin-bottom: 20px;
}}

.toc-block-header {{
    font-size: 1.05rem;
    font-weight: 600;
    color: {COLOR_PRIMARY};
    margin-bottom: 6px;
    padding: 8px 12px;
    background: {COLOR_BG_ALT};
    border-radius: 6px;
    border-left: 3px solid {COLOR_PRIMARY};
}}

.toc-subsection {{
    display: flex;
    align-items: center;
    padding: 4px 12px 4px 28px;
    font-size: 0.92rem;
    color: {COLOR_TEXT};
    text-decoration: none;
    transition: background 0.15s;
    border-radius: 4px;
}}

.toc-subsection:hover {{
    background: {COLOR_BG_ALT};
}}

.toc-depth-icon {{
    margin-right: 8px;
    font-size: 0.8rem;
}}

.toc-depth-label {{
    font-size: 0.78rem;
    color: {COLOR_TEXT_LIGHT};
    margin-left: 8px;
    font-style: italic;
}}

/* ===== Section / Block ===== */
.document-body {{
    padding: 40px 0;
}}

.section {{
    margin-bottom: 48px;
    padding-top: 8px;
}}

.section-header {{
    margin-bottom: 24px;
    padding-bottom: 12px;
    border-bottom: 2px solid {COLOR_BORDER};
}}

.section-title {{
    font-size: 1.65rem;
    font-weight: 700;
    color: {COLOR_PRIMARY};
    line-height: 1.3;
}}

/* ===== Subsection ===== */
.subsection {{
    margin-bottom: 28px;
}}

.subsection-header {{
    display: flex;
    align-items: baseline;
    gap: 12px;
    margin-bottom: 8px;
}}

.subsection-title {{
    font-size: 1.15rem;
    font-weight: 600;
    color: {COLOR_TEXT};
}}

.depth-badge {{
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 0.72rem;
    font-weight: 500;
    padding: 2px 8px;
    border-radius: 12px;
    white-space: nowrap;
}}

.subsection-text {{
    font-size: 0.95rem;
    line-height: 1.7;
    color: {COLOR_TEXT};
}}

.subsection-text p {{
    margin-bottom: 12px;
}}

.subsection-text ul,
.subsection-text ol {{
    margin: 8px 0 12px 24px;
}}

.subsection-text li {{
    margin-bottom: 4px;
}}

.subsection-empty {{
    font-style: italic;
    color: {COLOR_TEXT_LIGHT};
    padding: 16px;
    background: {COLOR_BG_ALT};
    border-radius: 6px;
    font-size: 0.9rem;
}}

/* ===== Risk Section ===== */
.risk-section {{
    margin-top: 48px;
    padding-top: 32px;
    border-top: 3px solid {COLOR_PRIMARY};
}}

.risk-summary {{
    display: flex;
    gap: 24px;
    flex-wrap: wrap;
    margin-bottom: 32px;
    padding: 20px;
    background: {COLOR_BG_ALT};
    border-radius: 8px;
}}

.risk-stat {{
    text-align: center;
}}

.risk-stat-value {{
    font-size: 1.8rem;
    font-weight: 700;
    color: {COLOR_PRIMARY};
    line-height: 1;
}}

.risk-stat-label {{
    font-size: 0.78rem;
    color: {COLOR_TEXT_LIGHT};
    margin-top: 4px;
}}

.risk-category {{
    margin-bottom: 32px;
}}

.risk-category-title {{
    font-size: 1.1rem;
    font-weight: 600;
    color: {COLOR_PRIMARY};
    margin-bottom: 16px;
    padding-bottom: 6px;
    border-bottom: 1px solid {COLOR_BORDER};
}}

.risk-card {{
    padding: 16px;
    margin-bottom: 12px;
    background: {COLOR_BG};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    border-left: 4px solid {COLOR_BORDER};
}}

.risk-card.high {{ border-left-color: {COLOR_DANGER}; }}
.risk-card.medium {{ border-left-color: {COLOR_WARNING}; }}
.risk-card.low {{ border-left-color: {COLOR_SUCCESS}; }}

.risk-card-title {{
    font-weight: 600;
    font-size: 0.95rem;
    margin-bottom: 4px;
    color: {COLOR_TEXT};
}}

.risk-card-details {{
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    font-size: 0.82rem;
    color: {COLOR_TEXT_LIGHT};
    margin-top: 6px;
}}

.risk-card-detail {{
    display: flex;
    align-items: center;
    gap: 4px;
}}

.risk-card-detail-label {{
    font-weight: 500;
    color: {COLOR_TEXT_LIGHT};
}}

.risk-card-mitigation {{
    margin-top: 8px;
    padding: 8px 12px;
    background: {COLOR_BG_ALT};
    border-radius: 6px;
    font-size: 0.88rem;
}}

.risk-card-mitigation strong {{
    color: {COLOR_SUCCESS};
}}

.risk-table {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 24px;
    font-size: 0.88rem;
}}

.risk-table th {{
    background: {COLOR_PRIMARY};
    color: white;
    padding: 10px 12px;
    text-align: left;
    font-weight: 600;
}}

.risk-table td {{
    padding: 8px 12px;
    border-bottom: 1px solid {COLOR_BORDER};
}}

.risk-table tr:nth-child(even) td {{
    background: {COLOR_BG_ALT};
}}

.risk-table tr:hover td {{
    background: #EBF8FF;
}}

/* ===== Progress Bar ===== */
.progress-section {{
    padding: 24px 0;
    margin-bottom: 32px;
}}

.progress-bar-bg {{
    width: 100%;
    height: 8px;
    background: {COLOR_BORDER};
    border-radius: 4px;
    overflow: hidden;
}}

.progress-bar-fill {{
    height: 100%;
    background: linear-gradient(90deg, {COLOR_ACCENT}, {COLOR_PRIMARY});
    border-radius: 4px;
    transition: width 0.5s ease;
}}

.progress-stats {{
    display: flex;
    justify-content: space-between;
    margin-top: 8px;
    font-size: 0.82rem;
    color: {COLOR_TEXT_LIGHT};
}}

/* ===== Footer ===== */
.document-footer {{
    padding: 32px 0;
    text-align: center;
    border-top: 1px solid {COLOR_BORDER};
    font-size: 0.82rem;
    color: {COLOR_TEXT_LIGHT};
}}

.document-footer a {{
    color: {COLOR_ACCENT};
    text-decoration: none;
}}

.document-footer a:hover {{
    text-decoration: underline;
}}

/* ===== Top Navigation Bar ===== */
.top-nav {{
    position: sticky;
    top: 0;
    z-index: 100;
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(8px);
    border-bottom: 1px solid {COLOR_BORDER};
    padding: 0 24px;
}}

.top-nav-inner {{
    max-width: 960px;
    margin: 0 auto;
    display: flex;
    justify-content: space-between;
    align-items: center;
    height: 48px;
}}

.top-nav-title {{
    font-size: 0.88rem;
    font-weight: 600;
    color: {COLOR_PRIMARY};
}}

.top-nav-links {{
    display: flex;
    gap: 16px;
    font-size: 0.82rem;
}}

.top-nav-links a {{
    color: {COLOR_TEXT_LIGHT};
    text-decoration: none;
    transition: color 0.15s;
}}

.top-nav-links a:hover {{
    color: {COLOR_ACCENT};
}}

/* ===== TOC Sidebar (mobile hamburger simplified) ===== */
.toc-toggle {{
    display: none;
}}

/* ===== Print Styles ===== */
@media print {{
    .top-nav {{
        display: none;
    }}

    .cover-page {{
        min-height: 100vh;
        page-break-after: always;
        padding: 60px 24px;
    }}

    .toc-page {{
        page-break-after: always;
    }}

    .section {{
        page-break-inside: avoid;
    }}

    .subsection {{
        page-break-inside: avoid;
    }}

    .risk-card {{
        page-break-inside: avoid;
    }}

    .risk-table {{
        page-break-inside: auto;
    }}

    body {{
        font-size: 11pt;
    }}

    .cover-title {{
        font-size: 24pt;
    }}

    .section-title {{
        font-size: 16pt;
    }}

    a {{
        color: {COLOR_TEXT} !important;
        text-decoration: none !important;
    }}
}}

/* ===== Responsive ===== */
@media (max-width: 768px) {{
    .container {{
        padding: 0 16px;
    }}

    .cover-title {{
        font-size: 1.8rem;
    }}

    .cover-subtitle {{
        font-size: 1rem;
    }}

    .cover-meta {{
        grid-template-columns: 1fr;
        gap: 4px;
        text-align: center;
    }}

    .cover-meta dt {{
        white-space: normal;
    }}

    .section-title {{
        font-size: 1.35rem;
    }}

    .subsection-header {{
        flex-direction: column;
        gap: 4px;
    }}

    .risk-summary {{
        justify-content: center;
    }}

    .risk-card-details {{
        flex-direction: column;
        gap: 4px;
    }}

    .top-nav-inner {{
        height: auto;
        padding: 8px 0;
        flex-direction: column;
        gap: 4px;
    }}
}}

@media (max-width: 480px) {{
    .cover-title {{
        font-size: 1.4rem;
    }}

    .cover-subtitle {{
        font-size: 0.9rem;
    }}

    .risk-table {{
        font-size: 0.78rem;
    }}

    .risk-table th,
    .risk-table td {{
        padding: 6px 8px;
    }}
}}
'''


# ==================== HTML Builders ====================

def _format_date(iso_str: str) -> str:
    """Форматирует ISO-дату в читаемый русский формат."""
    if not iso_str:
        return '—'
    try:
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        return dt.strftime('%d.%m.%Y %H:%M')
    except (ValueError, AttributeError):
        return iso_str


def _format_level(level: float) -> str:
    """Форматирует числовой уровень риска в текстовый."""
    if level is None:
        return 'Не определена'
    if level >= 0.7:
        return 'Высокая'
    if level >= 0.4:
        return 'Средняя'
    if level >= 0.1:
        return 'Низкая'
    return 'Не определена'


def _get_risk_level_class(level: float) -> str:
    """Возвращает CSS-класс для уровня риска."""
    if level is None:
        return ''
    if level >= 0.7:
        return 'high'
    if level >= 0.4:
        return 'medium'
    if level >= 0.1:
        return 'low'
    return ''


def _get_category_label(category: str) -> str:
    """Возвращает русскоязычную метку категории."""
    return CATEGORY_LABELS.get(category, category)


def _escape_html(text: str) -> str:
    """Экранирует HTML-спецсимволы."""
    if not text:
        return ''
    replacements = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _render_paragraphs(text: str) -> str:
    """Рендерит текст в HTML-параграфы, обрабатывая списки и переносы."""
    if not text or text.strip() == '':
        return ''

    lines = text.split('\n')
    html_parts = []
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # Маркированный список
        if line.startswith('—') or line.startswith('- ') or line.startswith('* ') or line.startswith('•'):
            html_parts.append('<ul>')
            while i < len(lines):
                l = lines[i].strip()
                if l.startswith('—') or l.startswith('- ') or l.startswith('* ') or l.startswith('•'):
                    item_text = l
                    for marker in ['— ', '- ', '* ', '• ']:
                        if item_text.startswith(marker):
                            item_text = item_text[len(marker):]
                            break
                    html_parts.append(f'<li>{_escape_html(item_text)}</li>')
                    i += 1
                elif l == '':
                    i += 1
                    break
                else:
                    break
            html_parts.append('</ul>')
            continue

        # Нумерованный список
        if len(line) > 2 and line[0].isdigit() and line[1] == '.':
            html_parts.append('<ol>')
            while i < len(lines):
                l = lines[i].strip()
                if len(l) > 2 and l[0].isdigit() and l[1] == '.':
                    num_end = l.find('.')
                    item_text = l[num_end+1:].strip()
                    html_parts.append(f'<li>{_escape_html(item_text)}</li>')
                    i += 1
                elif l == '':
                    i += 1
                    break
                else:
                    break
            html_parts.append('</ol>')
            continue

        # Обычный параграф
        html_parts.append(f'<p>{_escape_html(line)}</p>')
        i += 1

    return '\n'.join(html_parts)


# ==================== Cover Page ====================

def _build_cover_html(data: Dict) -> str:
    """Строит секцию титульной страницы HTML."""
    title = data.get('title', 'Документ бизнес-требований')
    created_at = data.get('createdAt', '')
    session_id = data.get('sessionId', '—')
    telegram_user = data.get('telegramUserId', '—')
    username = data.get('username', None)
    total_blocks = data.get('totalBlocks', 7)
    completed = data.get('completedSubsections', 0)
    total = data.get('totalSubsections', 0)
    risks_total = data.get('risks', {}).get('total', 0)

    meta_rows = [
        f'<dt>Дата создания</dt><dd>{_format_date(created_at)}</dd>',
        f'<dt>Сессия</dt><dd>{_escape_html(session_id)}</dd>',
    ]
    if username:
        meta_rows.append(f'<dt>Автор</dt><dd>{_escape_html(username)}</dd>')
    meta_rows.append(f'<dt>Автор (Telegram ID)</dt><dd>{_escape_html(str(telegram_user))}</dd>')
    meta_rows.append(f'<dt>Количество разделов</dt><dd>{total_blocks}</dd>')
    meta_rows.append(f'<dt>Заполнено подразделов</dt><dd>{completed}/{total}</dd>')
    meta_rows.append(f'<dt>Идентифицировано рисков</dt><dd>{risks_total}</dd>')

    return f'''
<section class="cover-page" id="top">
    <div class="cover-rule"></div>
    <h1 class="cover-title">{_escape_html(title)}</h1>
    <p class="cover-subtitle">Business Requirements Document</p>
    <dl class="cover-meta">
        {''.join(meta_rows)}
    </dl>
</section>
'''


# ==================== Table of Contents ====================

def _build_toc_html(data: Dict) -> str:
    """Строит секцию оглавления."""
    blocks = data.get('blocks', [])

    toc_items = []
    for block in blocks:
        bid = block.get('blockId', 0)
        bname = block.get('blockName', BLOCK_NAMES.get(bid, f'Блок {bid}'))
        subsections = block.get('subsections', [])

        subs_links = []
        for sub in subsections:
            sub_id = sub.get('subsectionId', '')
            sub_name = sub.get('subsectionName', '')
            depth = sub.get('depthReached', 'none')
            icon = DEPTH_ICONS.get(depth, '○')
            depth_label = {
                'L3': ' (глубоко)',
                'L2': ' (детально)',
                'L1': ' (поверхностно)',
                'none': '',
            }.get(depth, '')
            depth_color = DEPTH_COLORS.get(depth, COLOR_TEXT_LIGHT)
            subs_links.append(
                f'''<a href="#{_escape_html(sub_id)}" class="toc-subsection">'''
                f'''<span class="toc-depth-icon" style="color:{depth_color}">{icon}</span>'''
                f'''{_escape_html(sub_id)}. {_escape_html(sub_name)}'''
                f'''<span class="toc-depth-label">{_escape_html(depth_label)}</span>'''
                f'''</a>'''
            )

        toc_items.append(f'''
    <div class="toc-block">
        <div class="toc-block-header">Блок {bid}. {_escape_html(bname)}</div>
        {''.join(subs_links)}
    </div>
''')

    # Секция рисков
    risks = data.get('risks', {})
    risk_count = risks.get('total', 0)
    toc_items.append(f'''
    <div class="toc-block">
        <div class="toc-block-header">Блок 7. Риски и митигации ({risk_count} риск{"ов" if risk_count != 1 else ""})</div>
        <a href="#risks" class="toc-subsection">
            <span class="toc-depth-icon">▼</span>
            Все риски ({risk_count})
        </a>
    </div>
''')

    return f'''
<section class="toc-page" id="toc">
    <div class="container">
        <h2 class="toc-title">Содержание</h2>
        {''.join(toc_items)}
    </div>
</section>
'''


# ==================== Block Sections ====================

def _build_block_html(block: Dict) -> str:
    """Строит HTML для одного блока.

    Нумерация идентична DOCX-версии: "Блок {bid}. {bname}" (FR21).
    """
    bid = block.get('blockId', 0)
    bname = block.get('blockName', BLOCK_NAMES.get(bid, f'Блок {bid}'))
    subsections = block.get('subsections', [])

    subs_html = []
    for sub in subsections:
        sub_id = sub.get('subsectionId', '')
        sub_name = sub.get('subsectionName', '')
        text = sub.get('text', '')
        depth = sub.get('depthReached', 'none')

        depth_label = DEPTH_LABELS.get(depth, depth)
        depth_color = DEPTH_COLORS.get(depth, COLOR_TEXT_LIGHT)

        # Текст подраздела
        if text and text.strip() and not text.strip().startswith('— *Не заполнено'):
            content_html = f'<div class="subsection-text">{_render_paragraphs(text)}</div>'
        else:
            content_html = f'<div class="subsection-empty">— Нет данных.</div>'

        subs_html.append(f'''
    <div class="subsection" id="{_escape_html(sub_id)}">
        <div class="subsection-header">
            <h3 class="subsection-title">{_escape_html(sub_id)}. {_escape_html(sub_name)}</h3>
            <span class="depth-badge" style="background:{depth_color}15;color:{depth_color}">{_escape_html(depth_label)}</span>
        </div>
        {content_html}
    </div>
''')

    return f'''
<section class="section" id="block-{bid}">
    <div class="section-header">
        <h2 class="section-title">Блок {bid}. {_escape_html(bname)}</h2>
    </div>
    {''.join(subs_html)}
</section>
'''


# ==================== Risk Section ====================

def _build_risk_html(risks: Dict) -> str:
    """Строит секцию рисков HTML.

    Заголовок идентичен DOCX-версии: "Риски и митигации" (FR21).
    """
    items = risks.get('items', [])
    by_category = risks.get('byCategory', {})

    html_parts = ['''
<section class="risk-section" id="risks">
    <div class="section-header">
        <h2 class="section-title">Риски и митигации</h2>
    </div>
''']

    if not items:
        html_parts.append('<div class="subsection-empty">Риски не идентифицированы.</div>')
        html_parts.append('</section>')
        return '\n'.join(html_parts)

    # Сводка
    by_category_stats = by_category or {}
    total_categories = len(by_category_stats)
    has_mitigation = sum(1 for i in items if i.get('mitigation'))
    high_risk = sum(1 for i in items if i.get('probability', 0) is not None and i['probability'] >= 0.7)

    html_parts.append(f'''
    <div class="risk-summary">
        <div class="risk-stat">
            <div class="risk-stat-value">{len(items)}</div>
            <div class="risk-stat-label">Всего рисков</div>
        </div>
        <div class="risk-stat">
            <div class="risk-stat-value">{total_categories}</div>
            <div class="risk-stat-label">Категорий</div>
        </div>
        <div class="risk-stat">
            <div class="risk-stat-value">{has_mitigation}</div>
            <div class="risk-stat-label">С митигацией</div>
        </div>
        <div class="risk-stat">
            <div class="risk-stat-value" style="color:{COLOR_DANGER}">{high_risk}</div>
            <div class="risk-stat-label">Высокого риска</div>
        </div>
    </div>
''')

    # Таблица рисков
    html_parts.append('''
    <table class="risk-table">
        <thead>
            <tr>
                <th>№</th>
                <th>Риск</th>
                <th>Категория</th>
                <th>Вероятность</th>
                <th>Влияние</th>
            </tr>
        </thead>
        <tbody>
''')

    for idx, item in enumerate(items):
        risk_text = item.get('text', '—')
        if len(risk_text) > 120:
            risk_text = risk_text[:117] + '...'
        probability = item.get('probability')
        impact = item.get('impact')
        html_parts.append(f'''
            <tr>
                <td>{idx + 1}</td>
                <td>{_escape_html(risk_text)}</td>
                <td>{_escape_html(_get_category_label(item.get('category', 'uncategorized')))}</td>
                <td style="color:{_get_risk_color_css(probability)}">{_format_level(probability)}</td>
                <td style="color:{_get_risk_color_css(impact)}">{_format_level(impact)}</td>
            </tr>
''')

    html_parts.append('''
        </tbody>
    </table>
''')

    # Детальные карточки по категориям
    for category, cat_items in by_category_stats.items():
        cat_label = _get_category_label(category)
        html_parts.append(f'''
    <div class="risk-category">
        <h3 class="risk-category-title">{_escape_html(cat_label)} ({len(cat_items)})</h3>
''')

        for idx, item in enumerate(cat_items):
            risk_text = item.get('text', '—')
            probability = item.get('probability')
            impact = item.get('impact')
            mitigation = item.get('mitigation')
            level_class = _get_risk_level_class(probability or impact or 0)

            html_parts.append(f'''
        <div class="risk-card {level_class}">
            <div class="risk-card-title">Риск {idx + 1}. {_escape_html(risk_text)}</div>
            <div class="risk-card-details">
''')

            if probability is not None:
                html_parts.append(f'''
                <span class="risk-card-detail">
                    <span class="risk-card-detail-label">Вероятность:</span>
                    {_format_level(probability)}
                </span>
''')
            if impact is not None:
                html_parts.append(f'''
                <span class="risk-card-detail">
                    <span class="risk-card-detail-label">Влияние:</span>
                    {_format_level(impact)}
                </span>
''')

            html_parts.append('''
            </div>
''')

            if mitigation:
                html_parts.append(f'''
            <div class="risk-card-mitigation">
                <strong>Митигация:</strong> {_escape_html(mitigation)}
            </div>
''')

            html_parts.append('''
        </div>
''')

        html_parts.append('''
    </div>
''')

    html_parts.append('</section>')
    return '\n'.join(html_parts)


def _get_risk_color_css(level: float) -> str:
    """Возвращает CSS-цвет для уровня риска."""
    if level is None:
        return COLOR_TEXT_LIGHT
    if level >= 0.7:
        return COLOR_DANGER
    if level >= 0.4:
        return COLOR_WARNING
    if level >= 0.1:
        return COLOR_SUCCESS
    return COLOR_TEXT_LIGHT


# ==================== Progress Section ====================

def _build_progress_html(data: Dict) -> str:
    """Строит секцию прогресса."""
    completed = data.get('completedSubsections', 0)
    total = data.get('totalSubsections', 0)
    percent = data.get('completionPercent', 0)
    if total > 0:
        percent = round((completed / total) * 100)
    risks_total = data.get('risks', {}).get('total', 0)

    return f'''
<div class="progress-section">
    <div class="progress-bar-bg">
        <div class="progress-bar-fill" style="width:{percent}%"></div>
    </div>
    <div class="progress-stats">
        <span>Подразделы: {completed}/{total} ({percent}%)</span>
        <span>Рисков: {risks_total}</span>
        <span>Блоков: {data.get('totalBlocks', 7)}</span>
    </div>
</div>
'''


# ==================== Main Generation ====================

def generate_html(data: dict) -> str:
    """
    Генерирует полную HTML-страницу с документом БТ.

    Args:
        data: Словарь с данными БТ (блоки, ответы, риски)

    Returns:
        Полная HTML-строка
    """
    logger.info("Starting HTML generation")

    css = _build_css()

    # Строим компоненты
    cover_html = _build_cover_html(data)
    toc_html = _build_toc_html(data)
    progress_html = _build_progress_html(data)

    # Блоки
    blocks = data.get('blocks', [])
    logger.info(f"Building {len(blocks)} block(s)...")
    blocks_html = []
    for block in blocks:
        blocks_html.append(_build_block_html(block))

    # Риски
    risks = data.get('risks', {})
    logger.info(f"Building risk section ({risks.get('total', 0)} risks)...")
    risk_html = _build_risk_html(risks)

    # Footer
    generated_at = datetime.now().strftime('%d.%m.%Y %H:%M')
    session_id = _escape_html(data.get('sessionId', '—'))

    # Собираем полный HTML
    html = f'''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Документ бизнес-требований — Мамкин аналитик">
    <title>{_escape_html(data.get('title', 'Документ бизнес-требований'))}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
{css}
    </style>
</head>
<body>

<!-- Top Navigation -->
<nav class="top-nav">
    <div class="top-nav-inner">
        <span class="top-nav-title">{_escape_html(data.get('title', 'Бизнес-требования'))}</span>
        <div class="top-nav-links">
            <a href="#top">Наверх</a>
            <a href="#toc">Содержание</a>
            <a href="#risks">Риски</a>
        </div>
    </div>
</nav>

<!-- Cover Page -->
{cover_html}

<!-- Table of Contents -->
{toc_html}

<!-- Document Body -->
<div class="document-body">
    <div class="container">

        {progress_html}

        {''.join(blocks_html)}

        {risk_html}

    </div>
</div>

<!-- Footer -->
<div class="document-footer">
    <div class="container">
        <p>Сгенерировано {generated_at} · Сессия {session_id}</p>
        <p>Проект «Мамкин аналитик» · <a href="https://github.com/mamkin-analitik">GitHub Pages</a></p>
    </div>
</div>

</body>
</html>'''

    logger.info(f"HTML generation complete ({len(html)} bytes)")
    return html


# ==================== CLI & File Save ====================

def generate_html_to_file(data: dict, output_path: str) -> str:
    """
    Генерирует HTML и сохраняет в файл.

    Args:
        data: Данные сессии
        output_path: Путь для сохранения HTML

    Returns:
        Путь к сохранённому файлу
    """
    logger.info(f"Saving HTML → {output_path}")
    html = generate_html(data)

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    logger.info(f"HTML saved → {output_path} ({len(html)} bytes)")
    return output_path


def main():
    """Точка входа для CLI-вызова: html-gen.py <input_json> [output_html]."""
    if len(sys.argv) < 2:
        print("Usage: html-gen.py <input_json> [output_html]", file=sys.stderr)
        print("       html-gen.py --check       — проверка зависимостей", file=sys.stderr)
        print("       Если output_html не указан, выводит HTML в stdout", file=sys.stderr)
        sys.exit(1)

    if sys.argv[1] == '--check':
        print("✅ html-gen.py доступен (чистый Python, внешних зависимостей нет)")
        sys.exit(0)

    input_path = sys.argv[1]

    if not os.path.exists(input_path):
        print(f"❌ Файл не найден: {input_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка парсинга JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except IOError as e:
        print(f"❌ Ошибка чтения файла: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        if len(sys.argv) >= 3:
            output_path = sys.argv[2]
            result = generate_html_to_file(data, output_path)
            print(result)
        else:
            html = generate_html(data)
            print(html)
    except Exception as e:
        print(f"❌ Ошибка генерации HTML: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
