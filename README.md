# 🦉 TickEye

**TickEye** is a lightweight, no-frontend fund/index monitoring tool that periodically tracks selected financial instruments and sends alerts to your mobile device via Feishu Bot (Lark Bot).

## 📌 Features

- Periodically fetch fund/index data
- Rule-based alerting system (e.g. price thresholds, % change)
- Feishu Bot integration for real-time mobile notifications
- Simple configuration via YAML
- Extensible design for future features (data logging, web UI, etc.)

---

## 🧱 Project Structure

```sh
tickeye/
├── main.py               # Entry point
├── monitor/
│   ├── **init**.py
│   ├── fetcher.py        # Fund/index data fetcher
│   ├── rules.py          # Monitoring rules
│   └── notifier.py       # Feishu message sender
├── config/
│   └── settings.yaml     # Fund codes and thresholds
├── utils/
│   └── logger.py         # Logging utility
├── requirements.txt      # Python dependencies
└── README.md             # Project introduction
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

> (To be updated as code is written)

1. Clone the repo
2. Add your config in `config/settings.yaml`
3. Install dependencies:  
   `pip install -r requirements.txt`
4. Run the monitor:

```sh
python main.py
```

---

## 📌 Future Plans

* SQLite/CSV data logging
* Historical trend analysis
* Telegram/Bark/Server酱 as alternative push channels
* Optional Flask Web Dashboard

---

## 📄 License

MIT License

# TickEye 项目状态总结

## 项目概述

我正在开发 TickEye - 一个轻量级的基金/指数监控工具，主要功能包括：

1. 定时监控基金净值和涨跌幅数据
2. 基于自定义规则的智能预警（如跌幅超过3%）
3. 通过飞书Bot推送实时通知
4. 纯后端服务，通过YAML配置文件管理
5. 技术栈： Python + AkShare + Pandas + PyYAML + 飞书API

✅ 已完成的模块
1. 数据获取模块 (monitor/fetcher.py)
✅ 功能完整：使用AkShare获取开放式基金和ETF数据
✅ 智能缓存：5分钟多层缓存策略，避免重复API调用
✅ 动态字段映射：自动适配AkShare的字段名变化（如2025-07-23-单位净值、日增长率等）
✅ 性能优化：支持少量基金监控模式，智能识别监控规模
✅ 测试验证：已通过完整测试，数据获取正常

2. 规则引擎 (monitor/rules.py)
✅ 架构设计：抽象基类Rule + 具体规则实现
✅ 核心规则：
PercentageDropRule - 跌幅监控（支持全市场或特定基金）
PriceThresholdRule - 净值阈值监控
✅ 配置驱动：支持从YAML配置加载规则
✅ 扩展性强：易于添加新的监控规则类型

3. 配置管理
✅ 依赖管理 (requirements.txt)：完整的包依赖列表
✅ 配置模板 (config/settings.yaml)：规则配置、飞书Bot、调度等
✅ 虚拟环境：已配置 tickeye_env 环境

🚧 待开发模块
1. 通知模块 (monitor/notifier.py) - 优先级：高
飞书Bot Webhook集成
消息格式化和发送
错误重试机制
2. 主程序 (main.py) - 优先级：高
整合fetcher、rules、notifier
任务调度（schedule/apscheduler）
程序入口点
3. 集成测试 - 优先级：中
端到端功能验证
规则触发测试
飞书消息发送测试
🔧 关键技术问题已解决
AkShare字段适配：解决了字段名不匹配问题（单位净值 vs 2025-07-23-单位净值）
性能优化：虽然API限制需要全量获取，但通过缓存大幅提升效率
数据清洗：处理空值、百分号、数据类型转换等边界情况
📁 当前项目结构
tickeye/
├── monitor/
│   ├── fetcher.py      ✅ 完成
│   ├── rules.py        ✅ 完成  
│   └── notifier.py     🚧 待开发
├── config/
│   └── settings.yaml   ✅ 完成
├── requirements.txt    ✅ 完成
├── main.py            🚧 待开发
└── tickeye_env/       ✅ 环境配置
🎯 下一步开发计划
开发 notifier.py - 实现飞书Bot消息推送
集成测试 rules.py - 验证规则引擎与数据获取的集成
开发 
main.py
 - 创建完整的监控流程
端到端测试 - 验证整体功能
💡 开发环境说明
项目路径: /home/evan/tickeye
Python版本: 3.10.13 (已验证兼容)
虚拟环境: source tickeye_env/bin/activate
测试命令: python monitor/fetcher.py (已测试通过)
请帮我继续开发TickEye项目，重点关注通知模块和主程序的实现。