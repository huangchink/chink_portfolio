from flask import Flask, render_template_string
import yfinance as yf

app = Flask(__name__)

etf_symbols = [
    {'名稱': 'SGOV', '類型': '國庫券', '內扣費': '0.07%'},
    {'名稱': 'SHY', '類型': '短債', '內扣費': '0.15%'},
    {'名稱': 'VGSH', '類型': '短債', '內扣費': '0.04%'},
    {'名稱': 'IEI', '類型': '中長期債', '內扣費': '0.15%'},
    {'名稱': 'VGIT', '類型': '中長期債', '內扣費': '0.04%'},
    {'名稱': 'IEF', '類型': '中長期債', '內扣費': '0.15%'},
    {'名稱': 'TLT', '類型': '長債', '內扣費': '0.15%'},
]

etf_intro = {
    'SGOV': 'iShares 0-3 Month Treasury Bond ETF，追蹤美國0-3個月國庫券，風險極低，流動性高。',
    'SHY': 'iShares 1-3 Year Treasury Bond ETF，追蹤美國1-3年期國債，風險低，適合保守型投資人。',
    'VGSH': 'Vanguard Short-Term Treasury ETF，追蹤1-3年期美國國債。',
    'IEI': 'iShares 3-7 Year Treasury Bond ETF，追蹤3-7年期美國國債，利率敏感度適中。',
    'VGIT': 'Vanguard Intermediate-Term Treasury ETF，追蹤3-10年期美國國債。',
    'IEF': 'iShares 7-10 Year Treasury Bond ETF，追蹤7-10年期美國國債，利率敏感度較高。',
    'TLT': 'iShares 20+ Year Treasury Bond ETF，追蹤20年以上美國國債，利率敏感度高，波動較大。'
}

def get_etf_data():
    etfs = []
    for etf in etf_symbols:
        symbol = etf['名稱']
        ticker = yf.Ticker(symbol)
        data = ticker.history(period='1d')
        price = data['Close'].iloc[-1] if not data.empty else 'N/A'
        pct = ((data['Close'].iloc[-1] - data['Open'].iloc[-1]) / data['Open'].iloc[-1] * 100) if not data.empty else 'N/A'
        if pct != 'N/A':
            color = 'red' if pct > 0 else ('green' if pct < 0 else 'black')
        else:
            color = 'black'
        etfs.append({
            '名稱': symbol,
            '類型': etf['類型'],
            '內扣費': etf['內扣費'],
            '簡介': etf_intro[symbol],
            '現價': f"{price:.2f}" if price != 'N/A' else 'N/A',
            '漲跌幅': f"{pct:.2f}%" if pct != 'N/A' else 'N/A',
            'color': color
        })
    return etfs

@app.route('/')
def index():
    etfs = get_etf_data()
    html = '''
    <html>
    <head>
        <title>債券ETF介紹</title>
        <meta charset="utf-8">
        <style>
            body { font-family: "微軟正黑體", Arial, sans-serif; background: #f8f9fa; }
            .container { max-width: 1000px; margin: 40px auto; background: #fff; padding: 32px; border-radius: 12px; box-shadow: 0 2px 8px #ccc; }
            h1 { text-align: center; color: #2c3e50; }
            table { width: 100%; border-collapse: collapse; margin-top: 24px; }
            th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
            th { background: #e9ecef; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>債券ETF介紹</h1>
            <table>
                <tr>
                    <th>名稱</th>
                    <th>類型</th>
                    <th>現價</th>
                    <th>當日漲跌幅</th>
                    <th>內扣費</th>
                    <th>簡介</th>
                </tr>
                {% for etf in etfs %}
                <tr>
                    <td>{{ etf['名稱'] }}</td>
                    <td>{{ etf['類型'] }}</td>
                    <td style="color: {{ etf['color'] }}; font-weight: bold;">{{ etf['現價'] }}</td>
                    <td style="color: {{ etf['color'] }}; font-weight: bold;">{{ etf['漲跌幅'] }}</td>
                    <td>{{ etf['內扣費'] }}</td>
                    <td>{{ etf['簡介'] }}</td>
                </tr>
                {% endfor %}
            </table>
        </div>
    </body>
    </html>
    '''
    return render_template_string(html, etfs=etfs)

if __name__ == '__main__':
    app.run(debug=True)