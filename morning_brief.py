#!/usr/bin/env python3
"""大宗商品早报 demo 生成器 v2：10 个品种 + 联动解读。

数据源：Yahoo Finance 免费行情接口。
正式版接入：BMD 棕榈油、郑商所 PTA/MEG（需付费行情源）；结合新闻面的深度归因（需新闻源+大模型）。

用法: python3 morning_brief.py [--out 大宗商品早报-demo.html]
"""
import json, sys, urllib.request, datetime, html

# symbol, 名称, 市场, 单位, 分组, 一句话定位, 关键变量（通常影响它的因素框架，不是本次涨跌的原因）
SYMBOLS = [
    ("KC=F", "咖啡 C 期货", "ICE·纽约", "美分/磅", "农产品", "越南咖啡、土耳其订单都看这个价", "巴西/越南天气、全球库存、美元"),
    ("ZS=F", "大豆期货", "CBOT·芝加哥", "美分/蒲式耳", "农产品", "粮油成本的核心，全球大豆风向标", "南美天气、中美采购节奏、美元"),
    ("ZW=F", "小麦期货", "CBOT·芝加哥", "美分/蒲式耳", "农产品", "面粉、方便面的成本直接相关", "黑海局势、主产国天气、出口政策"),
    ("ZC=F", "玉米期货", "CBOT·芝加哥", "美分/蒲式耳", "农产品", "饲料、淀粉糖的成本基准", "美国中西部天气、乙醇需求、出口销售"),
    ("SB=F", "原糖 11 号", "ICE·纽约", "美分/磅", "农产品", "饮料、果汁用糖的成本基准", "巴西压榨进度、印度出口政策、原油"),
    ("CC=F", "可可期货", "ICE·纽约", "美元/吨", "农产品", "巧克力、饮料行业盯它", "西非天气、产区病害、全球库存"),
    ("CL=F", "WTI 原油", "NYMEX·纽约", "美元/桶", "能源宏观", "运费、包材（PET）成本都跟着它走", "OPEC+政策、美国商业库存、地缘局势"),
    ("DX-Y.NYB", "美元指数", "ICE·纽约", "", "能源宏观", "美元强弱决定大宗商品整体方向", "美联储政策预期、非农/CPI数据"),
    ("TRY=X", "美元/土耳其里拉", "外汇·盘中", "", "外汇", "土耳其的单子最怕里拉闪崩，单日超 2% 直接喊你", "土耳其央行利率政策、通胀数据"),
    ("CNY=X", "美元/人民币", "外汇·盘中", "", "外汇", "进出口报价的结算基准", "中美利差、贸易数据、中间价"),
]
GROUPS = ["农产品", "能源宏观", "外汇"]

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}

