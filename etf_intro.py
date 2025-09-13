# -*- coding: utf-8 -*-
"""
啟動方式：
  pip install flask yfinance
  python app.py
開啟：
  http://127.0.0.1:5000/          （ETF介紹）
  http://127.0.0.1:5000/portfolio （投資組合 + 自選股績效摘要）
"""


from flask import Flask, render_template_string, request
import yfinance as yf
from datetime import datetime, timedelta, date

app = Flask(__name__)
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
# ===== 你要在「自選股績效」中排除的美股 ETF（可自行調整） =====
EXCLUDED_ETFS_US = {'SGOV', 'VOO', 'VEA', 'TLT','BOXX','MSTR','VT','GLD','XLU','EWT'}

# --------------------- ETF 基礎資料 ---------------------
bond_etfs = [
    {'名稱': 'SGOV', '類型': '國庫券', '內扣費': '0.07%'},
    {'名稱': 'SHY', '類型': '短債', '內扣費': '0.15%'},
    {'名稱': 'VGSH', '類型': '短債', '內扣費': '0.04%'},
    {'名稱': 'VCSH', '類型': '投等債', '內扣費': '0.04%'},
    {'名稱': 'IEI', '類型': '中長期債', '內扣費': '0.15%'},
    {'名稱': 'VGIT', '類型': '中長期債', '內扣費': '0.04%'},
    {'名稱': 'IEF', '類型': '中長期債', '內扣費': '0.15%'},
    {'名稱': 'TLT', '類型': '長債', '內扣費': '0.15%'},
]

bond_intro = {
    'SGOV': 'iShares 0-3 Month Treasury Bond ETF，追蹤美國0-3個月國庫券，風險極低，流動性高。',
    'SHY': 'iShares 1-3 Year Treasury Bond ETF，追蹤美國1-3年期國債，風險低，適合保守型投資人。',
    'VGSH': 'Vanguard Short-Term Treasury ETF，追蹤1-3年期美國國債。',
    'VCSH': 'Vanguard Short-Term Corporate Bond ETF，追蹤1-5年期美國投資等級公司債。',
    'IEI': 'iShares 3-7 Year Treasury Bond ETF，追蹤3-7年期美國國債，利率敏感度適中。',
    'VGIT': 'Vanguard Intermediate-Term Treasury ETF，追蹤3-10年期美國國債。',
    'IEF': 'iShares 7-10 Year Treasury Bond ETF，追蹤7-10年期美國國債，利率敏感度較高。',
    'TLT': 'iShares 20+ Year Treasury Bond ETF，追蹤20年以上美國國債，利率敏感度高，波動較大。'
}

index_etfs = [
    {'名稱': 'VOO',  '類型': '美國大盤',   '內扣費': '0.03%'},
    {'名稱': 'VEA',  '類型': '已開發國家', '內扣費': '0.05%'},
    {'名稱': 'VT',   '類型': '全球股票',   '內扣費': '0.07%'},
    {'名稱': 'VGK',  '類型': '歐洲股票',   '內扣費': '0.11%'},
    {'名稱': 'VTI',  '類型': '美國全市場', '內扣費': '0.03%'},
    {'名稱': 'SPMO', '類型': '美股動能',   '內扣費': '0.13%'},
    {'名稱': '0050.TW',  '類型': '台灣大盤',   '內扣費': '0.32%'},
    {'名稱': '00713.TW', '類型': '台灣高息低波', '內扣費': '0.64%'},
]

index_intro = {
    'VOO': 'Vanguard S&P 500 ETF，追蹤美國標普500大盤指數。',
    'VEA': 'Vanguard FTSE Developed Markets ETF，追蹤已開發國家（不含美國、加拿大）股票。',
    'VT':  'Vanguard Total World Stock ETF，追蹤全球股票市場。',
    'VGK': 'Vanguard FTSE Europe ETF，追蹤歐洲已開發國家股票。',
    'VTI': 'Vanguard Total Stock Market ETF，追蹤美國整體股票市場。',
    'SPMO': 'Invesco S&P 500 Momentum ETF，追蹤 S&P 500 Momentum 指數（動能加權），多頭時常占優、風格反轉時回撤風險較高。',
    '0050.TW': '元大台灣50 ETF，追蹤台灣證券交易所市值前50大上市公司。',
    '00713.TW': '元大台灣高息低波ETF，追蹤台灣高股息且波動低的上市公司。',
}

