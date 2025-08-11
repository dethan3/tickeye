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

## ⚙️ Tech Stack

| Component         | Tech / Tool                  |
|------------------|------------------------------|
| Language          | Python 3.8+                  |
| Data Source       | AkShare API                   |
| Data Processing   | pandas                        |
| HTTP Client       | requests                      |
| Config Parsing    | Text file parsing             |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- Internet connection for API access

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/tickeye.git
cd tickeye
```

### 2. Create Virtual Environment (Recommended)

```bash
python -m venv tickeye_env
source tickeye_env/bin/activate  # On Windows: tickeye_env\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Your Funds

Create or edit `funds_config.txt` with your fund codes:

```txt
# Format 1: fund_code|fund_name (name will be auto-updated from API)
270042|广发纳指联接A
007360|易方达中短期美元债A

# Format 2: fund_code only (name auto-fetched from API)
001917
006195

# Comments and empty lines are supported
# 159915  # This is a comment
```

### 5. Run Fund Analysis

```bash
# Monitor funds for 1 day (default)
python fund_analysis.py

# Monitor funds for multiple days
python fund_analysis.py 7

# Monitor funds for 30 days
python fund_analysis.py 30
```

### 6. Understanding the Output

The tool provides a comprehensive report with:

- **Fund Code & Name**: Automatically fetched latest fund names
- **Latest Date**: Most recent trading date
- **Net Value**: Current unit net value
- **Change %**: Daily percentage change
- **Trend**: Visual indicators (📈 up, 📉 down, ➡️ flat)
- **Status**: Fund status (normal/error)
- **Summary**: Overall statistics and success rate

### 7. Configuration Tips

- **Smart Name Resolution**: The tool prioritizes API-fetched names over config file names for accuracy
- **Error Handling**: Invalid fund codes are automatically skipped with error messages
- **Flexible Format**: Mix both `code|name` and `code` formats in the same config file
- **Comments**: Use `#` for comments and documentation in your config file

---

## 📄 License

[MIT License](LICENSE)