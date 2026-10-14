#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Франциск I (1515–1547) — презентация в формате PowerPoint (.pptx) с иллюстрациями."""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

NAVY  = RGBColor(0x1B, 0x2A, 0x5B)
DARK  = RGBColor(0x10, 0x1A, 0x3A)
GOLD  = RGBColor(0xC9, 0xA2, 0x27)
LGOLD = RGBColor(0xE7, 0xC6, 0x6B)
CREAM = RGBColor(0xF7, 0xF3, 0xEA)
INK   = RGBColor(0x23, 0x26, 0x2E)
GREY  = RGBColor(0x7A, 0x71, 0x60)
RED   = RGBColor(0x8C, 0x2B, 0x2B)
GREEN = RGBColor(0x2F, 0x6B, 0x46)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
FONT  = "Arial"
IMG   = "/home/user1/.openclaw/workspace/francis1-assets/"

prs = Presentation()
prs.slide_width  = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]
SW, SH = 13.333, 7.5

# колонка под картинку: x=9.15, w=3.43, h=5.3 (соотношение 700x1080)
IMGX, IMGY, IMGW, IMGH = 9.15, 1.75, 3.43, 5.30
TXTW = 8.0   # ширина текстовой колонки, когда справа картинка


def slide():
    return prs.slides.add_slide(BLANK)


def rect(s, x, y, w, h, fill, line=None, shape=MSO_SHAPE.RECTANGLE, radius=None):
    sp = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    sp.fill.solid()
    sp.fill.fore_color.rgb = fill
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line
        sp.line.width = Pt(1)
    sp.shadow.inherit = False
    if radius is not None and shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        try:
            sp.adjustments[0] = radius
        except Exception:
            pass
    return sp


def pic(s, name, x, y, w, h):
    s.shapes.add_picture(IMG + name, Inches(x), Inches(y), Inches(w), Inches(h))


def textbox(s, x, y, w, h, anchor=MSO_ANCHOR.TOP):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Emu(0)
    tf.margin_top = tf.margin_bottom = Emu(0)
    return tf


def para(tf, text, size, color=INK, bold=False, italic=False, align=PP_ALIGN.LEFT,
         first=False, space_after=6, space_before=0, runs=None):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    p.space_after = Pt(space_after)
    p.space_before = Pt(space_before)
    if runs is None:
        runs = [(text, {})]
    for t, opts in runs:
        r = p.add_run()
        r.text = t
        r.font.name = FONT
        r.font.size = Pt(opts.get("size", size))
        r.font.bold = opts.get("bold", bold)
        r.font.italic = opts.get("italic", italic)
        r.font.color.rgb = opts.get("color", color)
    return p


def header(s, kicker, title):
    rect(s, 0, 0, SW, 1.25, NAVY)
    rect(s, 0, 1.25, SW, 0.055, GOLD)
    tf = textbox(s, 0.7, 0.16, 12, 1.0)
    para(tf, kicker.upper(), 11, LGOLD, bold=True, first=True, space_after=2)
    para(tf, title, 26, WHITE, bold=True, space_after=0)


def bg(s, color=CREAM):
    rect(s, 0, 0, SW, SH, color)


# ============================ 1. TITLE ============================
s = slide()
bg(s, DARK)
rect(s, 0, 0, 0.35, SH, GOLD)
pic(s, "f1-medallion.png", 9.05, 1.8, 3.7, 3.7)
tf = textbox(s, 1.1, 2.05, 7.4, 3.2)
para(tf, "Франциск I", 58, WHITE, bold=True, first=True, space_after=0)
para(tf, "1515–1547", 52, LGOLD, bold=True, space_after=10)
para(tf, "Король Франции из династии Валуа. «Король-рыцарь», покровитель искусств, "
         "полководец и вечный соперник императора Карла V.", 16, RGBColor(0xDF, 0xE3, 0xF2),
     space_after=0)
tag = rect(s, 1.1, 5.6, 4.4, 0.55, DARK, line=GOLD, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.5)
tf = tag.text_frame
tf.word_wrap = True
tf.vertical_anchor = MSO_ANCHOR.MIDDLE
para(tf, "Презентация по истории · 7 класс", 13, LGOLD, bold=True, align=PP_ALIGN.CENTER, first=True, space_after=0)

# ============================ 2. КТО ОН ============================
s = slide(); bg(s)
header(s, "Карточка героя", "Кто такой Франциск I")

def card(s, x, y, w, h, title, text):
    rect(s, x, y, w, h, WHITE, line=RGBColor(0xE3, 0xDC, 0xC9), shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06)
    rect(s, x, y, 0.09, h, GOLD)
    tf = textbox(s, x + 0.3, y + 0.22, w - 0.55, h - 0.4)
    para(tf, title, 16, NAVY, bold=True, first=True, space_after=4)
    para(tf, text, 13.5, INK, space_after=0)

