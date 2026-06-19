#!/usr/bin/env python3
"""Unify card styles across nasledstvo.html and social.html to match index.html"""

import re, sys

def transform_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.splitlines(keepends=True)
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        line_stripped = line.strip()

        # ---- Remove card-tag lines entirely ----
        if '<span class="card-tag">' in line_stripped:
            i += 1
            continue

        # ---- Fix footer: remove updated spans ----
        if '<span class="updated">' in line_stripped:
            i += 1
            continue

        # ---- Fix person: remove emoji ----
        if '<span class="person">' in line_stripped:
            line = line.replace('\U0001f464 ', '').replace('\U0001f464', '')
            result.append(line)
            i += 1
            continue

        # ---- Fix card-header structure ----
        if '<div class="card-header">' in line_stripped:
            # Look ahead for <h2>, skipping blank lines and card-tag lines
            j = i + 1
            while j < len(lines):
                l = lines[j].strip()
                if l == '' or '<span class="card-tag">' in l:
                    j += 1
                    continue
                break

            h2_found = False
            if j < len(lines) and '<h2>' in lines[j]:
                h2_line = lines[j]
                m = re.search(r'<h2>(.*?)</h2>', h2_line)
                if m:
                    h2_found = True
                    h2_text = m.group(1)
                    # Remove leading emoji from h2
                    h2_clean = re.sub(r'^[^\w\s<]+?\s*', '', h2_text)

                    # Determine badge from context (look back for card color class)
                    context_before = "".join(lines[max(0, i-15):i]).lower()
                    badge_cls = "daily"
                    badge_text = "\u0435\u0436\u0435\u0434\u043d\u0435\u0432\u043d\u043e"  # ежедневно
                    if 'card orange' in context_before:
                        badge_cls = "weekly"
                        badge_text = "\u043f\u043d/\u0447\u0442"  # пн/чт
                    elif 'card green' in context_before:
                        badge_cls = "weekly"
                        badge_text = "\u0435\u0436\u0435\u043d\u0435\u0434\u0435\u043b\u044c\u043d\u043e"  # еженедельно

                    # Build indented header-row
                    indent = line[:len(line) - len(line.lstrip())]
                    indent_inner = indent + "  "
                    indent_deep = indent + "    "

                    result.append(line)  # <div class="card-header">
                    result.append(f'{indent_inner}<div class="card-header-row">\n')
                    result.append(f'{indent_deep}<h2>{h2_clean}</h2>\n')
                    result.append(f'{indent_deep}<span class="card-badge {badge_cls}">{badge_text}</span>\n')
                    result.append(f'{indent_inner}</div>\n')

                    # Skip past the original h2 line
                    i = j + 1

            if not h2_found:
                result.append(line)
                i += 1
            continue

        result.append(line)
        i += 1

    output = "".join(result)

    # ---- Unwrap <p>...</p> inside desc (single paragraphs) ----
    output = re.sub(r'<p>\s*(.*?)\s*</p>', r'\1', output)

    # ---- Remove leftover <p>👤...</p> ----
    output = re.sub(r'<p>[^<]*\U0001f464[^<]*</p>\s*\n?', '', output)

    # ---- Clean up double blank lines ----
    output = re.sub(r'\n{3,}', '\n\n', output)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(output)

    print(f'\u2705 {filepath}')


if __name__ == "__main__":
    for fp in sys.argv[1:]:
        transform_file(fp)
