# -*- coding: utf-8 -*-
"""
本機：
  pip install flask yfinance
  python portfolio.py
開啟：http://127.0.0.1:5000/

Render（建議 Start Command）：
  gunicorn portfolio:app --bind 0.0.0.0:$PORT --access-logfile - --error-logfile - --timeout 120 --forwarded-allow-ips='*'
"""

from flask import Flask, render_template_string, request
from datetime import datetime, date
from werkzeug.middleware.proxy_fix import ProxyFix
import yfinance as yf
import pandas as pd
import threading, time, os, logging

app = Flask(__name__)
# 代理相容（雲端反向代理下正確判斷 https/host）
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# 降噪：隱藏 yfinance 的「possibly delisted」等訊息
logging.getLogger("yfinance").setLevel(logging.ERROR)

# ============== 使用者設定 ==============
# 在「自選股績效」中要排除的美股 ETF（用於 hide_etf 與摘要）
EXCLUDED_ETFS_US = {'SGOV', 'VOO', 'VEA', 'TLT', 'BOXX', 'GLD', 'VT', 'EWT', 'XLU'}

# 你的持倉（可自行調整；你剛剛已移除 00687B.TW，我這裡也不放）
US_PORTFOLIO = [
    {'symbol': 'SGOV',  'shares': 1200,  'cost': 100.40},
    {'symbol': 'VOO',   'shares': 70.00, 'cost': 506.75},
    {'symbol': 'VEA',   'shares': 86.80, 'cost': 53.55},
    {'symbol': 'GLD',   'shares': 16.55, 'cost': 300.10},
    {'symbol': 'TLT',   'shares': 224.7, 'cost': 92.22},
    {'symbol': 'BOXX',  'shares': 100,   'cost': 110.71},
    {'symbol': 'UNH',   'shares': 22,    'cost': 310.86},
    {'symbol': 'GOOGL', 'shares': 72,    'cost': 174.71},
    {'symbol': 'NVDA',  'shares': 32,    'cost': 120.92},
    {'symbol': 'MSTR',  'shares': 10,    'cost': 399.34},
    {'symbol': 'XLU',   'shares': 45.32, 'cost': 84.23},
    {'symbol': 'QCOM',  'shares': 3,     'cost': 148.51},
    {'symbol': 'KO',    'shares': 74.47, 'cost': 68.00},
    {'symbol': 'AEP',   'shares': 12,    'cost': 103.05},
    {'symbol': 'DUK',   'shares': 14,    'cost': 115.43},
    {'symbol': 'MCD',   'shares': 10,    'cost': 299.23},
    {'symbol': 'CEG',   'shares': 1,     'cost': 314.69},
    {'symbol': 'LEU',   'shares': 1,     'cost': 214.64},
    {'symbol': 'PYPL',  'shares': 26,    'cost': 69.41},
    {'symbol': 'TSM',   'shares': 2,     'cost': 227.80},
    {'symbol': 'EWT',   'shares': 100,   'cost': 61.27},
    {'symbol': 'SNPS',  'shares': 4,     'cost': 397.15},
    {'symbol': 'YUM',   'shares': 1,     'cost': 141.34},
    {'symbol': 'XLU',   'shares': 87.71, 'cost': 83.80},
    {'symbol': 'VT',    'shares': 50,    'cost': 133.69},
    {'symbol': 'GIS',   'shares': 2,     'cost': 49.695},
    {'symbol': 'IDMO',   'shares': 60,     'cost': 53.48},



    {'symbol': 'TSLA',   'shares': 1.473,     'cost': 423.885},


    {'symbol': 'AVDV',   'shares': 40,     'cost':87.945},


]

TW_PORTFOLIO = [
    {'symbol': '0050.TW',   'shares': 10637, 'cost': 41.58},
    {'symbol': '006208.TW', 'shares': 9000,  'cost': 112.67},
    {'symbol': '00713.TW',  'shares': 10427, 'cost': 54.40},
    # {'symbol': '00687B.TW', 'shares': 25000, 'cost': 31.59},  # 你已移除
]