card(s, 0.7, 1.7, 5.9, 1.7, "Основные данные",
     "Родился 12 сентября 1494 в Коньяке, умер 31 марта 1547 в Рамбуйе. Династия Валуа. "
     "На троне — с 1515 по 1547 год (32 года).")
card(s, 0.7, 3.6, 5.9, 1.7, "Как получил власть",
     "Наследовал Людовику XII, женившись на его дочери Клод Французской. "
     "Коронация прошла в Реймсе в январе 1515 года.")
card(s, 6.85, 1.7, 5.8, 1.7, "Прозвища и образ",
     "«Король-рыцарь» и «Отец и восстановитель словесности» (Père et restaurateur des lettres) "
     "— за любовь к наукам и искусствам.")
card(s, 6.85, 3.6, 5.8, 1.7, "Главный враг",
     "Император Священной Римской империи Карл V Габсбург. Их борьба за первенство в Европе "
     "длилась почти всё правление Франциска.")
pic(s, "f1-banner.png", 0.7, 5.55, 11.93, 1.5)

# ============================ 3-4. TIMELINE ============================
def timeline(kicker, title, rows, image):
    s = slide()
    bg(s)
    header(s, kicker, title)
    y = 1.8
    rowh = (SH - 1.95) / len(rows)
    for yr, kind, text in rows:
        color = GREEN if kind == "pos" else RED if kind == "neg" else NAVY
        pill = rect(s, 0.7, y + 0.05, 1.45, 0.5, color, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.5)
        ptf = pill.text_frame; ptf.word_wrap = False
        ptf.vertical_anchor = MSO_ANCHOR.MIDDLE
        para(ptf, yr, 14, WHITE, bold=True, align=PP_ALIGN.CENTER, first=True, space_after=0)
        tf = textbox(s, 2.4, y, 6.35, rowh - 0.12)
        para(tf, text, 12.5, INK, first=True, space_after=0)
        y += rowh
    pic(s, image, IMGX, IMGY, IMGW, IMGH)

timeline("Хронология · часть 1", "Годы и события: взлёт и плен (1515–1529)", [
    ("1515", "pos", "Битва при Мариньяно. Разгром швейцарцев, Франция возвращает Милан — блестящее начало правления."),
    ("1519", "neu", "Выборы императора. Франциск проигрывает борьбу за корону Священной Римской империи Карлу V."),
    ("1520", "neu", "«Поле золотой парчи». Роскошная встреча с королём Англии Генрихом VIII — попытка найти союзника."),
    ("1525", "neg", "Битва при Павии. Тяжёлое поражение; Франциск попадает в плен к Карлу V."),
    ("1526", "neg", "Мадридский договор. В плену отрекается от Италии и Бургундии, потом отказывается от обещаний."),
    ("1529", "pos", "Камбрейский мир. Мирный договор («мир дам»), который готовили матери обеих сторон."),
], "f1-battle.png")

timeline("Хронология · часть 2", "Годы и события: реформатор и «отец словесности» (1530–1547)", [
    ("1530", "pos", "Коллеж де Франс. Основан как «Коллеж королевских лекторов» — центр новых наук."),
    ("1534", "neg", "«Дело плакатов». Прокламации против католической мессы → волна казней протестантов."),
    ("1539", "pos", "Ордонанс Виллер-Котре. Французский язык вместо латыни в судах и документах."),
    ("1544", "neu", "Крепийский мир. Очередной мир с Карлом V; войны за Италию так и не принесли победы."),
    ("1547", "neu", "Смерть короля. Умер 31 марта; трон наследует его сын Генрих II."),
], "f1-culture.png")

# ============================ 5-6. ПЛЮСЫ / МИНУСЫ ============================
def bullet_slide(kicker, title, items, accent, image):
    s = slide()
    bg(s)
    header(s, kicker, title)
    tf = textbox(s, 0.85, 1.75, 7.9, SH - 2.0)
    first = True
    for b, rest in items:
        para(tf, "", 14, first=first, space_after=11)
        p = tf.paragraphs[-1]
        r = p.add_run(); r.text = "●  "
        r.font.name = FONT; r.font.size = Pt(13.5); r.font.color.rgb = accent; r.font.bold = True
        r2 = p.add_run(); r2.text = b
        r2.font.name = FONT; r2.font.size = Pt(14); r2.font.bold = True; r2.font.color.rgb = NAVY
        r3 = p.add_run(); r3.text = " " + rest
        r3.font.name = FONT; r3.font.size = Pt(14); r3.font.color.rgb = INK
        first = False
    pic(s, image, IMGX, IMGY, IMGW, IMGH)
    return s

