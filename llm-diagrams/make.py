# -*- coding: utf-8 -*-
import html

FONT = "DejaVu Sans, Liberation Sans, sans-serif"

def esc(t): return html.escape(t, quote=True)

def text(x, y, t, size=14, weight="normal", anchor="start", fill="#172033", opacity=1):
    return (f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
            f'font-weight="{weight}" text-anchor="{anchor}" fill="{fill}" opacity="{opacity}">{esc(t)}</text>')

def box(x, y, w, h, fill="#e2e8f0", stroke="#64748b", rx=10, sw=1, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{sw}"{d}/>')

def arrow(x1, y1, x2, y2, color="#64748b", sw=2, marker="arrow"):
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{sw}" '
            f'marker-end="url(#{marker})"/>')

# ---------------------------------------------------------------- DIAGRAM A
W, H = 1800, 800
s = []
s.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
s.append('<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
         '<path d="M0,0 L10,5 L0,10 z" fill="#64748b"/></marker></defs>')
s.append(box(0, 0, W, H, fill="#f8fafc", stroke="none", rx=0))

s.append(text(60, 66, "Как появились большие языковые модели (LLM)", size=34, weight="bold"))
s.append(text(60, 100, "От идеи «искусственного нейрона» до чат-помощников: 80 лет истории", size=18, fill="#5b6475"))

# roots chips
roots = ["Нейробиология (как работает мозг)", "Логика и теория вычислений",
         "Теория вероятностей и статистика", "Лингвистика (язык как система)",
         "Теория информации"]
s.append(text(60, 152, "Пять корней, из которых выросла идея:", size=16, weight="bold"))
cx = 60
for r in roots:
    wd = 22 + len(r) * 8.6
    s.append(box(cx, 166, wd, 36, fill="#fde68a", rx=18))
    s.append(text(cx + wd/2, 190, r, size=14, anchor="middle", fill="#3f2d05"))
    cx += wd + 14

s.append(text(60, 226, "Дорога во времени", size=20, weight="bold"))
s.append('<line x1="90" y1="400" x2="1706" y2="400" stroke="#94a3b8" stroke-width="4"/>')

miles = [
 ("1943", "Модель нейрона", ["Маккаллок и Питтс:", "первая формула «клетки мозга»"]),
 ("1950", "Тест Тьюринга", ["Вопрос: «может ли", "машина думать?»"]),
 ("1957", "Перцептрон", ["Розенблатт: первая", "обучаемая нейросеть"]),
 ("1969", "«Зима ИИ»", ["Минский и Пейперт показали", "пределы перцептрона"]),
 ("1986", "Обратное распространение", ["Сети снова учатся,", "но данных и мощности мало"]),
 ("1997", "LSTM · Deep Blue", ["Память для последовательностей;", "компьютер бьёт Каспарова"]),
 ("2006", "Глубокое обучение", ["Хинтон: много слоёв", "дают прорыв в качестве"]),
 ("2013", "Слова-векторы", ["word2vec: текст", "превращают в числа"]),
 ("2017", "ТРАНСФОРМЕР", ["«Attention is All You Need»", "— главный перелом"]),
 ("2018", "GPT-1 и BERT", ["Предобучение на текстах", "всего интернета"]),
 ("2020", "GPT-3", ["175 млрд параметров:", "пишет почти как человек"]),
 ("2022", "ChatGPT + RLHF", ["Обучение на похвале людей;", "ИИ выходит к массам"]),
 ("2023-24", "GPT-4, LLaMA", ["Мультимодальность, открытые", "модели, гонка компаний"]),
 ("2025-26", "Рассуждающие модели", ["LLM «думают» по шагам", "и работают как агенты"]),
]
xc0, step = 118, 118
for i, (yr, tt, lines) in enumerate(miles):
    x = xc0 + i * step
    up = (i % 2 == 0)
    hi = tt == "ТРАНСФОРМЕР"
    s.append(f'<circle cx="{x}" cy="400" r="9" fill="{"#4338ca" if hi else "#64748b"}"/>')
    s.append(f'<line x1="{x}" y1="{"382" if up else "418"}" x2="{x}" y2="{"336" if up else "500"}" stroke="#94a3b8" stroke-width="1.5"/>')
    cy = 240 if up else 508
    fill = "#c7d2fe" if hi else "#e2e8f0"
    s.append(box(x - 108, cy, 216, 92, fill=fill, rx=10))
    s.append(text(x, cy + 26, yr, size=17, weight="bold", anchor="middle",
                  fill="#312e81" if hi else "#172033"))
    s.append(text(x, cy + 46, tt, size=13, weight="bold", anchor="middle",
                  fill="#312e81" if hi else "#172033"))
    for j, ln in enumerate(lines):
        s.append(text(x, cy + 64 + j * 15, ln, size=11.5, anchor="middle", fill="#5b6475"))

