#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Рисуем 8 иллюстраций для презентации про Франциска I (SVG -> PNG через inkscape)."""
import os, subprocess

OUT = "/home/user1/.openclaw/workspace/francis1-assets"
os.makedirs(OUT, exist_ok=True)

NAVY = "#1B2A5B"; DARK = "#101A3A"; GOLD = "#C9A227"; LGOLD = "#E7C66B"
CREAM = "#F7F3EA"; RED = "#8C2B2B"; GREEN = "#2F6B46"; STEEL = "#6E7894"

S = {
    "fill": "none", "stroke_linejoin": "round", "stroke_linecap": "round",
}
HEAD = ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        'shape-rendering="geometricPrecision">')


def wrap(vb_w, vb_h, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vb_w} {vb_h}" '
            f'width="{vb_w}" height="{vb_h}">{body}</svg>')


def frame(w, h, inset=16, r=22):
    return (f'<rect x="{inset}" y="{inset}" width="{w-2*inset}" height="{h-2*inset}" rx="{r}" '
            f'fill="none" stroke="{GOLD}" stroke-width="4"/>')


def fleur(cx, cy, s=1.0, fill=GOLD, stroke=NAVY, sw=3):
    g = (f'<g transform="translate({cx},{cy}) scale({s})" fill="{fill}" stroke="{stroke}" '
         f'stroke-width="{sw}" stroke-linejoin="round">'
         '<path d="M0,-58 C13,-38 13,-16 0,-2 C-13,-16 -13,-38 0,-58 Z"/>'
         '<path d="M0,-6 C-8,-16 -26,-19 -34,-7 C-42,6 -30,21 -10,18 C-5,17 -1,13 0,10 Z"/>'
         '<path d="M0,-6 C8,-16 26,-19 34,-7 C42,6 30,21 10,18 C5,17 1,13 0,10 Z"/>'
         '<rect x="-20" y="10" width="40" height="11" rx="4"/>'
         '<path d="M0,20 C8,34 8,48 0,60 C-8,48 -8,34 0,20 Z"/>'
         '</g>')
    return g


def crown(cx, cy, s=1.0, fill=GOLD, stroke=NAVY, sw=5):
    return (f'<g transform="translate({cx},{cy}) scale({s})" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linejoin="round">'
            f'<path d="M-150,40 L-110,-60 L-45,10 L0,-80 L45,10 L110,-60 L150,40 Z" fill="{fill}"/>'
            f'<rect x="-155" y="40" width="310" height="52" rx="12" fill="{LGOLD}"/>'
            f'<circle cx="-70" cy="-20" r="11" fill="{NAVY}" stroke="none"/>'
            f'<circle cx="0" cy="-40" r="11" fill="{NAVY}" stroke="none"/>'
            f'<circle cx="70" cy="-20" r="11" fill="{NAVY}" stroke="none"/>'
            '</g>')


def chateau(x, y, s=1.0):
    """Стилизованный замок в 16:9-полосу."""
    return (f'<g transform="translate({x},{y}) scale({s})">'
            # central keep
            f'<rect x="180" y="70" width="160" height="150" fill="{NAVY}"/>'
            f'<path d="M150,70 L260,0 L370,70 Z" fill="{GOLD}"/>'
            f'<circle cx="260" cy="30" r="7" fill="{CREAM}"/>'
            # side towers
            f'<rect x="40" y="110" width="95" height="110" fill="{NAVY}"/>'
            f'<path d="M18,110 L87,44 L156,110 Z" fill="{GOLD}"/>'
            f'<rect x="385" y="110" width="95" height="110" fill="{NAVY}"/>'
            f'<path d="M363,110 L432,44 L501,110 Z" fill="{GOLD}"/>'
            # windows
            f'<rect x="242" y="120" width="34" height="52" rx="14" fill="{LGOLD}"/>'
            f'<rect x="70" y="150" width="24" height="40" rx="10" fill="{LGOLD}"/>'
            f'<rect x="415" y="150" width="24" height="40" rx="10" fill="{LGOLD}"/>'
            f'<rect x="150" y="190" width="22" height="30" rx="8" fill="{LGOLD}"/>'
            f'<rect x="348" y="190" width="22" height="30" rx="8" fill="{LGOLD}"/>'
            # flag
            f'<line x1="260" y1="0" x2="260" y2="-40" stroke="{NAVY}" stroke-width="5"/>'
            f'<path d="M260,-40 L330,-24 L260,-8 Z" fill="{RED}"/>'
            '</g>')


