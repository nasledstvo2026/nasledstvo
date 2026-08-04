"""
pdf-presentation-designer — PresentationBuilder
Собирает PDF-презентацию из Jinja2-шаблонов и рендерит через WeasyPrint.
"""

import os
import sys
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML, CSS

# Подключаем модуль иконок из той же папки references
_REF_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(_REF_DIR))
from icons import icon as _icon_fn


class Presentation:
    """Строитель PDF-презентаций на HTML/CSS/Jinja2.

    Использование:
        pres = Presentation(theme="dark")
        pres.add_title(...)
        pres.add_mission(...)
        pres.add_kpi_dashboard(...)
        pres.save("output.pdf")
    """

    THEMES = {
        "dark": "theme.css",
        "light": "theme.css",   # та же таблица стилей, переключается data-theme
        "accent": "theme.css",
    }

    def __init__(self, theme: str = "dark"):
        if theme not in self.THEMES:
            raise ValueError(f"Unknown theme '{theme}'. Choose: {list(self.THEMES)}")
        self.theme = theme
        self.slides: list[dict] = []
        self._page_num = 0

        # Jinja2
        templates_dir = _REF_DIR / "templates"
        self._env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )
        self._env.globals["icon"] = _icon_fn

        # CSS
        css_path = _REF_DIR / self.THEMES[theme]
        if not css_path.exists():
            raise FileNotFoundError(f"Theme file not found: {css_path}")
        self._css = CSS(filename=str(css_path))

    def _add_slide(self, template_name: str, **kwargs):
        """Регистрирует слайд: шаблон + данные."""
        self._page_num += 1
        margin = "48px"
        self.slides.append({
            "template": template_name,
            "data": {**kwargs, "page_num": f"{self._page_num}", "margin": margin},
        })

    # ── Слайды ──────────────────────────────────────────────────

    def add_title(self, title: str, subtitle: str, description: str = "",
                  classification: str = "Конфиденциально",
                  footer: str = ""):
        """Титульный слайд."""
        self._add_slide("title.html.j2",
                        title=title, subtitle=subtitle, description=description,
                        classification=classification, footer=footer)

    def add_mission(self, title: str, values: list[dict] = None, text: str = "",
                    footer: str = ""):
        """Слайд миссии с опциональными карточками ценностей.

        values: [{"icon": "shield", "label": "СКОРОСТЬ", "text": "..."}, ...]
        """
        self._add_slide("mission.html.j2",
                        title=title, values=values or [], text=text, footer=footer)

    def add_process(self, title: str, steps: list[dict], details: list[str] = None,
                    footer: str = ""):
        """Процесс: N шагов с иконками и номерами.

        steps: [{"icon": "shopping-cart", "label": "Заявка", "description": "..."}, ...]
        """
        self._add_slide("process.html.j2",
                        title=title, steps=steps, details=details or [], footer=footer)

    def add_timeline(self, title: str, events: list[dict], footer: str = ""):
        """Вертикальный таймлайн.

        events: [{"icon": "ticket", "label": "Этап", "description": "..."}, ...]
        """
        self._add_slide("timeline.html.j2",
                        title=title, events=events, footer=footer)

    def add_cards(self, title: str, cards: list[dict], footer: str = ""):
        """2-4 карточки с иконками.

        cards: [{"icon": "monitor", "label": "ТЕХНИКА", "points": ["Пункт 1", "Пункт 2"]}, ...]
        """
        self._add_slide("cards.html.j2",
                        title=title, cards=cards, footer=footer)

    def add_comparison(self, title: str, left: dict, right: dict,
                       note: str = "", footer: str = ""):
        """Две колонки для сравнения.

        left/right: {"icon": "...", "label": "ЗАГОЛОВОК", "points": [...], "text": "..."}
        """
        self._add_slide("comparison.html.j2",
                        title=title, left=left, right=right, note=note, footer=footer)

    def add_kpi_dashboard(self, title: str, metrics: list[dict],
                          note: str = "", footer: str = ""):
        """KPI-дашборд: 4-8 плиток.

        metrics: [{"value": "95%", "label": "Описание KPI", "color": "var(--success)"}, ...]
        """
        self._add_slide("kpi_dashboard.html.j2",
                        title=title, metrics=metrics, note=note, footer=footer)

    def add_stakeholders(self, title: str, internal: list[str], external: list[str],
                         internal_title: str = "", external_title: str = "",
                         note: str = "", footer: str = ""):
        """Стейкхолдеры: внутренние и внешние."""
        self._add_slide("stakeholders.html.j2",
                        title=title, internal=internal, external=external,
                        internal_title=internal_title, external_title=external_title,
                        note=note, footer=footer)

    def add_contacts(self, title: str, tagline: str, contacts: list[str],
                     cta: str = "", cta_sub: str = "", footer: str = ""):
        """Контакты + CTA-блок."""
        self._add_slide("contacts.html.j2",
                        title=title, tagline=tagline, contacts=contacts,
                        cta=cta, cta_sub=cta_sub, footer=footer)

    # ── Рендеринг ───────────────────────────────────────────────

    def render_html(self) -> str:
        """Рендерит полный HTML со всеми слайдами."""
        parts = []
        for slide in self.slides:
            template = self._env.get_template(slide["template"])
            html = template.render(**slide["data"])
            # Добавляем data-theme атрибут
            if 'data-theme=' not in html.split('\n')[0:3]:
                html = html.replace('<html lang="ru">',
                                    f'<html lang="ru" data-theme="{self.theme}">', 1)
            parts.append(html)
        return "\n".join(parts)

    def save(self, path: str):
        """Рендерит и сохраняет PDF."""
        html_str = self.render_html()
        doc = HTML(string=html_str)
        doc.write_pdf(path, stylesheets=[self._css])
        return path


