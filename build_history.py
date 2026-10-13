#!/usr/bin/env python3
"""扫描 history/ 目录，生成 history.html，并给 index.html 加历史入口。"""
import os
import re

HIST = "history"


def main():
    os.makedirs(HIST, exist_ok=True)
    files = sorted(
        (f for f in os.listdir(HIST) if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.html", f)),
        reverse=True,
    )
    items = "\n".join(f'<li><a href="{HIST}/{f}">{f[:-5]}</a></li>' for f in files)
    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>大宗商品早报 · 历史记录</title>
<style>body{{font-family:system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;max-width:640px;margin:40px auto;padding:0 20px;line-height:2}}a{{color:#1a73e8}}</style>
</head>
<body>
<h2>大宗商品早报 · 历史记录</h2>
<p><a href="index.html">&larr; 回今日早报</a></p>
<ul>{items}</ul>
</body></html>
"""
    with open("history.html", "w", encoding="utf-8") as f:
        f.write(page)

    with open("index.html", encoding="utf-8") as f:
        html = f.read()
    if "history.html" not in html:
        link = '<p style="text-align:center;margin:32px 0"><a href="history.html">查看历史记录</a></p>'
        html = html.replace("</body>", link + "</body>")
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(html)
    print(f"history: {len(files)} 天")


if __name__ == "__main__":
    main()
