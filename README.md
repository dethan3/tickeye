# 🦉 TickEye

**TickEye** is a lightweight, no-frontend fund monitoring tool that tracks your purchased funds and provides daily performance analysis using AkShare API.

[中文版 README](README_CN.md)

## 📌 Features

- **Fund Data Fetching**: Real-time fund data using AkShare API
- **Flexible Configuration**: Support both `fund_code|fund_name` and `fund_code` only formats
- **Smart Name Resolution**: Automatically fetch fund names via API when not provided
- **Performance Analysis**: Daily net value and percentage change tracking
- **Multi-fund Support**: Monitor multiple funds simultaneously
- **Clean Output**: Beautiful console output with trend indicators (📈📉➡️)

---

## 🧱 Project Structure

```sh
tickeye/
├── fund_analysis.py      # ✅ Main fund analysis tool
├── funds_config.txt      # ✅ Fund configuration file
├── monitor/
│   ├── __init__.py
│   ├── fetcher.py        # 🚧 Fund data fetcher (legacy)
│   ├── rules.py          # 🚧 Monitoring rules
│   └── notifier.py       # 🚧 Notification sender
├── config/
│   └── settings.yaml     # 🚧 Configuration file
├── utils/
│   └── logger.py         # 🚧 Logging utility
├── requirements.txt      # ✅ Python dependencies
└── README.md             # ✅ Project documentation
````

---

## ⚙️ Tech Stack

| Component         | Tech / Tool                  |
|------------------|------------------------------|
| Language          | Python 3.8+                  |
| HTTP Client       | `requests`                   |
| Task Scheduling   | `schedule` or `apscheduler`  |
| Config Parsing    | `PyYAML`                     |
| Data Fetching     | Public APIs / Web scraping   |
| Notification      | Feishu (Lark) Bot Webhook    |
| Logging           | Python `logging` module      |

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Your Funds

Create or edit `funds_config.txt` with your fund codes:

```txt
# Format 1: fund_code|fund_name
270042|广发纳指联接A
007360|易方达中短期美元债A

# Format 2: fund_code only (name auto-fetched)
001917
006195
```

### 3. Run Fund Analysis

```bash
`source tickeye_env/bin/activate`

# Monitor funds for 1 day (default)
python fund_analysis.py

# Monitor funds for multiple days
python fund_analysis.py 7
```

### 4. Sample Output

```txt
🦉 TickEye 基金监测工具
====================================================================================================
📋 正在监测 6 只已购买基金...
📅 数据日期: 最近 1 天

====================================================================================================
📊 已购买基金监测报告
====================================================================================================
基金代码     基金名称                                最新日期         单位净值       涨跌幅        趋势   状态        
----------------------------------------------------------------------------------------------------
007360   易方达中短期美元债券（QDII）A(人民币份额)            2025-08-04   1.2049     0.00%      ➡️   正常        
001917   招商量化精选股票A                           2025-08-05   3.1937     0.98%      📈    正常        
270042   广发纳指100ETF联接（QDII）人民币A              2025-08-04   6.8615     1.67%      📈    正常        
----------------------------------------------------------------------------------------------------
📈 上涨: 2 只  📉 下跌: 0 只  ➡️ 平盘: 1 只  ❌ 失败: 0 只
📊 上涨比例: 66.7%

✅ 基金监测完成!
```

---

## 📌 Future Plans

* SQLite/CSV data logging
* Historical trend analysis
* Telegram/Bark/Server酱 as alternative push channels
* Optional Flask Web Dashboard

---

## 📄 License

[MIT License](LICENSE)