# ── CLI (для тестирования) ─────────────────────────────────────
if __name__ == "__main__":
    pres = Presentation(theme="dark")
    pres.add_title(
        title="ТЕСТОВАЯ ПРЕЗЕНТАЦИЯ",
        subtitle="Проверка всех компонентов",
        description="Этот PDF сгенерирован автоматически — проверка шаблонов и рендеринга.",
    )
    pres.add_mission(
        title="МИССИЯ",
        values=[
            {"icon": "shield", "label": "СКОРОСТЬ", "text": "Минимальный срок обработки заявок и оформления документов."},
            {"icon": "gear", "label": "НАДЁЖНОСТЬ", "text": "Гарантированное исполнение каждого этапа процессов."},
            {"icon": "target", "label": "КОНТРОЛЬ", "text": "Полный аудит ЖЦ каждой закупки и командировки."},
        ],
    )
    pres.add_process(
        title="ПРОЦЕСС",
        steps=[
            {"icon": "clipboard-text", "label": "ЗАЯВКА", "description": "Размещение заявок на закупку в системе."},
            {"icon": "package", "label": "НОМЕНКЛАТУРА", "description": "Заведение и ведение номенклатуры."},
            {"icon": "file-contract", "label": "ДОГОВОР", "description": "Заключение договоров с поставщиками."},
        ],
    )
    pres.add_timeline(
        title="ТАЙМЛАЙН",
        events=[
            {"icon": "calendar-check", "label": "Заявка в 1С", "description": "Оформление и запуск командировки в системе."},
            {"icon": "ticket", "label": "Выкуп билетов и гостиниц", "description": "Бронирование транспорта и проживания."},
            {"icon": "check-circle", "label": "Закрытие", "description": "Полный пакет отчётных документов."},
        ],
    )
    pres.add_cards(
        title="КАРТОЧКИ",
        cards=[
            {"icon": "identification-card", "label": "ПРОПУСКА", "points": ["Оформление и учёт", "Контроль сроков", "Единая база"]},
            {"icon": "shopping-cart", "label": "ЗАКУПКИ", "points": ["Хозяйственные нужды", "Потребности УР", "Бюджетирование"]},
            {"icon": "monitor", "label": "ТЕХНИКА", "points": ["Оснащение сотрудников", "Комплект в день выхода", "Инвентаризация"]},
        ],
    )
    pres.add_comparison(
        title="СРАВНЕНИЕ",
        left={"icon": "wallet", "label": "СОБСТВЕННЫЕ СРЕДСТВА", "points": ["Формирование авансовых отчётов", "Контроль первичной документации", "Соблюдение сроков"]},
        right={"icon": "coins", "label": "ЗАКУПКА ПРОИЗВОДСТВА", "points": ["Закрытие отчётов для производства", "Привязка к ЖЦ закупки", "Сверка с договорной базой"]},
        note="🔄 Полный цикл: от выдачи аванса до утверждения отчёта",
    )
    pres.add_kpi_dashboard(
        title="KPI DASHBOARD",
        metrics=[
            {"value": "< 3 дней", "label": "Средний срок обработки заявки на закупку", "color": "var(--success)"},
            {"value": "≥ 95%", "label": "Доля командировок, закрытых в срок", "color": "var(--success)"},
            {"value": "> 1 200", "label": "Объём документооборота в месяц, ед.", "color": "var(--accent)"},
            {"value": "80+", "label": "Активных договоров с поставщиками", "color": "var(--accent)"},
            {"value": "< 4 часов", "label": "SLA оформления пропуска", "color": "var(--success)"},
            {"value": "100%", "label": "Обеспеченность техникой в день выхода", "color": "var(--success)"},
            {"value": "< 5 дней", "label": "Средний срок закрытия авансового отчёта", "color": "var(--warning)"},
            {"value": "0", "label": "Просроченных договоров поставки", "color": "var(--success)"},
        ],
    )
    pres.add_stakeholders(
        title="СТЕЙКХОЛДЕРЫ",
        internal=["Смежные управления", "Дирекция радиоэлектроники", "Подразделения УР", "Финансовый отдел"],
        external=["Поставщики оборудования", "Транспортные компании", "Гостиницы и операторы", "Контролирующие органы"],
        note="🔄 Регламентированные цепочки | 📞 Единое окно для внешних запросов",
    )
    pres.add_contacts(
        title="КОНТАКТЫ",
        tagline="Отдел сопровождения — ваш операционный фундамент",
        contacts=["📧 email@company.ru", "📞 +7 (XXX) XXX-XX-XX", "📍 Москва, ул. Примерная, д. 1"],
    )
    out = str(Path(__file__).parent.parent / "test_components.pdf")
    pres.save(out)
    print(f"✅ Тестовая презентация сохранена: {out}")