def fetch(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        d = json.load(r)
    if d["chart"].get("error"):
        return None
    res = d["chart"]["result"][0]
    if d["chart"].get("error") or not res:
        return None
    m = res["meta"]
    price = m["regularMarketPrice"]
    pct = m.get("regularMarketChangePercent") or 0.0
    prev = price / (1 + pct / 100) if pct else price
    chg = price - prev
    ts = datetime.datetime.fromtimestamp(m["regularMarketTime"],
        tz=datetime.timezone(datetime.timedelta(hours=8)))
    # 5 日走势：收盘序列算本周累计，最高/最低算区间
    ind = res.get("indicators", {}).get("quote", [{}])[0]
    closes = [c for c in (ind.get("close") or []) if c]
    highs = [h for h in (ind.get("high") or []) if h]
    lows = [l for l in (ind.get("low") or []) if l]
    week_pct = (closes[-1] - closes[0]) / closes[0] * 100 if len(closes) >= 2 else 0.0
    hi5 = max(highs) if highs else price
    lo5 = min(lows) if lows else price
    return {"price": price, "prev": prev, "chg": chg, "pct": pct,
            "week_pct": week_pct, "hi5": hi5, "lo5": lo5,
            "time": ts.strftime("%Y-%m-%d %H:%M")}

def fmt(n, dec=2):
    return f"{n:,.{dec}f}"

def position(q):
    """价格在 5 日区间里的位置：上沿 / 中部 / 下沿"""
    hi, lo = q["hi5"], q["lo5"]
    if hi <= lo:
        return ""
    r = (q["price"] - lo) / (hi - lo)
    if r >= 0.7:
        return "处在5日区间上沿"
    if r <= 0.3:
        return "处在5日区间下沿"
    return "处在5日区间中部"

# 每周固定要盯的数据（北京时间）
WATCH = {
    0: ["USDA 作物生长报告（今晚出）——新作供应前景的每周体检"],
    2: ["EIA 原油库存（今晚 22:30）——原油短期方向就看它"],
    3: ["USDA 周度出口销售报告（今晚）——大豆、玉米、小麦的需求晴雨表"],
    4: ["CFTC 持仓报告（周六凌晨）——看投机资金在押多还是押空"],
}

def main():
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv \
        else "大宗商品早报-demo.html"
    rows = []
    for sym, name, mkt, unit, grp, why, drv in SYMBOLS:
        try:
            q = fetch(sym)
        except Exception:
            q = None
        rows.append((sym, name, mkt, unit, grp, why, drv, q))
    by_sym = {r[0]: r[7] for r in rows if r[7]}

    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    date_str = now.strftime("%Y年%-m月%-d日")
    weekday = "一二三四五六日"[now.weekday()]
    alerts = [r for r in rows if r[7] and abs(r[7]["pct"]) >= 2]
    n_ok = sum(1 for r in rows if r[7])

    # 今早一句话：像交易员一样，先给结论
    ok_rows = [r for r in rows if r[7]]
    if ok_rows:
        top = max(ok_rows, key=lambda r: abs(r[7]["pct"]))
        tname, tq = top[1], top[7]
        direction = "涨了" if tq["pct"] >= 0 else "跌了"
        quiet_n = sum(1 for r in ok_rows if abs(r[7]["pct"]) < 1)
        if quiet_n == len(ok_rows):
            one_liner = f"今早一句话：都没啥动静，{tname}{direction} {abs(tq['pct']):.2f}%，已经是全场最大波动了。"
        else:
            one_liner = f"今早一句话：{tname}{direction} {abs(tq['pct']):.2f}%，另外 {quiet_n} 个品种波动不到 1%。"
    else:
        one_liner = "今早一句话：行情一个都没抓到，晚点再看。"

    # 行情卡片（按分组）
    cards = []
    for grp in GROUPS:
        gr = [r for r in rows if r[4] == grp]
        if not gr:
            continue
        cards.append(f'<div class="gtitle">{grp}</div>')
        for sym, name, mkt, unit, _, why, _, q in gr:
            if q is None:
                cards.append(f"""<div class="card"><div class="cn">{html.escape(name)}</div>
<div class="cm">{html.escape(mkt)}</div><div class="err">这个没抓到，晚点再看</div></div>""")
                continue
            up = q["pct"] >= 0
            cls = "up" if up else "dn"
            arrow = "▲" if up else "▼"
            wup = q["week_pct"] >= 0
            wcls = "up" if wup else "dn"
            warrow = "▲" if wup else "▼"
            wk_line = (f'<div class="wk">本周累计 <span class="{wcls}">{warrow}{abs(q["week_pct"]):.2f}%</span>'
                       f' · 5日区间 {fmt(q["lo5"])}–{fmt(q["hi5"])} · {position(q)}</div>')
            cards.append(f"""<div class="card">
<div class="ch"><div><div class="cn">{html.escape(name)}</div><div class="cm">{html.escape(mkt)}</div></div>
<div class="pv {cls}">{fmt(q['price'])}<span class="unit">{html.escape(unit)}</span></div></div>
<div class="cd {cls}"><span class="arrow">{arrow}</span> {fmt(abs(q['chg']))}（{abs(q['pct']):.2f}%）· 昨收 {fmt(q['prev'])}</div>
{wk_line}
<div class="why">{html.escape(why)}</div></div>""")

    # 异动预警
    if alerts:
        ab = "".join(f"<div class='aitem'>⚠️ <b>{html.escape(n)}</b> 单日 {abs(q['pct']):.2f}%，超过 2% 线了</div>"
                     for _, n, _, _, _, _, _, q in alerts)
        alert_html = f"<div class='alert on'><div class='at'>异动预警</div>{ab}</div>"
    else:
        alert_html = ("<div class='alert ok'><div class='at'>异动预警</div>"
                      f"<div class='aitem'>今早 {n_ok} 个品种全在 ±2% 以内，没啥大动静</div></div>")

    # 今日关注：按星期几推当天要出的重要数据
    watch_items = list(WATCH.get(now.weekday(), []))
    if now.weekday() == 4:
        first_friday = next(d for d in range(1, 8)
                            if datetime.date(now.year, now.month, d).weekday() == 4)
        if now.day == first_friday:
            watch_items.insert(0, "美国非农就业数据（今晚 20:30）——美元和商品方向的关键数据")
    if watch_items:
        lis = "".join(f"<div class='witem'>📅 {html.escape(w)}</div>" for w in watch_items)
        watch_html = f"<div class='watch'><div class='wt'>今日关注</div>{lis}</div>"
    else:
        watch_html = ""

    # 联动解读：波动最大的 3 个品种 × 同日宏观对照 × 关键变量框架
    # 注意：这里给的是关联市场对照和变量框架，不是本次涨跌的具体原因（那需要新闻面，demo 版不编造）
    dxy, oil = by_sym.get("DX-Y.NYB"), by_sym.get("CL=F")
    movers = sorted([r for r in ok_rows if r[0] != "DX-Y.NYB"],
                    key=lambda r: abs(r[7]["pct"]), reverse=True)[:3]
    ritems = []
    for sym, name, _, _, _, _, drv, q in movers:
        arrow = "▲" if q["pct"] >= 0 else "▼"
        bits = []
        if dxy:
            bits.append(f"美元指数 {'▲' if dxy['pct'] >= 0 else '▼'}{abs(dxy['pct']):.2f}%")
        if oil and sym != "CL=F":
            bits.append(f"WTI原油 {'▲' if oil['pct'] >= 0 else '▼'}{abs(oil['pct']):.2f}%")
        ml = "，".join(bits) if bits else "宏观数据缺失"
        ritems.append(f"""<div class="ritem"><b>{html.escape(name)} {arrow}{abs(q['pct']):.2f}%</b>
<div class="rmeta">同日：{ml}</div>
<div class="drv">关键变量：{html.escape(drv)}</div></div>""")
    read_html = f"""<div class="read"><div class="rt">🔍 联动解读 <span class="rsub">波动最大的 3 个品种 × 同日宏观 × 关键变量</span></div>
{''.join(ritems)}
<div class="rnote">以上是关联市场对照 + 该品种的关键变量框架；某天具体的涨跌原因需要结合新闻面，demo 版不编造，完整版接入新闻源后由大模型生成归因。</div></div>""" if ritems else ""

    # 页脚：行情源直达链接（每个品种点进去就是 Yahoo 报价页）
    srclinks = " · ".join(
        f'<a href="https://finance.yahoo.com/quote/{s}">{html.escape(n)}</a>'
        for s, n, *_ in rows)

    page = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>大宗商品早报 · {date_str}</title><style>
*{{box-sizing:border-box}}body{{margin:0;font-family:-apple-system,"PingFang SC","Noto Sans SC","Microsoft YaHei",sans-serif;background:#f4f5f7;color:#1a1a1a;line-height:1.6}}
.wrap{{max-width:560px;margin:0 auto;padding:14px 14px 30px}}
.flow{{background:#101828;color:#fff;border-radius:14px;padding:12px 14px;font-size:12.5px;margin-bottom:12px}}
.flow .ft{{font-weight:700;margin-bottom:8px;font-size:13px}}
.steps{{display:flex;align-items:center;gap:4px;flex-wrap:nowrap}}
.step{{flex:1;text-align:center;background:rgba(255,255,255,.1);border-radius:8px;padding:6px 2px;font-size:11px;line-height:1.4}}
.step b{{display:block;font-size:14px}}
.arr{{color:#8a94a6;font-size:11px}}
.hdr{{background:#fff;border-radius:14px;padding:16px;margin-bottom:12px;box-shadow:0 1px 4px rgba(0,0,0,.06)}}
.hdr h1{{font-size:19px;margin:0 0 2px}}
.hdr .sub{{color:#666;font-size:12.5px}}
.one{{background:#fff;border-left:4px solid #f0a020;border-radius:0 12px 12px 0;padding:10px 14px;margin-bottom:12px;font-size:14px;font-weight:600}}
.alert{{border-radius:12px;padding:12px 14px;margin-bottom:12px;font-size:13px}}
.alert.ok{{background:#e9f7ee;border:1px solid #bfe6cd}}
.alert.on{{background:#fdeceb;border:1px solid #f5c2bd}}
.alert .at{{font-weight:700;margin-bottom:4px;font-size:13px}}
.gtitle{{font-size:13px;font-weight:800;color:#666;margin:14px 2px 8px;letter-spacing:2px}}
.card{{background:#fff;border-radius:14px;padding:14px;margin-bottom:10px;box-shadow:0 1px 4px rgba(0,0,0,.06)}}
.ch{{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}}
.cn{{font-weight:700;font-size:15px}}.cm{{color:#888;font-size:12px;margin-top:2px}}
.pv{{font-size:21px;font-weight:800;white-space:nowrap}}.unit{{font-size:11px;font-weight:400;color:#888;margin-left:2px}}
.cd{{margin-top:6px;font-size:13.5px;font-weight:700}}
.up{{color:#c81e1e}}.dn{{color:#1a7f37}}
.wk{{margin-top:6px;font-size:12.5px;color:#666}}
.why{{margin-top:8px;font-size:12.5px;color:#555;background:#f6f7f9;border-radius:8px;padding:8px 10px}}
.watch{{background:#fff8e6;border:1px solid #f0d48a;border-radius:14px;padding:12px 14px;margin-bottom:12px;box-shadow:0 1px 4px rgba(0,0,0,.06)}}
.watch .wt{{font-weight:800;font-size:13.5px;margin-bottom:4px}}
.watch .witem{{font-size:13px;color:#5a4a1a;margin-top:4px;line-height:1.6}}
.read{{background:#fff;border-radius:14px;padding:14px;margin:12px 0;box-shadow:0 1px 4px rgba(0,0,0,.06)}}
.read .rt{{font-weight:800;font-size:14px;margin-bottom:8px}}
.read .rsub{{font-weight:400;font-size:11.5px;color:#888}}
.ritem{{background:#f6f7f9;border-radius:8px;padding:10px 12px;margin-bottom:8px;font-size:13px}}
.ritem .rmeta{{color:#555;margin-top:2px}}
.ritem .drv{{color:#8a6d1b;margin-top:2px}}
.rnote{{font-size:11.5px;color:#999;margin-top:4px;line-height:1.7}}
.rule{{background:#fff;border-radius:14px;padding:14px;margin:12px 0;font-size:12.5px;color:#444;box-shadow:0 1px 4px rgba(0,0,0,.06)}}
.rule b{{color:#111}}
.ft{{font-size:11.5px;color:#999;text-align:center;margin-top:14px;line-height:1.8}}
.ft a{{color:#7a8aa0}}
</style></head><body><div class="wrap">
<div class="flow"><div class="ft">🤖 Agent 自动工作流（每天 7:00）</div>
<div class="steps"><div class="step"><b>⏰</b>定时触发</div><div class="arr">→</div>
<div class="step"><b>🔎</b>自动抓取行情</div><div class="arr">→</div>
<div class="step"><b>🧠</b>生成中文早报</div><div class="arr">→</div>
<div class="step"><b>📲</b>推送到手机</div></div></div>
<div class="hdr"><h1>☀️ 大宗商品早报</h1><div class="sub">{date_str} 星期{weekday} · 北京时间 {now.strftime("%H:%M")} 定时更新 · {n_ok} 个品种</div></div>
<div class="one">{html.escape(one_liner)}</div>
{alert_html}
{watch_html}
{''.join(cards)}
{read_html}
<div class="rule"><b>📌 盯盘逻辑</b><br>
· 单日波动 ≥2% 就标红，直接推到你手机上<br>
· 里拉单独盯——土耳其的单子最怕它突然贬值<br>
· 每周五加一份周报：本周复盘 + 下周看点</div>
<div class="ft">数据：Yahoo Finance 指示性行情（ICE·纽约 / CBOT·芝加哥 / NYMEX / 外汇盘中）<br>
本次抓取时间：北京时间 {now.strftime("%Y-%m-%d %H:%M")}（定时抓取，非实时）<br>
行情源链接：{srclinks}<br>
demo 版 · 正式版可接马来西亚 BMD 棕榈油、郑商所 PTA/MEG；深度归因需接入新闻源</div>
</div></body></html>"""
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"OK: {n_ok}/{len(rows)} 行情获取成功 -> {out}")

if __name__ == "__main__":
    main()
