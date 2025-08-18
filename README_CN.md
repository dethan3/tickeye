# 🦉 TickEye

**TickEye** 是一个轻量级的基金监测工具，用于跟踪您购买的基金并使用 AkShare API 提供每日表现分析。

[English README](README.md)

## 📌 功能特性

- **基金与指数追踪**：同时监控基金与主流指数（全球与中国）
- **实时指数**：全球指数使用 `index_global_spot_em`；中国指数使用 `stock_zh_index_spot_em`（默认展示当日实时，失败回退到日线历史）
- **灵活配置**：通过 `funds_config.json` 配置（同时支持基金与指数）
- **智能名称解析**：当未提供基金名称时，自动通过 API 获取
- **表现分析**：每日净值/点位与涨跌幅跟踪
- **多项目支持**：同时监测多只基金/多个指数
- **美观输出**：带有趋势指标的精美控制台输出 (📈📉➡️)

---

## ⚙️ 技术栈

| 组件         | 技术/工具                    |
|-------------|------------------------------|
| 编程语言      | Python 3.8+                  |
| 数据获取      | AkShare API                   |
| 数据处理      | pandas                        |
| HTTP 客户端   | requests                      |
| 配置解析      | JSON 文件解析                  |

---

## 🚀 快速开始

### 环境要求

- Python 3.8 或更高版本
- 互联网连接（用于 API 访问）

### 1. 克隆仓库

```bash
git clone https://github.com/yourusername/tickeye.git
cd tickeye
```

### 2. 创建虚拟环境（推荐）

```bash
python -m venv tickeye_env
source tickeye_env/bin/activate  # Windows 系统: tickeye_env\Scripts\activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置基金/指数

使用 `funds_config.json` 配置基金与指数：

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

说明：
- 基金使用 6 位数代码（如 `001917`）。
- 中国指数可用别名 `000001`（内部映射到 `sh000001`），或直接使用 `sh000001`/`sz399001`。
- 全球指数使用如 `HSI`、`NDX`、`SPX`、`VNINDEX` 等代码。
- `name` 可留空；留空时程序将通过 API/配置自动解析名称。
- 可在 `indices_config.json` 中新增/调整指数别名映射。

### 5. 运行监测

```bash
# 监测 1 天（默认）；指数默认显示当日实时
python fund_analysis.py

# 请求多天历史（基金使用历史；指数仍默认优先实时）
python fund_analysis.py 7
```

### 6. 理解输出结果

报告包含：

- **代码与名称**：包含基金与指数；名称自动解析
- **最新日期**：最近交易日；当走实时指数时为当前时间戳
- **净值/点位**：基金单位净值或指数点位
- **涨跌幅**：日涨跌幅（指数实时为盘中涨跌；历史为收盘对前一日收盘）
- **趋势**：📈 上涨，📉 下跌，➡️ 平盘
- **汇总**：整体统计与成功率

### 7. 配置技巧

- **智能名称解析**：工具优先使用 API 获取的名称（最准确）
- **错误处理**：无效的基金代码会自动跳过并显示错误信息
- **灵活格式**：可在同一配置文件中混合使用 `基金代码|名称` 和 `基金代码` 格式
- **注释支持**：使用 `#` 在配置文件中添加注释和说明

---

## 🔧 技术特性

### 智能名称解析

程序采用以下优先级获取基金名称：

1. **优先使用 AkShare API** 获取的基金名称（最准确）
2. **如果 API 获取失败**，使用配置文件中的名称作为备选
3. **如果都失败**，返回基金代码本身

### 数据获取

- 基金：`fund_open_fund_info_em`
- 全球指数：`index_global_spot_em`
- 中国指数：优先 `stock_zh_index_spot_em`，回退 `stock_zh_index_daily`
- 自动处理数据清洗与格式转换，支持历史数据获取（可指定天数）

### 错误处理

- 完善的错误提示和格式验证
- 基金代码格式检查
- API 调用失败的优雅降级

---

## 📄 许可证

[MIT License](LICENSE)

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📞 联系

如有问题或建议，请通过 GitHub Issues 联系。