bullet_slide("Оценка · плюсы", "Что Франциск I сделал хорошо", [
    ("Покровитель искусств.", "В 1516 году пригласил во Францию Леонардо да Винчи; приобрёл «Мону Лизу»."),
    ("Расцвет Ренессанса.", "Строил и перестраивал замки Шамбор и Фонтенбло, собрал коллекции итальянских мастеров."),
    ("Наука и образование.", "Основал Коллеж де Франс (1530), развивал книгопечатание и королевскую библиотеку."),
    ("Язык.", "Ордонанс 1539 года сделал французский официальным языком делопроизводства."),
    ("Сильная власть.", "Укрепил королевскую армию и центральную власть, ослабил сепаратизм знати."),
], GREEN, "f1-vitruvian.png")

bullet_slide("Оценка · минусы", "В чём Франциск I ошибался", [
    ("Бесконечные войны.", "Соперничество с Карлом V истощило казну и разорило страну."),
    ("Плен и позор.", "В 1525 году попал в плен при Павии, подписал унизительный Мадридский договор и нарушил слово."),
    ("Италия потеряна.", "Милан, добытый в 1515 году, в итоге вернуть не удалось."),
    ("Религиозные репрессии.", "После «дела плакатов» (1534) начались казни протестантов."),
    ("Расточительность.", "Роскошь двора и дорогие войны требовали всё новых налогов."),
], RED, "f1-minus.png")

# ============================ 7. МОЁ МНЕНИЕ ============================
s = slide(); bg(s)
header(s, "Субъективно", "Моё мнение")
tf = textbox(s, 0.85, 1.75, 7.9, 1.1)
para(tf, "«Франциск I — двойственный король: блестящий меценат и заурядный полководец».", 19,
     NAVY, italic=True, first=True, space_after=0)
tf = textbox(s, 0.85, 3.05, 7.9, 2.5)
para(tf, "Он больше выиграл на поприще культуры, чем на поле боя. Именно при нём Франция стала "
         "центром Северного Ренессанса, а французский язык получил статус государственного. "
         "Военные же амбиции почти всегда заканчивались пленом, разорением казны или невыгодным миром.",
     14.5, INK, first=True, space_after=12)
para(tf, "Если бы Франциск направил часть военных расходов на просвещение и экономику, страна могла бы "
         "окрепнуть быстрее. Но и без его меценатства не было бы ни Шамбора, ни Коллеж де Франс.",
     14.5, INK, space_after=0)
vh = rect(s, 0.85, 5.75, 7.9, 0.62, GOLD, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.25)
vtf = vh.text_frame; vtf.vertical_anchor = MSO_ANCHOR.MIDDLE; vtf.word_wrap = True
para(vtf, "Итог: великий культурный король и средний полководец", 14, NAVY, bold=True,
     align=PP_ALIGN.CENTER, first=True, space_after=0)
pic(s, "f1-balance.png", IMGX, IMGY, IMGW, IMGH)

# ============================ 8. ШОКИРУЮЩИЙ ФАКТ ============================
s = slide(); bg(s)
header(s, "Шокирующий факт", "«Всё потеряно, кроме чести»")
box = rect(s, 0.85, 1.75, 8.05, 3.75, DARK, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.04)
tf = textbox(s, 1.3, 2.05, 7.15, 3.1)
para(tf, "Король в плену", 19, LGOLD, bold=True, first=True, space_after=7)
para(tf, "В 1525 году под Павией армия Франции была разбита, а сам король попал в плен и провёл больше "
         "года в испанском плену. Узнав о разгроме, он написал матери знаменитую фразу:",
     13.5, WHITE, space_after=9)
para(tf, "«Мадам, всё потеряно, кроме чести».", 21, LGOLD, bold=True, italic=True, space_after=9)
para(tf, "Чтобы выйти на свободу, Франциск подписал Мадридский договор с отказом от Италии и Бургундии — "
         "а оказавшись на воле, объявил, что подписал его по принуждению, и продолжил войну.",
     13.5, WHITE, space_after=0)
tf = textbox(s, 0.85, 5.7, 8.05, 1.4)
para(tf, "Бонус-факты: по преданию, Леонардо да Винчи умер в 1519 году на руках у Франциска. "
         "А купленную «Мону Лизу» король держал… в своей ванной комнате во дворце Фонтенбло.",
     12, GREY, first=True, space_after=0)
pic(s, "f1-tower.png", IMGX, IMGY, IMGW, IMGH)

out = "/home/user1/.openclaw/workspace/francis1-prezentaciya.pptx"
prs.save(out)
print("saved:", out, "slides:", len(prs.slides._sldIdLst))