# bottom: three pillars
s.append(text(60, 676, "Что сделало LLM возможными: три условия встретились вместе", size=20, weight="bold"))
pill = [("Огромные текстовые данные", "интернет, книги, код —", "#bfdbfe"),
        ("Мощные видеокарты (GPU)", "миллиарды вычислений", "#99f6e4"),
        ("Алгоритмы: Transformer", "и обучение на подсказках", "#c7d2fe")]
px = 60
for i, (a, b, c) in enumerate(pill):
    s.append(box(px, 700, 420, 72, fill=c, rx=12))
    s.append(text(px + 210, 730, a, size=16, weight="bold", anchor="middle"))
    s.append(text(px + 210, 754, b, size=13.5, anchor="middle", fill="#5b6475"))
    s.append(arrow(px + 424, 736, px + 468, 736))
    px += 472
s.append(box(1500, 700, 240, 72, fill="#312e81", stroke="#312e81", rx=12))
s.append(text(1620, 732, "LLM", size=24, weight="bold", anchor="middle", fill="#ffffff"))
s.append(text(1620, 754, "языковая модель", size=13, anchor="middle", fill="#c7d2fe"))
s.append('</svg>')
open("/home/user1/.openclaw/workspace/llm-diagrams/llm-history.svg", "w").write("\n".join(s))

# ---------------------------------------------------------------- DIAGRAM B
W2, H2 = 1500, 760
t = []
t.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W2}" height="{H2}" viewBox="0 0 {W2} {H2}">')
t.append(box(0, 0, W2, H2, fill="#f8fafc", stroke="none", rx=0))
t.append(text(60, 66, "Топ-10 LLM в сентябре 2026 года", size=32, weight="bold"))
t.append(text(60, 100, "Самые сильные модели каждой компании по индексу интеллекта Artificial Analysis", size=17, fill="#5b6475"))

rows = [
 ("Claude Opus 5.5", "Anthropic · США", 58),
 ("GPT-6 Astra", "OpenAI · США", 53),
 ("Muse Spark 1.3", "Meta · США", 48),
 ("Grok 4.7", "xAI · США", 46),
 ("MiMo-V2.6-Pro", "Xiaomi · Китай", 46),
 ("Qwen3.8 Max", "Alibaba · Китай", 45),
 ("GLM-5.3", "Z.ai (Zhipu) · Китай", 45),
 ("Kimi K3", "Moonshot AI · Китай", 44),
 ("Gemini 3.8 Flash", "Google · США", 41),
 ("DeepSeek V4.1 Flash", "DeepSeek · Китай", 39),
]
x0, xmax = 480, 1330
maxtot = 60.0
y = 150
for i, (name, comp, val) in enumerate(rows):
    t.append(text(60, y + 20, f"{i+1}.", size=17, weight="bold", fill="#5b6475"))
    t.append(text(100, y + 20, name, size=18, weight="bold"))
    t.append(text(100, y + 40, comp, size=12.5, fill="#5b6475"))
    col = "#312e81" if i < 3 else ("#4338ca" if i < 6 else "#818cf8")
    wd = (xmax - x0) * val / maxtot
    t.append(box(x0, y, wd, 30, fill=col, stroke=col, rx=6))
    t.append(text(x0 + wd + 12, y + 22, str(val), size=16, weight="bold", fill="#172033"))
    y += 55
t.append('<line x1="480" y1="150" x2="480" y2="700" stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="4 4"/>')
t.append(text(60, 730, "Источник: Artificial Analysis Intelligence Index, 25.09.2026. Рейтинг меняется каждую неделю — это снимок на сегодня.", size=12.5, fill="#5b6475"))
t.append(text(60, 748, "Максимум шкалы — 60 баллов.", size=12.5, fill="#5b6475"))
t.append('</svg>')
open("/home/user1/.openclaw/workspace/llm-diagrams/llm-top10.svg", "w").write("\n".join(t))
print("ok")