# ---------------------------------------------------------------- 1. медальон
medallion = wrap(700, 700,
    '<g stroke-linejoin="round" stroke-linecap="round">'
    f'<ellipse cx="350" cy="350" rx="330" ry="338" fill="{CREAM}" stroke="{GOLD}" stroke-width="10"/>'
    f'<ellipse cx="350" cy="350" rx="298" ry="306" fill="{NAVY}" stroke="{GOLD}" stroke-width="6"/>'
    + crown(350, 250, 1.0)
    + fleur(350, 470, 2.1)
    + '</g>')

# ------------------------------------------------------------------ 2. полоса
banner = wrap(2385, 300,
    '<g stroke-linejoin="round" stroke-linecap="round">'
    f'<rect x="40" y="250" width="2305" height="8" rx="4" fill="{GOLD}"/>'
    + chateau(120, 40, 1.0)
    + chateau(930, 70, 0.82)
    + chateau(1720, 40, 1.0)
    + f'<circle cx="1330" cy="70" r="34" fill="{LGOLD}"/>'
    + ''.join(f'<line x1="{1330+int(46*__import__("math").cos(a))}" y1="{70+int(46*__import__("math").sin(a))}" '
              f'x2="{1330+int(60*__import__("math").cos(a))}" y2="{70+int(60*__import__("math").sin(a))}" '
              f'stroke="{GOLD}" stroke-width="6"/>' for a in
              [i*3.14159/6 for i in range(12)])
    + '</g>')

# ------------------------------------------------------------- 3. битва/война
def sword(cx, cy, ang, s=1.0):
    return (f'<g transform="translate({cx},{cy}) rotate({ang}) scale({s})">'
            f'<rect x="-16" y="-330" width="32" height="470" rx="6" fill="{STEEL}" stroke="{NAVY}" stroke-width="4"/>'
            f'<path d="M-16,-330 L0,-410 L16,-330 Z" fill="{STEEL}" stroke="{NAVY}" stroke-width="4"/>'
            f'<rect x="-95" y="140" width="190" height="26" rx="10" fill="{GOLD}" stroke="{NAVY}" stroke-width="4"/>'
            f'<rect x="-12" y="166" width="24" height="90" rx="8" fill="{NAVY}"/>'
            f'<circle cx="0" cy="270" r="24" fill="{GOLD}" stroke="{NAVY}" stroke-width="4"/>'
            '</g>')

battle = wrap(700, 1080,
    frame(700, 1080)
    + crown(350, 130, 0.72)
    + sword(350, 500, 34)
    + sword(350, 500, -34)
    + f'<path d="M350,300 L560,352 C560,520 540,650 350,770 C160,650 140,520 140,352 Z" '
      f'fill="{NAVY}" stroke="{GOLD}" stroke-width="7" stroke-linejoin="round"/>'
    + fleur(350, 500, 1.5)
    # tents
    + f'<path d="M170,900 L250,800 L330,900 Z" fill="{CREAM}" stroke="{NAVY}" stroke-width="5"/>'
    + f'<path d="M370,900 L450,800 L530,900 Z" fill="{CREAM}" stroke="{NAVY}" stroke-width="5"/>'
    + f'<line x1="250" y1="800" x2="250" y2="900" stroke="{NAVY}" stroke-width="5"/>'
    + f'<line x1="450" y1="800" x2="450" y2="900" stroke="{NAVY}" stroke-width="5"/>'
    + f'<rect x="60" y="900" width="580" height="8" rx="4" fill="{GOLD}"/>')