# 新增貴金屬 / 公用事業
precious_etfs = [
    {'名稱': 'GLD', '類型': '黃金', '內扣費': '0.40%'},
    {'名稱': 'SLV', '類型': '白銀', '內扣費': '0.50%'},
]
precious_intro = {
    'GLD': 'SPDR Gold Shares，追蹤黃金現貨價格，全球最大黃金ETF。',
    'SLV': 'iShares Silver Trust，追蹤白銀現貨價格，全球最大白銀ETF。',
}

utility_etfs = [
    {'名稱': 'XLU', '類型': '公用事業', '內扣費': '0.10%'},
    {'名稱': 'VPU', '類型': '公用事業', '內扣費': '0.10%'},
]
utility_intro = {
    'XLU': 'Utilities Select Sector SPDR Fund，追蹤美國公用事業類股。',
    'VPU': 'Vanguard Utilities ETF，追蹤美國公用事業類股。',
}

# --------------------- 工具函式 ---------------------
def calc_annualized_return(ticker, years, price):
    """以歷史收盤價計算年化報酬率（3/5/10 年）；price 為最新價。"""
    try:
        end_date = datetime.today()
        start_date = end_date - timedelta(days=365 * years)
        hist = ticker.history(start=start_date.strftime('%Y-%m-%d'),
                              end=end_date.strftime('%Y-%m-%d'))
        if not hist.empty:
            first_price = hist['Close'].iloc[0]
            actual_years = (hist.index[-1] - hist.index[0]).days / 365.25
            if first_price > 0 and price != 'N/A' and actual_years > 0:
                ann_return = (price / first_price) ** (1 / actual_years) - 1
                return f"{ann_return * 100:.2f}%"
    except Exception:
        pass
    return 'N/A'

def get_etf_data(etf_list, intro_dict):
    etfs = []
    for etf in etf_list:
        symbol = etf['名稱']
        ticker = yf.Ticker(symbol)
        data = ticker.history(period='2d')
        if not data.empty and len(data) >= 2:
            prev_close = data['Close'].iloc[-2]
            price = data['Close'].iloc[-1]
            pct = ((price - prev_close) / prev_close * 100) if prev_close != 0 else 'N/A'
        else:
            price = 'N/A'
            pct = 'N/A'
        ann_return_3y = calc_annualized_return(ticker, 3, price)
        ann_return_5y = calc_annualized_return(ticker, 5, price)
        ann_return_10y = calc_annualized_return(ticker, 10, price)
        if pct != 'N/A':
            color = 'red' if pct > 0 else ('green' if pct < 0 else 'black')
        else:
            color = 'black'
        etfs.append({
            '名稱': symbol,
            '類型': etf['類型'],
            '內扣費': etf['內扣費'],
            '簡介': intro_dict.get(symbol, ''),
            '現價': f"{price:.2f}" if price != 'N/A' else 'N/A',
            '漲跌幅': f"{pct:.2f}%" if pct != 'N/A' else 'N/A',
            '年化報酬率_3y': ann_return_3y,
            '年化報酬率_5y': ann_return_5y,
            '年化報酬率_10y': ann_return_10y,
            'color': color
        })
    return etfs

def get_tw_stock_price(symbol):
    """嘗試多種可能的台股代碼格式，取最新收盤價。"""
    possible_symbols = [
        symbol,
        symbol.replace('.TW', ''),
        symbol.replace('.TW', '.TWO'),
        symbol.replace('.TW', '.TW:US'),
    ]
    for sym in possible_symbols:
        try:
            ticker = yf.Ticker(sym)
            hist = ticker.history(period='1d')
            if not hist.empty:
                return hist['Close'].iloc[-1]
        except Exception:
            continue
    return 'N/A'