# ============== 輕量 TTL 快取 ==============
_TTL_FAST   = 60        # 1 分鐘：即時／當日
_TTL_NORMAL = 300       # 5 分鐘：一般
_TTL_LONG   = 3600      # 1 小時：較長週期

_cache = {}
_cache_lock = threading.Lock()
def _now(): return time.time()
def _get_cache(key):
    with _cache_lock:
        return _cache.get(key)
def _set_cache(key, value):
    with _cache_lock:
        _cache[key] = value

def cached_history(symbol, *, period=None, start=None, end=None, ttl=_TTL_NORMAL):
    """以 TTL 記憶 yfinance history；抓失敗時回上次成功的舊值（stale）。"""
    key = ("history", symbol, period, start, end)
    entry = _get_cache(key)
    now = _now()
    if entry and (now - entry["ts"] < ttl) and entry["data"] is not None:
        return entry["data"]
    try:
        tkr = yf.Ticker(symbol)
        df = tkr.history(period=period) if period else tkr.history(start=start, end=end)
        _set_cache(key, {"ts": now, "data": df})
        return df
    except Exception:
        if entry and entry["data"] is not None:
            return entry["data"]
        return pd.DataFrame()

def cached_close(symbol, ttl=_TTL_FAST):
    """
    取最近一筆有效收盤價：先試 7d，再退 1mo；各自帶 TTL。
    避免假日／停牌導致 period='1d' 為空而報「possibly delisted」。
    """
    for period, t in (("7d", ttl), ("1mo", max(ttl, _TTL_NORMAL))):
        df = cached_history(symbol, period=period, ttl=t)
        if not df.empty and "Close" in df:
            close = df["Close"].dropna()
            if not close.empty:
                return float(close.iloc[-1])
    return 'N/A'

def get_tw_stock_price(symbol):
    """
    台股 ETF/股票的強韌代碼嘗試：.TW → .TWO → 裸代碼 → .TPE
    取最近有效收盤價（搭配 cached_close）。
    """
    base = symbol.replace(".TW", "")
    candidates = [f"{base}.TW", f"{base}.TWO", base, f"{base}.TPE"]
    seen = set()
    for sym in candidates:
        if sym in seen: 
            continue
        seen.add(sym)
        price = cached_close(sym, ttl=_TTL_FAST)
        if price != 'N/A':
            return price
    return 'N/A'

def get_usdtwd_rate(default=31.5):
    px = cached_close('USDTWD=X', ttl=_TTL_FAST)
    return px if px != 'N/A' else default

