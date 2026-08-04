#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "pdf-presentation-designer", "references"))

from pathlib import Path
from weasyprint import HTML, CSS
from icons import icon as icon_fn

REF = Path(__file__).parent / "pdf-presentation-designer" / "references"

HTML_STR = r"""<!DOCTYPE html>
<html lang="ru" data-theme="light">
<head>
<meta charset="utf-8">
<style>
  @page { size: 1280px 920px; margin: 0; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: var(--bg-primary);
    color: var(--text-secondary);
    width: 1280px;
  }
  .page {
    width: 1280px; height: 920px;
    padding: 32px 40px 28px 40px;
    position: relative; overflow: hidden;
    display: flex; flex-direction: column;
    font-size: 10.5px; line-height: 1.4;
  }
  .page::before {
    content: ''; position: absolute;
    top: -60px; right: -60px;
    width: 280px; height: 280px;
    border-radius: 50%;
    background: var(--accent-glow);
    filter: blur(50px); pointer-events: none;
  }
  h1 { font-size: 24px; font-weight: 700; color: var(--text-primary); margin: 0 0 2px 0; }
  .subtitle { font-size: 14px; font-weight: 300; color: var(--accent-light); margin-bottom: 14px; }
  .decor { width: 60px; height: 2px; background: var(--decor-line); border-radius: 2px; margin-bottom: 16px; }
  h2 { font-size: 13px; font-weight: 700; color: var(--accent-light); margin: 0 0 6px 0; text-transform: uppercase; }
  .grid-2 { display: flex; flex-direction: row; }
  .col { flex: 1; }
  .section { margin-bottom: 14px; position: relative; z-index: 1; }

  /* Карточка сценария */
  .card-row {
    display: flex; align-items: flex-start;
    background: var(--bg-card); border-radius: var(--radius-sm);
    padding: 8px 10px; margin-bottom: 5px;
    box-shadow: var(--shadow-sm);
    border-left: 3px solid var(--accent);
  }
  .card-num {
    width: 22px; height: 22px; border-radius: 50%; background: var(--accent);
    display: flex; align-items: center; justify-content: center;
    font-size: 10px; font-weight: 700; color: #fff;
    flex-shrink: 0; margin-right: 8px; margin-top: 1px;
  }
  .card-body { flex: 1; }
  .card-title { font-weight: 700; color: var(--text-primary); font-size: 10.5px; margin-bottom: 1px; }
  .card-desc { color: var(--text-muted); font-size: 9px; line-height: 1.35; }

  /* Барьер */
  .barrier {
    background: var(--bg-card); border-radius: var(--radius-sm);
    padding: 10px; margin-bottom: 6px;
    box-shadow: var(--shadow-sm);
    display: flex; align-items: flex-start;
  }
  .barrier-icon {
    width: 28px; height: 28px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0; margin-right: 10px;
  }
  .barrier-red { background: var(--danger-bg); }
  .barrier-yellow { background: var(--warning-bg); }
  .barrier-blue { background: var(--accent-glow); }

  /* Шаги */
  .step {
    background: var(--bg-card); border-radius: var(--radius-sm);
    padding: 10px; margin-bottom: 5px;
    box-shadow: var(--shadow-sm);
    display: flex; align-items: flex-start;
  }
  .step-num {
    width: 24px; height: 24px; border-radius: 50%; background: var(--accent);
    display: flex; align-items: center; justify-content: center;
    font-size: 11px; font-weight: 700; color: #fff;
    flex-shrink: 0; margin-right: 10px;
  }
  .step-text { font-size: 10px; color: var(--text-secondary); line-height: 1.4; }
  .step-text strong { color: var(--text-primary); }

  .footer {
    border-top: 1px solid var(--border); padding-top: 8px;
    font-size: 8px; color: var(--text-muted);
    display: flex; justify-content: space-between;
    margin-top: auto;
  }
  .tag {
    display: inline-block; background: var(--accent); color: #fff;
    border-radius: 3px; padding: 1px 5px; font-size: 7px; font-weight: 600;
  }
</style>
<link rel="stylesheet" href="THEME_CSS_PATH">
</head>
<body>
<div class="page">
  <div>
    <h1>COMPUTER VISION В РИТЕЙЛЕ</h1>
    <div class="subtitle">Сценарии автоматизации для розничных сетей всех форматов</div>
    <div class="decor"></div>
  </div>

  <div class="grid-2">
    <!-- Левая: сценарии -->
    <div class="col" style="margin-right: 18px;">
      <div class="section">
        <h2>ПРИОРИТЕТНЫЕ СЦЕНАРИИ</h2>

        <div class="card-row">
          <div class="card-num">1</div>
          <div class="card-body">
            <div class="card-title">Контроль полок</div>
            <div class="card-desc">Робот-уборщик с камерами сканирует полки: пустоты, нарушения планограммы. Попутный сбор данных для нейромаркетинга.</div>
          </div>
        </div>

        <div class="card-row">
          <div class="card-num">2</div>
          <div class="card-body">
            <div class="card-title">Контроль ценников</div>
            <div class="card-desc">Распознавание текста на ценниках (OCR) → сверка с базой → сигнал о расхождении.</div>
          </div>
        </div>

        <div class="card-row">
          <div class="card-num">3</div>
          <div class="card-body">
            <div class="card-title">Зона свежести и скоропорт</div>
            <div class="card-desc">Камеры у рыбных и мясных прилавков отслеживают время нахождения продукта в зоне и качество льда. Автооповещение персонала.</div>
          </div>
        </div>

        <div class="card-row">
          <div class="card-num">4</div>
          <div class="card-body">
            <div class="card-title">Эффективность персонала</div>
            <div class="card-desc">Трекинг перемещений и времени выполнения задач → объективная оценка индивидуальной производительности.</div>
          </div>
        </div>

        <div class="card-row">
          <div class="card-num">5</div>
          <div class="card-body">
            <div class="card-title">Распределение потока по кассирам</div>
            <div class="card-desc">Анализ входящего потока покупателей → проактивное прогнозирование загрузки касс. Альтернатива дорогостоящему подсчёту очередей.</div>
          </div>
        </div>

        <div class="card-row">
          <div class="card-num">6</div>
          <div class="card-body">
            <div class="card-title">Эмоции покупателей</div>
            <div class="card-desc">Камера терминала Сбера фиксирует эмоции с привязкой к чеку и кассиру. Контроль качества обслуживания.</div>
          </div>
        </div>

        <div class="card-row">
          <div class="card-num">7</div>
          <div class="card-body">
            <div class="card-title">Антикража</div>
            <div class="card-desc">Поведенческий анализ траекторий и жестов → выявление подозрительных сценариев хищения.</div>
          </div>
        </div>

        <div class="card-row">
          <div class="card-num">8</div>
          <div class="card-body">
            <div class="card-title">Антифрод на кассе</div>
            <div class="card-desc">Видеосопоставление сканируемых товаров с фискальными данными: непробитие, подмена, сговор.</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Правая: барьеры, экономика, шаги -->
    <div class="col">
      <div class="section">
        <h2>КЛЮЧЕВОЙ БАРЬЕР</h2>

        <div class="barrier">
          <div class="barrier-icon barrier-red">
            <span style="font-size: 14px;">$$</span>
          </div>
          <div>
            <div style="font-weight: 700; color: var(--text-primary); font-size: 10.5px; margin-bottom: 3px;">Высокая стоимость — главный блокер</div>
            <div style="font-size: 9px; color: var(--text-muted); line-height: 1.4;">Технология воспринимается ритейлом как дорогая. Основные драйверы стоимости: камеры и ИИ-аналитика.</div>
          </div>
        </div>

        <div class="barrier">
          <div class="barrier-icon barrier-yellow">
            <span style="font-size: 14px;">⚡</span>
          </div>
          <div>
            <div style="font-weight: 700; color: var(--text-primary); font-size: 10.5px; margin-bottom: 3px;">Цена ошибки при полной автоматизации</div>
            <div style="font-size: 9px; color: var(--text-muted); line-height: 1.4;">При отказе от человека в пользу ИТ-решения требования к точности возрастают до 100% → усложнение алгоритмов → рост стоимости.</div>
          </div>
        </div>

        <div class="barrier">
          <div class="barrier-icon barrier-blue">
            <span style="font-size: 14px;">🔄</span>
          </div>
          <div>
            <div style="font-weight: 700; color: var(--text-primary); font-size: 10.5px; margin-bottom: 3px;">Попытки внедрения продолжаются</div>
            <div style="font-size: 9px; color: var(--text-muted); line-height: 1.4;">Несмотря на барьеры, пилотные проекты запускаются. Ритейлеры ищут сценарии с быстрой окупаемостью.</div>
          </div>
        </div>
      </div>

      <div class="section">
        <h2>ЭКОНОМИКА РЕШЕНИЯ</h2>
        <div style="background: var(--bg-card); border-radius: var(--radius-sm); padding: 12px; box-shadow: var(--shadow-sm);">
          <div style="display: flex; justify-content: space-between; font-size: 9px; margin-bottom: 6px;">
            <span style="color: var(--text-muted);">Стоимость камер</span>
            <span style="color: var(--danger); font-weight: 700;">Высокая</span>
          </div>
          <div style="display: flex; justify-content: space-between; font-size: 9px; margin-bottom: 6px;">
            <span style="color: var(--text-muted);">Стоимость ИИ-аналитики</span>
            <span style="color: var(--danger); font-weight: 700;">Высокая</span>
          </div>
          <div style="display: flex; justify-content: space-between; font-size: 9px; margin-bottom: 6px;">
            <span style="color: var(--text-muted);">100% автоматизация (без человека)</span>
            <span style="color: var(--warning); font-weight: 700;">Кратно дороже</span>
          </div>
          <div style="display: flex; justify-content: space-between; font-size: 9px;">
            <span style="color: var(--text-muted);">Гибридный подход (человек + CV)</span>
            <span style="color: var(--success); font-weight: 700;">Оптимален</span>
          </div>
        </div>
      </div>

      <div class="section">
        <h2>ДАЛЬНЕЙШИЕ ШАГИ</h2>

        <div class="step">
          <div class="step-num">1</div>
          <div class="step-text">
            <strong>Встречи с ритейлом.</strong> Совместно с Дивизионом «Эквайринг» (А. Шумский) провести серию встреч с представителями розничных сетей. Оценить потребности и бюджетные ожидания. Договориться о пилоте с 1–2 сетями.
          </div>
        </div>

        <div class="step">
          <div class="step-num">2</div>
          <div class="step-text">
            <strong>Определение сценариев.</strong> По итогам встреч выбрать приоритетные сценарии для пилотного проекта. Сформировать SMART-описание целей пилота.
          </div>
        </div>

        <div class="step">
          <div class="step-num">3</div>
          <div class="step-text">
            <strong>Запуск пилота.</strong> Реализация пилотного проекта на площадке ритейлера-партнёра. Замер KPI, оценка окупаемости, масштабирование.
          </div>
        </div>
      </div>
    </div>
  </div>

  <div class="footer">
    <span>Computer Vision в ритейле | Для внутреннего обсуждения</span>
    <span>Сбер · Дивизион «Биометрия» + Дивизион «Эквайринг»</span>
  </div>
</div>
</body>
</html>"""

# Внедряем theme.css инлайн
theme_css = (REF / "theme.css").read_text()
css_text = theme_css.replace(":root,", ":root,")  # noop, just ensure light theme applies

html = HTML(string=HTML_STR.replace("THEME_CSS_PATH", "data:text/css;base64,__PLACEHOLDER__"))

# WeasyPrint не умеет инлайн data: в link, поэтому соберём один CSS
full_html = HTML_STR.replace('<link rel="stylesheet" href="THEME_CSS_PATH">', f"<style>{theme_css}</style>")

out = os.path.expanduser("~/.openclaw/workspace/CV_Retail_OnePager.pdf")
HTML(string=full_html).write_pdf(out)
print(f"✅ One-pager сохранён: {out}")