# --------------------- 路由：ETF介紹 ---------------------
@app.route('/')
def index():
    bond_data = get_etf_data(bond_etfs, bond_intro)
    index_data = get_etf_data(index_etfs, index_intro)
    precious_data = get_etf_data(precious_etfs, precious_intro)
    utility_data = get_etf_data(utility_etfs, utility_intro)
    html = '''
    <html>
    <head>
        <div style="display:flex; gap:16px; margin-bottom:16px;">

        <a href="/">ETF介紹</a>
        <a href="/portfolio">投資組合</a>
        </div>
        
        <meta charset="utf-8">
        <style>
            body { font-family: "微軟正黑體", Arial, sans-serif; background: #f8f9fa; }
            .container { max-width: 1400px; margin: 40px auto; background: #fff; padding: 32px; border-radius: 12px; box-shadow: 0 2px 8px #ccc; }
            h1 { text-align: center; color: #2c3e50; }
            h2 { color: #2c3e50; margin-top: 40px; }
            table { width: 100%; border-collapse: collapse; margin-top: 24px; }
            th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
            th { background: #e9ecef; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>ETF介紹</h1>

            <h2>指數ETF</h2>
            <table>
                <tr>
                    <th>名稱</th><th>類型</th><th>現價</th><th>當日漲跌幅</th>
                    <th>年化報酬率(3年)</th><th>年化報酬率(5年)</th><th>年化報酬率(10年)</th>
                    <th>內扣費</th><th>簡介</th>
                </tr>
                {% for etf in index_data %}
                <tr>
                    <td>{{ etf['名稱'] }}</td>
                    <td>{{ etf['類型'] }}</td>
                    <td style="color: {{ etf['color'] }}; font-weight: bold;">{{ etf['現價'] }}</td>
                    <td style="color: {{ etf['color'] }}; font-weight: bold;">{{ etf['漲跌幅'] }}</td>
                    <td>{{ etf['年化報酬率_3y'] }}</td>
                    <td>{{ etf['年化報酬率_5y'] }}</td>
                    <td>{{ etf['年化報酬率_10y'] }}</td>
                    <td>{{ etf['內扣費'] }}</td>
                    <td>{{ etf['簡介'] }}</td>
                </tr>
                {% endfor %}
            </table>

            <h2>債券ETF</h2>
            <table>
                <tr>
                    <th>名稱</th><th>類型</th><th>現價</th><th>當日漲跌幅</th>
                    <th>年化報酬率(3年)</th><th>年化報酬率(5年)</th><th>年化報酬率(10年)</th>
                    <th>內扣費</th><th>簡介</th>
                </tr>
                {% for etf in bond_data %}
                <tr>
                    <td>{{ etf['名稱'] }}</td>
                    <td>{{ etf['類型'] }}</td>
                    <td style="color: {{ etf['color'] }}; font-weight: bold;">{{ etf['現價'] }}</td>
                    <td style="color: {{ etf['color'] }}; font-weight: bold;">{{ etf['漲跌幅'] }}</td>
                    <td>{{ etf['年化報酬率_3y'] }}</td>
                    <td>{{ etf['年化報酬率_5y'] }}</td>
                    <td>{{ etf['年化報酬率_10y'] }}</td>
                    <td>{{ etf['內扣費'] }}</td>
                    <td>{{ etf['簡介'] }}</td>
                </tr>
                {% endfor %}
            </table>

            <h2>貴金屬ETF</h2>
            <table>
                <tr>
                    <th>名稱</th><th>類型</th><th>現價</th><th>當日漲跌幅</th>
                    <th>年化報酬率(3年)</th><th>年化報酬率(5年)</th><th>年化報酬率(10年)</th>
                    <th>內扣費</th><th>簡介</th>
                </tr>
                {% for etf in precious_data %}
                <tr>
                    <td>{{ etf['名稱'] }}</td>
                    <td>{{ etf['類型'] }}</td>
                    <td style="color: {{ etf['color'] }}; font-weight: bold;">{{ etf['現價'] }}</td>
                    <td style="color: {{ etf['color'] }}; font-weight: bold;">{{ etf['漲跌幅'] }}</td>
                    <td>{{ etf['年化報酬率_3y'] }}</td>
                    <td>{{ etf['年化報酬率_5y'] }}</td>
                    <td>{{ etf['年化報酬率_10y'] }}</td>
                    <td>{{ etf['內扣費'] }}</td>
                    <td>{{ etf['簡介'] }}</td>
                </tr>
                {% endfor %}
            </table>

            <h2>公用事業ETF</h2>
            <table>
                <tr>
                    <th>名稱</th><th>類型</th><th>現價</th><th>當日漲跌幅</th>
                    <th>年化報酬率(3年)</th><th>年化報酬率(5年)</th><th>年化報酬率(10年)</th>
                    <th>內扣費</th><th>簡介</th>
                </tr>
                {% for etf in utility_data %}
                <tr>
                    <td>{{ etf['名稱'] }}</td>
                    <td>{{ etf['類型'] }}</td>
                    <td style="color: {{ etf['color'] }}; font-weight: bold;">{{ etf['現價'] }}</td>
                    <td style="color: {{ etf['color'] }}; font-weight: bold;">{{ etf['漲跌幅'] }}</td>
                    <td>{{ etf['年化報酬率_3y'] }}</td>
                    <td>{{ etf['年化報酬率_5y'] }}</td>
                    <td>{{ etf['年化報酬率_10y'] }}</td>
                    <td>{{ etf['內扣費'] }}</td>
                    <td>{{ etf['簡介'] }}</td>
                </tr>
                {% endfor %}
            </table>
        </div>
    </body>
    </html>
    '''
    return render_template_string(html,
                                  bond_data=bond_data,
                                  index_data=index_data,
                                  precious_data=precious_data,
                                  utility_data=utility_data)