# --------------------------------------------------------- 4. книга и перо (культура)
culture = wrap(700, 1080,
    frame(700, 1080)
    + crown(350, 130, 0.72)
    # open book
    + f'<path d="M130,590 L340,560 L340,760 L130,790 Z" fill="{CREAM}" stroke="{NAVY}" stroke-width="6"/>'
    + f'<path d="M570,590 L360,560 L360,760 L570,790 Z" fill="{CREAM}" stroke="{NAVY}" stroke-width="6"/>'
    + f'<line x1="350" y1="560" x2="350" y2="760" stroke="{NAVY}" stroke-width="6"/>'
    + ''.join(f'<line x1="165" y1="{615+i*26}" x2="315" y2="{603+i*26}" stroke="{GOLD}" stroke-width="4"/>' for i in range(5))
    + ''.join(f'<line x1="385" y1="{603+i*26}" x2="535" y2="{615+i*26}" stroke="{GOLD}" stroke-width="4"/>' for i in range(5))
    # quill
    + f'<g transform="translate(470,300) rotate(28)">'
      f'<ellipse cx="0" cy="-120" rx="34" ry="140" fill="{LGOLD}" stroke="{NAVY}" stroke-width="4"/>'
      f'<line x1="0" y1="20" x2="0" y2="210" stroke="{NAVY}" stroke-width="6"/>'
      f'<line x1="0" y1="-250" x2="0" y2="-40" stroke="{NAVY}" stroke-width="5"/>'
      f'</g>'
    + f'<rect x="440" y="820" width="80" height="70" rx="10" fill="{NAVY}" stroke="{GOLD}" stroke-width="5"/>'
    + f'<ellipse cx="480" cy="820" rx="48" ry="14" fill="{LGOLD}" stroke="{NAVY}" stroke-width="4"/>'
    # sparkles
    + fleur(160, 300, 0.9) + f'<circle cx="560" cy="260" r="9" fill="{GOLD}"/>')

# ------------------------------------------------------- 5. Витрувианский человек (Леонардо)
vitruvian = wrap(700, 1080,
    frame(700, 1080)
    + f'<rect x="120" y="310" width="460" height="460" fill="none" stroke="{GOLD}" stroke-width="5"/>'
    + f'<circle cx="350" cy="540" r="320" fill="none" stroke="{LGOLD}" stroke-width="5"/>'
    # figure (navy)
    + f'<g stroke="{NAVY}" stroke-width="13" fill="none" stroke-linecap="round">'
      f'<circle cx="350" cy="330" r="36" fill="{NAVY}" stroke="none"/>'
      f'<line x1="350" y1="366" x2="350" y2="620"/>'
      f'<line x1="200" y1="430" x2="500" y2="430"/>'      # arms out
      f'<line x1="205" y1="480" x2="120" y2="700"/>'      # arm pos2
      f'<line x1="495" y1="480" x2="580" y2="700"/>'
      f'<line x1="350" y1="620" x2="250" y2="830"/>'      # legs
      f'<line x1="350" y1="620" x2="450" y2="830"/>'
      f'<line x1="350" y1="620" x2="180" y2="760"/>'      # leg pos2
      f'<line x1="350" y1="620" x2="520" y2="760"/>'
      '</g>'
    + fleur(350, 980, 0.8))

