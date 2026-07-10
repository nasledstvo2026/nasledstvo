"""Convert each region .md to styled HTML page"""
import os, re

regions_dir = "/home/user1/.openclaw/workspace/reports/regions"

def md_to_html(text):
    """Simple markdown to HTML"""
    lines = text.split('\n')
    html = []
    in_table = False
    table_rows = []

    for line in lines:
        # Horizontal rule
        if re.match(r'^---+\s*$', line):
            html.append('<hr>')
            continue

        # Table
        if '|' in line and re.match(r'^\s*\|', line):
            row_line = line.strip()
            if re.match(r'^\|[\s\-:|]+\|$', row_line):
                continue
            cells = [c.strip() for c in row_line.split('|')[1:-1]]
            row = '<tr>' + ''.join(f'<td>{c}</td>' for c in cells) + '</tr>'
            table_rows.append(row)
            continue
        elif table_rows:
            html.append('<table>' + ''.join(table_rows) + '</table>')
            table_rows = []

        # Headings
        if line.startswith('### '):
            html.append(f'<h3>{line[4:].strip()}</h3>')
        elif line.startswith('## '):
            html.append(f'<h2>{line[3:].strip()}</h2>')
        elif line.startswith('# '):
            html.append(f'<h1>{line[2:].strip()}</h1>')
        elif not line.strip():
            html.append('')
        elif re.match(r'^[-*]\s+', line):
            text_content = re.sub(r'^[-*]\s+', '', line)
            text_content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text_content)
            html.append(f'<li>{text_content}</li>')
        elif re.match(r'^\d+\.\s+', line):
            text_content = re.sub(r'^\d+\.\s+', '', line)
            text_content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text_content)
            html.append(f'<li>{text_content}</li>')
        else:
            text_content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', line)
            html.append(f'<p>{text_content}</p>')

    if table_rows:
        html.append('<table>' + ''.join(table_rows) + '</table>')

    return '\n'.join(html)

template = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — НПА май 2026</title>
<style>
:root {{
  --glass-bg: rgba(22, 27, 34, 0.6);
  --glass-border: rgba(255, 255, 255, 0.08);
  --text: #e6edf3;
  --text-dim: #8b949e;
  --text-faint: #484f58;
  --blue: #58a6ff;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #0a0e14;
  background-image:
    radial-gradient(ellipse at 20% 0%, rgba(88,166,255,.08), transparent 50%),
    radial-gradient(ellipse at 80% 100%, rgba(188,140,255,.06), transparent 50%);
  background-attachment: fixed;
  color: var(--text);
  min-height: 100vh;
  padding: 40px 24px;
}}
a {{ color: var(--blue); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
.back {{ display: inline-block; margin-bottom: 24px; font-size: 14px; color: var(--text-dim); }}
.back:hover {{ color: var(--blue); }}
.content {{
  max-width: 800px;
  margin: 0 auto;
  background: var(--glass-bg);
  backdrop-filter: blur(20px);
  border: 1px solid var(--glass-border);
  border-radius: 16px;
  padding: 32px;
  box-shadow: 0 4px 24px rgba(0,0,0,.3);
}}
h1 {{ font-size: 22px; font-weight: 800; margin-bottom: 8px; }}
h2 {{ font-size: 18px; font-weight: 700; margin: 24px 0 12px; color: #58a6ff; }}
h3 {{ font-size: 15px; font-weight: 600; margin: 20px 0 8px; color: #bc8cff; }}
p {{ font-size: 14px; line-height: 1.7; color: var(--text-dim); margin: 8px 0; }}
strong {{ color: var(--text); }}
li {{ font-size: 14px; line-height: 1.7; color: var(--text-dim); margin: 4px 0 4px 20px; }}
hr {{ border: none; border-top: 1px solid rgba(255,255,255,.08); margin: 20px 0; }}
table {{ border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 13px; }}
th, td {{ border: 1px solid rgba(255,255,255,.1); padding: 8px 10px; text-align: left; color: var(--text-dim); }}
th {{ background: rgba(255,255,255,.05); font-weight: 600; }}
.footer {{ text-align: center; padding: 24px; font-size: 12px; color: var(--text-faint); }}
</style>
</head>
<body>
<a class="back" href="../report-irina.html">← Все регионы</a>
<div class="content">
{body}
</div>
<div class="footer"><strong>☽ ЛУНТ</strong> · НПА май 2026</div>
</body>
</html>"""

for fname in sorted(os.listdir(regions_dir)):
    if not fname.endswith(".md"):
        continue
    md_path = os.path.join(regions_dir, fname)
    html_path = os.path.join(regions_dir, fname.replace(".md", ".html"))

    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    title = fname.replace(".md", "").replace("_", " ")
    body = md_to_html(md_text)
    page = template.format(title=title, body=body)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(page)

    print(f"OK: {fname} -> {fname.replace('.md', '.html')}")

print("\nDone!")