# --------------------- 路由：投資組合 & 自選股績效 ---------------------
@app.route('/portfolio')
def portfolio():
    # 美股投資組合
    us_portfolio = [
        {'symbol': 'SGOV',  'shares': 1200,  'cost': 100.40},
        {'symbol': 'VOO',   'shares': 70.00, 'cost': 506.75},
        # {'symbol': 'SPMO', 'shares': 60,    'cost': 114.2},
        {'symbol': 'VEA',   'shares': 86.80, 'cost': 53.55},
        {'symbol': 'GLD',   'shares': 16.55,  'cost': 300.10},
        {'symbol': 'TLT',   'shares': 224.7, 'cost': 92.22},
        {'symbol': 'BOXX',  'shares': 100,   'cost': 110.71},
        {'symbol': 'UNH',   'shares': 22,    'cost': 310.86},
        {'symbol': 'GOOGL', 'shares': 72,'cost': 174.71},
        {'symbol': 'NVDA',  'shares': 32,    'cost': 120.92},
        {'symbol': 'MSTR',  'shares': 10,    'cost': 399.34},
        # {'symbol': 'PYPL',  'shares': 25,    'cost': 69.51},
        {'symbol': 'XLU',   'shares': 45.32,  'cost': 84.23},
        {'symbol': 'QCOM',  'shares': 3,     'cost': 148.51},
        {'symbol': 'KO',    'shares': 74.47, 'cost': 68.00},
        {'symbol': 'AEP',   'shares': 12,    'cost': 103.05},
        # {'symbol': 'CB',    'shares': 3,     'cost': 271.52},
        {'symbol': 'DUK',   'shares': 14,    'cost': 115.43},
        {'symbol': 'MCD',   'shares': 10,    'cost': 299.23},
        {'symbol': 'CEG',   'shares': 1,    'cost': 314.69},
            {'symbol': 'LEU',   'shares': 1,    'cost': 214.64},
            {'symbol': 'PYPL',   'shares': 26,    'cost': 69.41},
        {'symbol': 'TSM',   'shares': 2,    'cost': 227.8},

        {'symbol': 'EWT',   'shares': 100,    'cost': 61.27},
        {'symbol': 'SNPS',   'shares': 4,    'cost': 397.15},
        {'symbol': 'YUM',   'shares': 1,    'cost': 141.34},

        {'symbol': 'XLU',   'shares': 87.71,    'cost': 83.80},
        {'symbol': 'VT',   'shares': 50,    'cost': 133.69},



    ]

    # 台股投資組合
    tw_portfolio = [
        {'symbol': '0050.TW',   'shares': 10637, 'cost': 41.58},
        {'symbol': '006208.TW', 'shares': 9000,  'cost': 112.67},
        {'symbol': '00713.TW',  'shares': 10427, 'cost': 54.4},
        {'symbol': '00687B.TW', 'shares': 25000, 'cost': 31.59},
    ]

    # 匯率（USD/TWD）
    try:
        usd_twd_hist = yf.Ticker('USDTWD=X').history(period='1d')
        exchange_rate = usd_twd_hist['Close'].iloc[-1] if not usd_twd_hist.empty else 31.5
    except Exception:
        exchange_rate = 31.5

    # ---- 美股即時數據
    us_total_market_value = 0
    for item in us_portfolio:
        ticker = yf.Ticker(item['symbol'])
        hist = ticker.history(period='1d')
        price = hist['Close'].iloc[-1] if not hist.empty else 'N/A'
        market_value = price * item['shares'] if price != 'N/A' else 0
        item['price'] = price
        item['market_value'] = market_value
        item['profit'] = market_value - item['cost'] * item['shares'] if price != 'N/A' else 0
        item['profit_pct'] = (item['profit'] / (item['cost'] * item['shares']) * 100) if price != 'N/A' else 0
        us_total_market_value += market_value

    # ---- 台股即時數據
    tw_total_market_value = 0
    for item in tw_portfolio:
        price = get_tw_stock_price(item['symbol'])
        market_value = price * item['shares'] if price != 'N/A' else 0
        item['price'] = price
        item['market_value'] = market_value
        item['profit'] = market_value - item['cost'] * item['shares'] if price != 'N/A' else 0
        item['profit_pct'] = (item['profit'] / (item['cost'] * item['shares']) * 100) if price != 'N/A' else 0
        tw_total_market_value += market_value

    # 排序
    us_portfolio.sort(key=lambda x: x['market_value'], reverse=True)
    tw_portfolio.sort(key=lambda x: x['market_value'], reverse=True)

    # 各市場總結（全部持倉）
    us_total_cost = sum(item['cost'] * item['shares'] for item in us_portfolio)
    us_total_profit = sum(item['profit'] for item in us_portfolio)
    us_total_profit_pct = (us_total_profit / us_total_cost * 100) if us_total_cost else 0

    tw_total_cost = sum(item['cost'] * item['shares'] for item in tw_portfolio)
    tw_total_profit = sum(item['profit'] for item in tw_portfolio)
    tw_total_profit_pct = (tw_total_profit / tw_total_cost * 100) if tw_total_cost else 0

    # ===== 自選股績效（排除 EXCLUDED_ETFS_US）=====
    us_core = [it for it in us_portfolio if it['symbol'] not in EXCLUDED_ETFS_US]
    us_core_total_market_value = sum(it['market_value'] for it in us_core)
    us_core_total_cost = sum(it['cost'] * it['shares'] for it in us_core)
    us_core_total_profit = sum(it['profit'] for it in us_core)
    us_core_total_profit_pct = (us_core_total_profit / us_core_total_cost * 100) if us_core_total_cost else 0

    # ===== 切換：是否隱藏 ETF（影響表格 & 佔比分母）=====
    hide_etf = request.args.get('hide_etf') in ('1', 'true', 'on', 'yes')
    us_table = us_core if hide_etf else us_portfolio
    us_denominator = (us_core_total_market_value if hide_etf else us_total_market_value)

    # 轉台幣（總覽仍以「全部持倉」計）
    total_market_value_twd = (us_total_market_value * exchange_rate) + tw_total_market_value
    total_cost_twd = (us_total_cost * exchange_rate) + tw_total_cost
    total_profit_twd = (us_total_profit * exchange_rate) + tw_total_profit
    total_profit_pct = (total_profit_twd / total_cost_twd * 100) if total_cost_twd else 0

    # 今年以來績效（VOO、0050）
    today = date.today()
    year_start = date(today.year, 1, 1)

    voo_hist = yf.Ticker('VOO').history(start=year_start.strftime('%Y-%m-%d'),
                                        end=today.strftime('%Y-%m-%d'))
    if not voo_hist.empty:
        sp500_ytd = (voo_hist['Close'].iloc[-1] - voo_hist['Close'].iloc[0]) / voo_hist['Close'].iloc[0] * 100
        sp500_ytd_str = f"{sp500_ytd:.2f}%"
        sp500_color = 'red' if sp500_ytd > 0 else ('green' if sp500_ytd < 0 else 'black')
    else:
        sp500_ytd_str, sp500_color = 'N/A', 'black'

    tw50_hist = yf.Ticker('0050.TW').history(start=year_start.strftime('%Y-%m-%d'),
                                             end=today.strftime('%Y-%m-%d'))
    if not tw50_hist.empty:
        tw50_ytd = (tw50_hist['Close'].iloc[-1] - tw50_hist['Close'].iloc[0]) / tw50_hist['Close'].iloc[0] * 100
        tw50_ytd_str = f"{tw50_ytd:.2f}%"
        tw50_color = 'red' if tw50_ytd > 0 else ('green' if tw50_ytd < 0 else 'black')
    else:
        tw50_ytd_str, tw50_color = 'N/A', 'black'

    html = '''
    <html>
    <head>
        <title>Chink's Portfolio</title>
        <meta charset="utf-8">
        <style>
            body { font-family: "微軟正黑體", Arial, sans-serif; background: #f8f9fa; }
            .container { max-width: 1200px; margin: 40px auto; background: #fff; padding: 32px; border-radius: 12px; box-shadow: 0 2px 8px #ccc; }
            h1 { text-align: center; color: #2c3e50; }
            h2 { color: #2c3e50; margin-top: 40px; }
            table { width: 100%; border-collapse: collapse; margin-top: 16px; }
            th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
            th { background: #e9ecef; }
            .summary { background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }
            .summary h3 { margin-top: 0; color: #495057; }
            .summary-row { display: flex; justify-content: space-between; margin: 10px 0; }
            .summary-label { font-weight: bold; }
            .summary-value { font-weight: bold; }
            .exchange-rate { background: #e3f2fd; padding: 10px; border-radius: 5px; margin: 10px 0; text-align: center; color: #1976d2; }
            .right { text-align: right; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Chink's Portfolio</h1>

            <div class="exchange-rate">
                <strong>美金兌台幣匯率: {{ '%.2f' % exchange_rate }} TWD/USD</strong>
            </div>

            <div class="summary">
                <h3>投資組合總覽（台幣）</h3>
                <div class="summary-row">
                    <span class="summary-label">總市值:</span>
                    <span class="summary-value">{{ '%.0f' % total_market_value_twd }} TWD</span>
                </div>
                <div class="summary-row">
                    <span class="summary-label">總成本:</span>
                    <span class="summary-value">{{ '%.0f' % total_cost_twd }} TWD</span>
                </div>
                <div class="summary-row">
                    <span class="summary-label">總報酬:</span>
                    <span class="summary-value" style="color: {% if total_profit_pct > 0 %}red{% elif total_profit_pct < 0 %}green{% else %}black{% endif %};">
                        {{ '%.0f' % total_profit_twd }} TWD ({{ '%.2f' % total_profit_pct }}%)
                    </span>
                </div>
            </div>

            <h2>美股投資組合（美金）</h2>

            <!-- 切換：顯示/隱藏 ETF -->
            <form method="get" id="filterForm" class="right">
                <label>
                    <input type="checkbox" name="hide_etf" value="1" {% if hide_etf %}checked{% endif %} onchange="document.getElementById('filterForm').submit()">
                    隱藏 ETF（SGOV、VOO、VEA、TLT、BOXX、GLD、VT、EWT）
                </label>
            </form>

            <table>
            <tr>
                <th>代碼</th>
                <th>現價</th>
                <th>成本價</th>  <!-- 新增 -->
                <th>持有股數</th>
                <th>市值</th>
                <th>佔美股比例（依目前顯示）</th>
                <th>個別報酬率</th>
            </tr>
            {% for item in us_table %}
            <tr>
                <td>{{ item['symbol'] }}</td>
                <td>{{ '%.2f' % item['price'] if item['price'] != 'N/A' else 'N/A' }}</td>
                <td>{{ '%.2f' % item['cost'] }}</td>  <!-- 新增 -->
                <td>{{ '%.2f' % item['shares'] }}</td>
                <td>{{ '%.2f' % item['market_value'] if item['price'] != 'N/A' else 'N/A' }}</td>
                <td>{{ '%.2f' % (item['market_value'] / us_denominator * 100) if item['price'] != 'N/A' and us_denominator > 0 else 'N/A' }}%</td>
                <td style="color: {% if item['price'] != 'N/A' and item['profit_pct'] > 0 %}red{% elif item['price'] != 'N/A' and item['profit_pct'] < 0 %}green{% else %}black{% endif %}; font-weight: bold;">
                {{ '%.2f' % item['profit_pct'] if item['price'] != 'N/A' else 'N/A' }}%
                </td>
            </tr>
            {% endfor %}
            </table>

            <div class="summary">
                <h3>美股投資組合摘要</h3>
                <div class="summary-row">
                    <span class="summary-label">美股總市值（全部持倉）:</span>
                    <span class="summary-value">{{ '%.2f' % us_total_market_value }} USD ({{ '%.0f' % (us_total_market_value * exchange_rate) }} TWD)</span>
                </div>
                <div class="summary-row">
                    <span class="summary-label">美股總成本（全部持倉）:</span>
                    <span class="summary-value">{{ '%.2f' % us_total_cost }} USD ({{ '%.0f' % (us_total_cost * exchange_rate) }} TWD)</span>
                </div>
                <div class="summary-row">
                    <span class="summary-label">美股總報酬（全部持倉）:</span>
                    <span class="summary-value" style="color: {% if us_total_profit_pct > 0 %}red{% elif us_total_profit_pct < 0 %}green{% else %}black{% endif %};">
                        {{ '%.2f' % us_total_profit }} USD ({{ '%.0f' % (us_total_profit * exchange_rate) }} TWD) ({{ '%.2f' % us_total_profit_pct }}%)
                    </span>
                </div>
                <div class="summary-row">
                    <span class="summary-label">S&amp;P 500 今年以來績效（VOO）:</span>
                    <span class="summary-value" style="color: {{ sp500_color }};">{{ sp500_ytd_str }}</span>
                </div>
            </div>

            <!-- 自選股績效摘要（恆以排除 ETF 計算） -->
            <div class="summary">
                <h3>美股自選股績效（已扣除 SGOV、VOO、VEA、TLT、BOXX）</h3>
                <div class="summary-row">
                    <span class="summary-label">自選股總市值:</span>
                    <span class="summary-value">{{ '%.2f' % us_core_total_market_value }} USD ({{ '%.0f' % (us_core_total_market_value * exchange_rate) }} TWD)</span>
                </div>
                <div class="summary-row">
                    <span class="summary-label">自選股總成本:</span>
                    <span class="summary-value">{{ '%.2f' % us_core_total_cost }} USD ({{ '%.0f' % (us_core_total_cost * exchange_rate) }} TWD)</span>
                </div>
                <div class="summary-row">
                    <span class="summary-label">自選股總報酬:</span>
                    <span class="summary-value" style="color: {% if us_core_total_profit_pct > 0 %}red{% elif us_core_total_profit_pct < 0 %}green{% else %}black{% endif %};">
                        {{ '%.2f' % us_core_total_profit }} USD ({{ '%.0f' % (us_core_total_profit * exchange_rate) }} TWD) ({{ '%.2f' % us_core_total_profit_pct }}%)
                    </span>
                </div>
            </div>

            <h2>台股投資組合（台幣）</h2>
            <table>
            <tr>
                <th>代碼</th>
                <th>現價</th>
                <th>成本價</th>  <!-- 新增 -->
                <th>持有股數</th>
                <th>市值</th>
                <th>佔台股比例</th>
                <th>個別報酬率</th>
            </tr>
            {% for item in tw_portfolio %}
            <tr>
                <td>{{ item['symbol'] }}</td>
                <td>{{ '%.2f' % item['price'] if item['price'] != 'N/A' else 'N/A' }}</td>
                <td>{{ '%.2f' % item['cost'] }}</td>  <!-- 新增 -->
                <td>{{ '%.2f' % item['shares'] }}</td>
                <td>{{ '%.2f' % item['market_value'] if item['price'] != 'N/A' else 'N/A' }}</td>
                <td>{{ '%.2f' % (item['market_value'] / tw_total_market_value * 100) if item['price'] != 'N/A' and tw_total_market_value > 0 else 'N/A' }}%</td>
                <td style="color: {% if item['price'] != 'N/A' and item['profit_pct'] > 0 %}red{% elif item['price'] != 'N/A' and item['profit_pct'] < 0 %}green{% else %}black{% endif %}; font-weight: bold;">
                {{ '%.2f' % item['profit_pct'] if item['price'] != 'N/A' else 'N/A' }}%
                </td>
            </tr>
            {% endfor %}
            </table>


            <div class="summary">
                <h3>台股投資組合摘要</h3>
                <div class="summary-row">
                    <span class="summary-label">台股總市值:</span>
                    <span class="summary-value">{{ '%.0f' % tw_total_market_value }} TWD</span>
                </div>
                <div class="summary-row">
                    <span class="summary-label">台股總成本:</span>
                    <span class="summary-value">{{ '%.0f' % tw_total_cost }} TWD</span>
                </div>
                <div class="summary-row">
                    <span class="summary-label">台股總報酬:</span>
                    <span class="summary-value" style="color: {% if tw_total_profit_pct > 0 %}red{% elif tw_total_profit_pct < 0 %}green{% else %}black{% endif %};">
                        {{ '%.0f' % tw_total_profit }} TWD ({{ '%.2f' % tw_total_profit_pct }}%)
                    </span>
                </div>
                <div class="summary-row">
                    <span class="summary-label">台灣50 今年以來績效（0050）:</span>
                    <span class="summary-value" style="color: {{ tw50_color }};">{{ tw50_ytd_str }}</span>
                </div>
            </div>
        </div>
    </body>
    </html>
    '''
    return render_template_string(
        html,
        # 原本變數
        us_portfolio=us_portfolio,
        tw_portfolio=tw_portfolio,
        us_total_market_value=us_total_market_value,
        tw_total_market_value=tw_total_market_value,
        us_total_cost=us_total_cost,
        tw_total_cost=tw_total_cost,
        us_total_profit=us_total_profit,
        tw_total_profit=tw_total_profit,
        us_total_profit_pct=us_total_profit_pct,
        tw_total_profit_pct=tw_total_profit_pct,
        total_market_value_twd=total_market_value_twd,
        total_cost_twd=total_cost_twd,
        total_profit_twd=total_profit_twd,
        total_profit_pct=total_profit_pct,
        exchange_rate=exchange_rate,
        sp500_ytd_str=sp500_ytd_str,
        sp500_color=sp500_color,
        tw50_ytd_str=tw50_ytd_str,
        tw50_color=tw50_color,
        # 切換用變數
        hide_etf=hide_etf,
        us_table=us_table,
        us_denominator=us_denominator,
        # 自選股摘要
        us_core_total_market_value=us_core_total_market_value,
        us_core_total_cost=us_core_total_cost,
        us_core_total_profit=us_core_total_profit,
        us_core_total_profit_pct=us_core_total_profit_pct
    )


# --------------------- 入口 ---------------------
# 修改後的程式碼
if __name__ == '__main__':
    # Render 會自動設定 PORT 環境變數
    # 在本機執行時，我們預設用 5000
    import os
    port = int(os.environ.get('PORT', 5000))
    # 將 host 設為 '0.0.0.0' 讓外部可以連線
    # 注意：debug 模式在正式部署時建議關閉
    app.run(host='0.0.0.0', port=port, debug=False)