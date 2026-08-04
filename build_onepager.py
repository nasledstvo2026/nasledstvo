#!/usr/bin/env python3
"""One-pager: Отдел сопровождения дирекции радиоэлектроники."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "pdf-presentation-designer", "references"))

from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML, CSS
from icons import icon as _icon_fn

_REF_DIR = Path(__file__).parent / "pdf-presentation-designer" / "references"
TEMPLATES_DIR = _REF_DIR / "templates"

env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)
env.globals["icon"] = _icon_fn

css = CSS(filename=str(_REF_DIR / "theme.css"))

template = env.get_template("onepager.html.j2")
html_str = template.render(contacts_footer="📧 email@company.ru  📞 +7 (XXX) XXX-XX-XX  📍 Москва")

# Добавляем data-theme
html_str = html_str.replace('<html lang="ru">', '<html lang="ru" data-theme="light">', 1)

out = os.path.expanduser("~/.openclaw/workspace/Отдел_сопровождения_РЭ_onepager.pdf")
HTML(string=html_str).write_pdf(out, stylesheets=[css])
print(f"✅ One-pager сохранён: {out}")