# ------------------------------------------------------------------ 6. минусы (война/расходы)
minus = wrap(700, 1080,
    frame(700, 1080)
    # cannon
    + f'<g transform="translate(360,360) rotate(-18)">'
      f'<rect x="-40" y="-30" width="330" height="64" rx="20" fill="{STEEL}" stroke="{NAVY}" stroke-width="6"/>'
      f'<rect x="255" y="-40" width="34" height="84" rx="12" fill="{GOLD}" stroke="{NAVY}" stroke-width="5"/>'
      f'<rect x="-60" y="-14" width="40" height="34" rx="10" fill="{NAVY}"/>'
      f'</g>'
    + f'<path d="M180,360 L540,360 L500,470 L220,470 Z" fill="{NAVY}" stroke="{GOLD}" stroke-width="5"/>'
    + f'<circle cx="240" cy="480" r="52" fill="{CREAM}" stroke="{NAVY}" stroke-width="7"/>'
    + f'<circle cx="430" cy="480" r="52" fill="{CREAM}" stroke="{NAVY}" stroke-width="7"/>'
    + ''.join(f'<line x1="{240+44*__import__("math").cos(a)}" y1="{480+44*__import__("math").sin(a)}" '
              f'x2="{240-44*__import__("math").cos(a)}" y2="{480-44*__import__("math").sin(a)}" '
              f'stroke="{NAVY}" stroke-width="4"/>' for a in [0,1.047,2.094])
    + ''.join(f'<line x1="{430+44*__import__("math").cos(a)}" y1="{480+44*__import__("math").sin(a)}" '
              f'x2="{430-44*__import__("math").cos(a)}" y2="{480-44*__import__("math").sin(a)}" '
              f'stroke="{NAVY}" stroke-width="4"/>' for a in [0,1.047,2.094])
    # cannonballs
    + f'<circle cx="120" cy="880" r="34" fill="{NAVY}" stroke="{GOLD}" stroke-width="4"/>'
    + f'<circle cx="200" cy="905" r="34" fill="{NAVY}" stroke="{GOLD}" stroke-width="4"/>'
    + f'<circle cx="150" cy="950" r="34" fill="{NAVY}" stroke="{GOLD}" stroke-width="4"/>'
    # broken sword
    + f'<g transform="translate(500,800) rotate(30)">'
      f'<rect x="-13" y="-160" width="26" height="150" rx="6" fill="{STEEL}" stroke="{NAVY}" stroke-width="4"/>'
      f'<path d="M-13,0 L0,26 L13,0 Z" fill="{NAVY}"/>'
      f'<rect x="-60" y="60" width="120" height="20" rx="8" fill="{GOLD}" stroke="{NAVY}" stroke-width="4"/>'
      f'<rect x="-11" y="80" width="22" height="70" rx="8" fill="{NAVY}"/>'
      f'</g>'
    + f'<circle cx="600" cy="900" r="26" fill="{GOLD}" stroke="{NAVY}" stroke-width="4"/>'
    + f'<circle cx="330" cy="930" r="26" fill="{GOLD}" stroke="{NAVY}" stroke-width="4"/>')

# --------------------------------------------------------------- 7. весы (мнение)
balance = wrap(700, 1080,
    frame(700, 1080)
    + f'<g transform="translate(350,470) rotate(-13)">'
      f'<rect x="-235" y="-9" width="470" height="18" rx="8" fill="{GOLD}" stroke="{NAVY}" stroke-width="5"/>'
      f'<circle cx="-235" cy="0" r="14" fill="{NAVY}"/>'
      f'<circle cx="235" cy="0" r="14" fill="{NAVY}"/>'
      f'</g>'
    + f'<rect x="342" y="470" width="16" height="430" rx="6" fill="{NAVY}"/>'
    + f'<path d="M290,930 L410,930 L385,880 L315,880 Z" fill="{NAVY}" stroke="{GOLD}" stroke-width="5"/>'
    + f'<circle cx="350" cy="470" r="20" fill="{GOLD}" stroke="{NAVY}" stroke-width="5"/>'
    # left pan (culture, lower)
    + f'<line x1="128" y1="522" x2="60" y2="650" stroke="{NAVY}" stroke-width="4"/>'
    + f'<line x1="128" y1="522" x2="196" y2="650" stroke="{NAVY}" stroke-width="4"/>'
    + f'<path d="M40,650 L216,650 A88,88 0 0 1 40,650 Z" fill="{CREAM}" stroke="{NAVY}" stroke-width="5"/>'
    + crown(128, 560, 0.55)
    # right pan (war, higher)
    + f'<line x1="572" y1="416" x2="504" y2="540" stroke="{NAVY}" stroke-width="4"/>'
    + f'<line x1="572" y1="416" x2="640" y2="540" stroke="{NAVY}" stroke-width="4"/>'
    + f'<path d="M484,540 L660,540 A88,88 0 0 1 484,540 Z" fill="{CREAM}" stroke="{NAVY}" stroke-width="5"/>'
    + f'<g transform="translate(572,470) rotate(90)">'
      f'<rect x="-7" y="-95" width="14" height="140" rx="4" fill="{STEEL}" stroke="{NAVY}" stroke-width="3"/>'
      f'<rect x="-40" y="40" width="80" height="12" rx="5" fill="{GOLD}" stroke="{NAVY}" stroke-width="3"/>'
      f'<rect x="-6" y="52" width="12" height="40" rx="5" fill="{NAVY}"/>'
      f'</g>'
    + fleur(350, 990, 0.8))

