import markdown
import weasyprint

md_path = "/home/user1/.openclaw/workspace/analytical_review_may_2026_social_support.md"
pdf_path = "/home/user1/.openclaw/workspace/analytical_review_may_2026_social_support.pdf"

with open(md_path, "r", encoding="utf-8") as f:
    md_text = f.read()

html_body = markdown.markdown(md_text, extensions=["tables", "fenced_code"])

html_full = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page {{
    size: A4;
    margin: 2cm;
  }}
  body {{
    font-family: sans-serif;
    font-size: 11pt;
    line-height: 1.5;
    color: #222;
  }}
  h1 {{
    font-size: 18pt;
    border-bottom: 2px solid #333;
    padding-bottom: 6px;
  }}
  h2 {{
    font-size: 15pt;
    color: #333;
    margin-top: 24px;
  }}
  h3 {{
    font-size: 13pt;
    color: #444;
  }}
  table {{
    border-collapse: collapse;
    width: 100%;
    margin: 12px 0;
    font-size: 10pt;
  }}
  th, td {{
    border: 1px solid #999;
    padding: 6px 8px;
    text-align: left;
  }}
  th {{
    background: #eee;
    font-weight: bold;
  }}
  strong {{
    color: #111;
  }}
  hr {{
    border: none;
    border-top: 1px solid #ccc;
    margin: 20px 0;
  }}
</style>
</head>
<body>
{html_body}
</body>
</html>"""

weasyprint.HTML(string=html_full).write_pdf(pdf_path)
print(f"PDF saved: {pdf_path}")