# ============== 模板（投資組合） ==============
TEMPLATE = r"""
<html>
<head>
    <meta charset="utf-8">
    <title>Chink's Portfolio</title>
    <style>
        body { font-family: "微軟正黑體", Arial, sans-serif; background: #f4f6f8; }
        .container { max-width: 1200px; margin: 32px auto; background: #fff; padding: 28px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,.06); }
        h1 { margin: 0 0 8px; color: #2c3e50; }
        .meta { color: #6c757d; margin-bottom: 16px; }
        .bar { display:flex; justify-content: space-between; align-items:center; margin: 10px 0 18px; gap: 8px; flex-wrap: wrap; }
        .pill { background:#e3f2fd; color:#1976d2; padding:8px 12px; border-radius:999px; font-weight:600; }
        .summary { background:#f8f9fa; padding:18px; border-radius:10px; margin:18px 0; }
        .summary-row { display:flex; justify-content:space-between; margin:6px 0; }
        table { width:100%; border-collapse: collapse; margin-top: 14px; }
        th, td { border: 1px solid #eaecef; padding: 10px 12px; text-align: left; }
        th { background: #f0f3f6; }
        .right { text-align:right; }
        .gain { color:#c62828; font-weight:700; }   /* 紅漲 */
        .loss { color:#2e7d32; font-weight:700; }   /* 綠跌 */
        .nav { margin-bottom: 8px; }
        .nav a { margin-right: 14px; text-decoration:none; color:#1976d2; }
    </style>
</head>
<body>
<div class="container">
    <div class="nav">
        <a href="/">投資組合</a>
        <a href="/health">健康檢查</a>
    </div>

    <h1>Chink's Portfolio</h1>
    <div class="meta">更新時間：{{ updated_at }}（UTC）</div>

    <div class="bar">
        <div class="pill">美金兌台幣匯率：{{ '%.2f' % exchange_rate }} TWD / USD</div>
        <form method="get" id="filterForm">
            <label>
                <input type="checkbox" name="hide_etf" value="1" {% if hide_etf %}checked{% endif %} onchange="document.getElementById('filterForm').submit()">
                隱藏 ETF（{{ excluded_join }}）
            </label>
        </form>
    </div>

    <div class="summary">
        <div class="summary-row">
            <span>總市值（折台幣）：</span>
            <span class="right"><b>{{ '%.0f' % total_market_value_twd }}</b> TWD</span>
        </div>
        <div class="summary-row">
            <span>總成本（折台幣）：</span>
            <span class="right"><b>{{ '%.0f' % total_cost_twd }}</b> TWD</span>
        </div>
        <div class="summary-row">
            <span>總報酬（折台幣）：</span>
            <span class="right {% if total_profit_pct > 0 %}gain{% elif total_profit_pct < 0 %}loss{% endif %}">
                <b>{{ '%.0f' % total_profit_twd }}</b> TWD（{{ '%.2f' % total_profit_pct }}%）
            </span>
        </div>
    </div>

    <h2>美股投資組合（USD）</h2>
    <table>
        <tr>
            <th>代碼</th>
            <th class="right">現價</th>
            <th class="right">成本價</th>
            <th class="right">持有股數</th>
            <th class="right">市值</th>
            <th class="right">佔比（依目前顯示）</th>
            <th class="right">個別報酬率</th>
        </tr>
        {% for it in us_table %}
        <tr>
            <td>{{ it.symbol }}</td>
            <td class="right">{{ it.price_str }}</td>
            <td class="right">{{ it.cost_str }}</td>
            <td class="right">{{ it.shares_str }}</td>
            <td class="right">{{ it.mv_str }}</td>
            <td class="right">{{ it.weight_str }}</td>
            <td class="right {% if it.profit_pct > 0 %}gain{% elif it.profit_pct < 0 %}loss{% endif %}">{{ it.profit_pct_str }}</td>
        </tr>
        {% endfor %}
    </table>

    <div class="summary">
        <h3>美股總結（全部持倉）</h3>
        <div class="summary-row">
            <span>美股總市值：</span>
            <span class="right"><b>{{ '%.2f' % us_total_market_value }}</b> USD（{{ '%.0f' % (us_total_market_value * exchange_rate) }} TWD）</span>
        </div>
        <div class="summary-row">
            <span>美股總成本：</span>
            <span class="right"><b>{{ '%.2f' % us_total_cost }}</b> USD（{{ '%.0f' % (us_total_cost * exchange_rate) }} TWD）</span>
        </div>
        <div class="summary-row">
            <span>美股總報酬：</span>
            <span class="right {% if us_total_profit_pct > 0 %}gain{% elif us_total_profit_pct < 0 %}loss{% endif %}">
                <b>{{ '%.2f' % us_total_profit }}</b> USD（{{ '%.0f' % (us_total_profit * exchange_rate) }} TWD，{{ '%.2f' % us_total_profit_pct }}%）
            </span>
        </div>
    </div>

    <div class="summary">
        <h3>美股自選股績效（已扣除 {{ excluded_join }}）</h3>
        <div class="summary-row">
            <span>自選股總市值：</span>
            <span class="right"><b>{{ '%.2f' % us_core_total_market_value }}</b> USD（{{ '%.0f' % (us_core_total_market_value * exchange_rate) }} TWD）</span>
        </div>
        <div class="summary-row">
            <span>自選股總成本：</span>
            <span class="right"><b>{{ '%.2f' % us_core_total_cost }}</b> USD（{{ '%.0f' % (us_core_total_cost * exchange_rate) }} TWD）</span>
        </div>
        <div class="summary-row">
            <span>自選股總報酬：</span>
            <span class="right {% if us_core_total_profit_pct > 0 %}gain{% elif us_core_total_profit_pct < 0 %}loss{% endif %}">
                <b>{{ '%.2f' % us_core_total_profit }}</b> USD（{{ '%.0f' % (us_core_total_profit * exchange_rate) }} TWD，{{ '%.2f' % us_core_total_profit_pct }}%）
            </span>
        </div>
    </div>

    <h2>台股投資組合（TWD）</h2>
    <table>
        <tr>
            <th>代碼</th>
            <th class="right">現價</th>
            <th class="right">成本價</th>
            <th class="right">持有股數</th>
            <th class="right">市值</th>
            <th class="right">佔比</th>
            <th class="right">個別報酬率</th>
        </tr>
        {% for it in tw_table %}
        <tr>
            <td>{{ it.symbol }}</td>
            <td class="right">{{ it.price_str }}</td>
            <td class="right">{{ it.cost_str }}</td>
            <td class="right">{{ it.shares_str }}</td>
            <td class="right">{{ it.mv_str }}</td>
            <td class="right">{{ it.weight_str }}</td>
            <td class="right {% if it.profit_pct > 0 %}gain{% elif it.profit_pct < 0 %}loss{% endif %}">{{ it.profit_pct_str }}</td>
        </tr>
        {% endfor %}
    </table>

    <div class="summary">
        <div class="summary-row">
            <span>台股總市值：</span>
            <span class="right"><b>{{ '%.0f' % tw_total_market_value }}</b> TWD</span>
        </div>
        <div class="summary-row">
            <span>台股總成本：</span>
            <span class="right"><b>{{ '%.0f' % tw_total_cost }}</b> TWD</span>
        </div>
        <div class="summary-row">
            <span>台股總報酬：</span>
            <span class="right {% if tw_total_profit_pct > 0 %}gain{% elif tw_total_profit_pct < 0 %}loss{% endif %}">
                <b>{{ '%.0f' % tw_total_profit }}</b> TWD（{{ '%.2f' % tw_total_profit_pct }}%）
            </span>
        </div>
    </div>
</div>
</body>
</html>
"""

