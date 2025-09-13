import yfinance as yf

# 投資組合資料：ETF代碼、持有股數、總成本
portfolio = [
    {'symbol': 'VOO', 'shares': 68.65, 'cost': 505.08},
    {'symbol': 'SPMO', 'shares': 60, 'cost': 114.2},
    {'symbol': 'VEA', 'shares': 83.40, 'cost': 53.32},
    {'symbol': 'GLD', 'shares': 15.9, 'cost': 299.8},
    {'symbol': 'TLT', 'shares': 224.7, 'cost': 92.22},
    # 台股ETF
    {'symbol': '0050.TW', 'shares': 10637, 'cost': 41.58},
    {'symbol': '006208.TW', 'shares': 9000, 'cost': 112.67},
]

total_market_value = 0
for item in portfolio:
    ticker = yf.Ticker(item['symbol'])
    price = ticker.history(period='1d')['Close'].iloc[-1]
    market_value = price * item['shares']
    item['price'] = price
    item['market_value'] = market_value
    item['profit'] = market_value - item['cost'] * item['shares']
    item['profit_pct'] = item['profit'] / (item['cost'] * item['shares']) * 100
    total_market_value += market_value

total_cost = sum(item['cost'] * item['shares'] for item in portfolio)
total_profit = sum(item['profit'] for item in portfolio)
total_profit_pct = total_profit / total_cost * 100

print(f"{'ETF':<6}{'現價':>10}{'持有股數':>10}{'市值':>12}{'佔比':>8}{'個別報酬率':>14}")
for item in portfolio:
    percent = item['market_value'] / total_market_value * 100
    print(f"{item['symbol']:<6}{item['price']:>10.2f}{item['shares']:>10.2f}{item['market_value']:>12.2f}{percent:>7.2f}%{item['profit_pct']:>13.2f}%")

print(f"\n投資組合總市值: {total_market_value:.2f}")
print(f"投資組合總成本: {total_cost:.2f}")
print(f"投資組合總報酬: {total_profit:.2f} ({total_profit_pct:.2f}%)")

