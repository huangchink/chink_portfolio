import matplotlib.pyplot as plt

# --- 資料準備 ---
# 從您的圖片中整理出的投資組合數據
portfolio_data = {
    '台股': 3142993.46,
    '債券': 1944336.21,
    '標普500': 1327604.72,
    '科技股': 1123226.26,
    '防禦性資產': 519406.99,
    '電力股': 510026.92,
    '台美以外全球分散': 376641.86,
    '黃金': 196556.49,
    '比特幣': 53556.44
}

# 準備圖表的標籤和對應的數值
labels = portfolio_data.keys()
sizes = portfolio_data.values()

# --- 繪製圓餅圖 ---

# 設定字體以正確顯示中文 (在 Windows/macOS 上常見的字體)
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'PingFang TC', 'Heiti TC']
plt.rcParams['axes.unicode_minus'] = False  # 修正負號顯示問題

# 建立一個圖表
fig, ax = plt.subplots(figsize=(10, 8))

# 繪製圓餅圖
# autopct='%1.1f%%' 會將百分比顯示到小數點後一位
# startangle=90 讓圖表從90度角開始繪製，視覺上更整齊
wedges, texts, autotexts = ax.pie(sizes, autopct='%1.1f%%', startangle=140,
                                  textprops=dict(color="w")) # 設定百分比文字為白色

# 設定圖例 (Legend)
ax.legend(wedges, labels,
          title="投資項目",
          loc="center left",
          bbox_to_anchor=(1, 0, 0.5, 1))

# 設定圖表標題
ax.set_title("投資組合分佈圓餅圖", fontsize=16, pad=20)

# 確保圓餅圖是圓形的
ax.axis('equal')

# 顯示圖表
plt.show()