# ============== 路由 ==============
@app.route("/")
def home():
    updated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    exchange_rate = get_usdtwd_rate(default=31.5)

    # ---- 美股資料
    us_items = []
    us_total_market_value = 0.0
    for row in US_PORTFOLIO:
        price = cached_close(row['symbol'], ttl=_TTL_FAST)
        if price == 'N/A':
            mv = 0.0
            profit = 0.0
            profit_pct = 0.0
            price_str = 'N/A'
            mv_str = 'N/A'
            profit_pct_str = 'N/A'
        else:
            mv = price * row['shares']
            profit = mv - row['cost'] * row['shares']
            profit_pct = (profit / (row['cost'] * row['shares']) * 100) if row['cost'] * row['shares'] else 0.0
            price_str = f"{price:.2f}"
            mv_str = f"{mv:.2f}"
            profit_pct_str = f"{profit_pct:.2f}%"
        us_total_market_value += mv
        us_items.append({
            "symbol": row['symbol'],
            "price": price,
            "price_str": price_str,
            "shares": row['shares'],
            "shares_str": f"{row['shares']:.2f}",
            "cost": row['cost'],
            "cost_str": f"{row['cost']:.2f}",
            "market_value": mv,
            "mv_str": mv_str,
            "profit": profit,
            "profit_pct": profit_pct,
            "profit_pct_str": profit_pct_str,
        })

    us_total_cost = sum(r['cost'] * r['shares'] for r in US_PORTFOLIO)
    us_total_profit = sum(it["profit"] for it in us_items)
    us_total_profit_pct = (us_total_profit / us_total_cost * 100) if us_total_cost else 0.0

    # ===== 美股「自選股」摘要（排除 ETF）=====
    us_core_items = [it for it in us_items if it["symbol"] not in EXCLUDED_ETFS_US]
    us_core_total_market_value = sum(it["market_value"] for it in us_core_items)
    us_core_total_cost = sum((it["cost"] * it["shares"]) for it in us_core_items)
    us_core_total_profit = sum(it["profit"] for it in us_core_items)
    us_core_total_profit_pct = (us_core_total_profit / us_core_total_cost * 100) if us_core_total_cost else 0.0

    # 切換：隱藏 ETF（影響表格與佔比分母）
    hide_etf = request.args.get('hide_etf') in ('1', 'true', 'on', 'yes')
    us_table = us_core_items if hide_etf else us_items
    us_denominator = sum(it["market_value"] for it in us_table) if hide_etf else us_total_market_value
    for it in us_table:
        it["weight_str"] = (f"{(it['market_value'] / us_denominator * 100):.2f}%"
                            if it['market_value'] and us_denominator else "N/A")

    # ---- 台股資料
    tw_items = []
    tw_total_market_value = 0.0
    for row in TW_PORTFOLIO:
        price = get_tw_stock_price(row['symbol'])
        if price == 'N/A':
            mv = 0.0
            profit = 0.0
            profit_pct = 0.0
            price_str = 'N/A'
            mv_str = 'N/A'
            profit_pct_str = 'N/A'
        else:
            mv = price * row['shares']
            profit = mv - row['cost'] * row['shares']
            profit_pct = (profit / (row['cost'] * row['shares']) * 100) if row['cost'] * row['shares'] else 0.0
            price_str = f"{price:.2f}"
            mv_str = f"{mv:.2f}"
            profit_pct_str = f"{profit_pct:.2f}%"
        tw_total_market_value += mv
        tw_items.append({
            "symbol": row['symbol'],
            "price": price,
            "price_str": price_str,
            "shares": row['shares'],
            "shares_str": f"{row['shares']:.2f}",
            "cost": row['cost'],
            "cost_str": f"{row['cost']:.2f}",
            "market_value": mv,
            "mv_str": mv_str,
            "profit": profit,
            "profit_pct": profit_pct,
            "profit_pct_str": profit_pct_str,
        })
    tw_total_cost = sum(r['cost'] * r['shares'] for r in TW_PORTFOLIO)
    tw_total_profit = sum(it["profit"] for it in tw_items)
    tw_total_profit_pct = (tw_total_profit / tw_total_cost * 100) if tw_total_cost else 0.0
    for it in tw_items:
        it["weight_str"] = (f"{(it['market_value'] / tw_total_market_value * 100):.2f}%"
                            if it['market_value'] and tw_total_market_value else "N/A")

    # ---- 總覽（折台幣）
    total_market_value_twd = (us_total_market_value * exchange_rate) + tw_total_market_value
    total_cost_twd = (us_total_cost * exchange_rate) + tw_total_cost
    total_profit_twd = (us_total_profit * exchange_rate) + tw_total_profit
    total_profit_pct = (total_profit_twd / total_cost_twd * 100) if total_cost_twd else 0.0

    # 排序（市值大到小）
    us_table.sort(key=lambda x: x["market_value"], reverse=True)
    tw_items.sort(key=lambda x: x["market_value"], reverse=True)

    return render_template_string(
        TEMPLATE,
        updated_at=updated_at,
        exchange_rate=exchange_rate,
        hide_etf=hide_etf,
        excluded_join="、".join(sorted(EXCLUDED_ETFS_US)),

        us_table=us_table,
        us_total_market_value=us_total_market_value,
        us_total_cost=us_total_cost,
        us_total_profit=us_total_profit,
        us_total_profit_pct=us_total_profit_pct,

        # 自選股摘要
        us_core_total_market_value=us_core_total_market_value,
        us_core_total_cost=us_core_total_cost,
        us_core_total_profit=us_core_total_profit,
        us_core_total_profit_pct=us_core_total_profit_pct,

        tw_table=tw_items,
        tw_total_market_value=tw_total_market_value,
        tw_total_cost=tw_total_cost,
        tw_total_profit=tw_total_profit,
        tw_total_profit_pct=tw_total_profit_pct,

        total_market_value_twd=total_market_value_twd,
        total_cost_twd=total_cost_twd,
        total_profit_twd=total_profit_twd,
        total_profit_pct=total_profit_pct,
    )

@app.get("/health")
def health():
    return {"status": "ok"}

# 本機執行（Render 用 gunicorn，不會跑到這裡）
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