# ------------------------------------------------------------- 8. башня-тюрьма
tower = wrap(700, 1080,
    frame(700, 1080)
    # crescent + stars
    + f'<path d="M560,150 A55,55 0 1 0 560,250 A44,44 0 1 1 560,150 Z" fill="{GOLD}"/>'
    + f'<circle cx="150" cy="150" r="8" fill="{GOLD}"/><circle cx="230" cy="110" r="6" fill="{GOLD}"/>'
    # tower body
    + f'<rect x="185" y="360" width="330" height="560" fill="{NAVY}"/>'
    + ''.join(f'<line x1="185" y1="{410+i*70}" x2="515" y2="{410+i*70}" stroke="{DARK}" stroke-width="3"/>' for i in range(7))
    # crenellations
    + ''.join(f'<rect x="{185+i*55}" y="320" width="34" height="44" fill="{NAVY}" stroke="{GOLD}" stroke-width="3"/>' for i in range(6))
    + f'<rect x="185" y="360" width="330" height="560" fill="none" stroke="{GOLD}" stroke-width="5"/>'
    # arched window with bars
    + f'<path d="M275,780 L275,620 A75,75 0 0 1 425,620 L425,780 Z" fill="{DARK}" stroke="{GOLD}" stroke-width="5"/>'
    + ''.join(f'<line x1="{275+i*37}" y1="560" x2="{275+i*37}" y2="780" stroke="{LGOLD}" stroke-width="6"/>' for i in range(5))
    + ''.join(f'<line x1="275" y1="{600+i*55}" x2="425" y2="{600+i*55}" stroke="{LGOLD}" stroke-width="6"/>' for i in range(4))
    # crown behind bars
    + f'<g transform="translate(350,690) scale(0.5)">'
      f'<path d="M-150,40 L-110,-60 L-45,10 L0,-80 L45,10 L110,-60 L150,40 Z" fill="{GOLD}"/>'
      f'<rect x="-155" y="40" width="310" height="52" rx="12" fill="{LGOLD}"/>'
      f'</g>'
    # chain
    + ''.join(f'<circle cx="{110+i*46}" cy="{900-i*30}" r="15" fill="none" stroke="{GOLD}" stroke-width="6"/>' for i in range(6))
    + f'<rect x="60" y="920" width="580" height="10" rx="5" fill="{GOLD}"/>')

files = {
    "f1-medallion.png": ("f1-medallion.svg", medallion, 700),
    "f1-banner.png":    ("f1-banner.svg", banner, 2385),
    "f1-battle.png":    ("f1-battle.svg", battle, 700),
    "f1-culture.png":   ("f1-culture.svg", culture, 700),
    "f1-vitruvian.png": ("f1-vitruvian.svg", vitruvian, 700),
    "f1-minus.png":     ("f1-minus.svg", minus, 700),
    "f1-balance.png":   ("f1-balance.svg", balance, 700),
    "f1-tower.png":     ("f1-tower.svg", tower, 700),
}

for png, (svg, content, w) in files.items():
    sp = os.path.join(OUT, svg)
    with open(sp, "w", encoding="utf-8") as f:
        f.write(content)
    pp = os.path.join(OUT, png)
    cmd = ["inkscape", sp, f"--export-filename={pp}", f"--export-width={w}"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    ok = os.path.exists(pp) and os.path.getsize(pp) > 500
    print(f"{'OK ' if ok else 'ERR'} {png} {os.path.getsize(pp) if ok else 0}B  {r.stderr.strip()[:80]}")
