# 🦉 TickEye

**TickEye** is a lightweight, no-frontend fund monitoring tool that tracks your purchased funds and provides daily performance analysis using AkShare API.

[中文版 README](README_CN.md)

## 🐳 Docker Deployment

### Quick Start with Docker

```bash
# Clone the repository
git clone https://github.com/yourusername/tickeye.git
cd tickeye

# Build and run with Docker Compose
docker-compose up -d

# Run manually
docker build -t tickeye .
docker run -d --name tickeye-fund-monitor tickeye
```

### Environment Variables

Create a `.env` file for configuration:

```bash
# Feishu notification configuration
FEISHU_WEBHOOK_URL=your_webhook_url_here
FEISHU_ENABLED=true

# Log level
LOG_LEVEL=INFO
```

### Docker Configuration

The Docker setup includes:
- Multi-stage build for smaller image size
- Non-root user for security
- Health checks
- Environment variable support
- Volume mounting for configuration files

```bash
# View logs
docker-compose logs -f tickeye

# Stop the service
docker-compose down

# Rebuild and restart
docker-compose up -d --build
```

## 📌 Features

- **Fund & Index Tracking**: Monitor your funds and major indices (global and China)
- **Real-time Indices**:  
  - Combined support for China and major global indices, with built-in retry and fallback logic to reduce `N/A` values
- **Flexible Configuration**: Configure items in `funds_config.json` (supports funds and indices)
- **Smart Name Resolution**: Automatically fetch fund names via API when not provided
- **Performance Analysis**: Daily net value and percentage change tracking
- **Multi-item Support**: Monitor multiple funds/indices simultaneously
- **Clean Output**: Beautiful console output with trend indicators (📈📉➡️)

---

## ⚙️ Tech Stack

| Component         | Tech / Tool                  |
|------------------|------------------------------|
| Language          | Python 3.8+                  |
| Data Source       | AkShare API                   |
| Data Processing   | pandas                        |
| HTTP Client       | requests                      |
| Config Parsing    | JSON file parsing             |

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

### 4. Configure Your Items

Use `funds_config.json` to configure funds and indices:

```json
{
  "items": [
    {"code": "007360", "name": "易方达中短期美元债A"},
    {"code": "001917", "name": "招商量化精选股票A"},

    {"code": "000001", "name": ""},           
    {"code": "HSI", "name": "恒生指数"},      
    {"code": "NDX", "name": "纳斯达克"},      
    {"code": "SPX", "name": "标普500"}
  ]
}
```

Notes:
- For funds, use the 6-digit code (e.g., `001917`).
- For China indices, you can use alias `000001` (mapped to `sh000001` internally) or direct symbol `sh000001`/`sz399001`.
- For global indices, use tickers like `HSI`, `NDX`, `SPX`, or other symbols you configure in `indices_config.json`.
- `name` is optional; when empty, the tool will resolve via API/config.
- Optional: you can add/adjust index aliases in `indices_config.json`.

### Data Sources

- **Funds**  
  - Uses AkShare to fetch historical net asset values and basic fund information, with in-memory caching of fund names to reduce repeated API calls.

- **Indices**  
  - China indices prefer intraday snapshots and automatically fall back to recent daily history when intraday data is unavailable.  
  - Global indices support key benchmarks (such as HSI, SPX, NDX) with robust retry / fallback handling; other indices degrade gracefully and may display `N/A` when upstream data providers are unstable.

### Index Coverage & Limitations

- The default configuration in `funds_config.json` monitors a small set of funds plus several major indices (e.g., Shanghai Composite, HSI, NDX, SPX).  
- Additional indices can be added, but data availability ultimately depends on upstream data providers; some symbols may occasionally return `N/A` or sparse history.  
- The tool is designed to **fail gracefully**: when an index cannot be retrieved, it is reported as `N/A` with logging, without breaking the overall report.

### Adding or Extending Indices

- To monitor a new index:
  1. (Optional) Add or adjust its alias in `indices_config.json` so that a short code (e.g., `HSI`, `SPX`) maps to the correct underlying symbol and display name.  
  2. Add the index code to the `items` list in `funds_config.json`, alongside your funds.
- Different global indices may be supported to different degrees by upstream data sources; if a newly added symbol does not appear in the report or shows `N/A`, check the logs to see whether the data provider returned anything for that code.

### 5. Run Fund/Index Analysis

```bash
# Monitor for 1 day (default); indices default to same-day spot
python fund_analysis.py

# Request multiple days of history (funds use history; indices still prefer spot by default)
python fund_analysis.py 7
```

### 6. Understanding the Output

The tool provides a comprehensive report with:

- **Code & Name**: Funds and indices; names auto-resolved
- **Latest Date**: Most recent trading date or current timestamp for spot indices
- **Net Value / Spot**: Unit NAV (fund) or index level
- **Change %**: Daily percentage change (spot for indices; close-to-close for history)
- **Trend**: Visual indicators (📈 up, 📉 down, ➡️ flat)
- **Summary**: Overall statistics and success rate

### 7. Configuration Tips

- **Smart Name Resolution**: The tool prioritizes API-fetched names over config file names for accuracy
- **Error Handling**: Invalid fund codes are automatically skipped with error messages
- **Flexible Format**: Mix both `code|name` and `code` formats in the same config file
- **Comments**: Use `#` for comments and documentation in your config file

---

## 📄 License

[MIT License](LICENSE)
