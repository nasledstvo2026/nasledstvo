#!/usr/bin/env python3
"""Fix nasledstvo.html issues"""

import re

with open("/home/c/cq832843/public_html/nasledstvo.html", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Remove person name lines from desc (Катя, Лена, Данил as sole line content)
lines = content.split("\n")
result = []
for i, line in enumerate(lines):
    stripped = line.strip()
    if stripped in ("Катя", "Лена", "Данил"):
        continue
    result.append(line)
content = "\n".join(result)

# 2. Fix broken stats link — add proper <a> tag with href
old_stats = '    </a>\n      <span class="icon">📊</span> Статистика\n    </a>'
new_stats = '    </a>\n    <a href="stats-inheritance.html" class="nav-btn pink">\n      <span class="icon">📊</span> Статистика\n    </a>'
content = content.replace(old_stats, new_stats)

with open("/home/c/cq832843/public_html/nasledstvo.html", "w", encoding="utf-8") as f:
    f.write(content)

print("OK")
