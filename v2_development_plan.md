# TickEye V2 Web MVP 开发计划

| 字段 | 内容 |
|------|------|
| 文档性质 | 技术方案与执行计划 |
| 版本 | 0.1 |
| 日期 | 2026-08-21 |
| 状态 | Ready for implementation |
| 产品依据 | `v2_product.md` |

---

## 1. 开发目标

V2 MVP 要交付一个可以在本地运行的个人投资风险工作台，完成下面的最小闭环：

```text
录入资产与持仓
      │
      ▼
获取并验证市场数据
      │
      ▼
形成可解释的组合风险状态
      │
      ▼
创建“不操作 / 买入 / 卖出 / 调整权重”方案
      │
      ▼
比较操作前后的风险结构与数据可信度
```

MVP 完成的判断标准不是“页面已经打开”，而是用户可以回答：

> 我的组合目前最需要关注什么风险？这个判断使用了哪些数据？如果执行我提出的方案，风险结构会怎样变化？

---

## 2. 已确定的工程边界

### 2.1 本阶段采用

- 单用户、本地优先，不建设注册、登录和多租户系统。
- FastAPI API 服务默认只监听本机地址；如果未来允许远程访问，必须先增加认证和访问控制。
- 前端采用独立 React 单页应用，不使用 Jinja2 或其他服务端页面模板。
- 开发时分别运行 Vite 前端和 FastAPI 后端；本地发布时由 FastAPI 托管 Vite 构建后的静态文件，不额外部署 Nginx。
- 采用模块化单体后端，不拆微服务。
- 核心业务逻辑与前端、未来 IM 和 Agent 渠道分离。
- SQLite 保存个人数据，使用迁移工具管理数据库结构。
- 市场数据由用户手动刷新；当前不恢复 GitHub Actions 或其他自动调度。
- 所有金额默认以人民币为组合基准币种。MVP 支持人民币计价的基金、ETF、QDII 基金和现金；直接外币资产换算后置。
- 现有 v1 在迁移期间只作为数据获取行为参考，不作为 V2 领域模型的基础。

### 2.2 本阶段不做

- 交易与现金流账本。
- 真实账户收益、TWR、XIRR、收益归因和决策增量价值。
- 基金推荐、机会发现和候选标的排序。
- 自动下单、券商或银行连接。
- 完整投资者画像、适当性和商业化边界。
- 多用户、机构权限、云端部署和实时流式行情。
- IM 通知和 Agent 工具实现；MVP 只保留稳定 API 边界。
- 自动定时刷新和 CI/CD；开发阶段先使用本地命令验证。

---

## 3. 技术选型

| 层次 | 选择 | 原因 |
|------|------|------|
| 后端运行时 | Python 3.11+ | 延续现有 AkShare、pandas 资产，并使用现代类型能力 |
| Backend API | FastAPI | 只提供 `/api/v1`、OpenAPI 和构建后静态文件托管，不渲染业务页面 |
| Frontend | React + TypeScript | 独立建设风险工作台和交互体验，组件与 API 类型可检查 |
| 前端构建 | Vite + pnpm | 开发反馈快，正式产物为可由 FastAPI 托管的静态文件 |
| 路由与服务端状态 | React Router + TanStack Query | 页面路由与 API 缓存、刷新、错误和 mutation 生命周期分开管理 |
| API 类型 | FastAPI OpenAPI → TypeScript 类型生成 | 后端模型是契约源，避免前后端手写两套响应类型 |
| 图表 | ECharts，本地固定版本静态资源 | 支持权重、回撤和风险对比图，不依赖运行时 CDN |
| 数据库 | SQLite | 适合单用户本地工具，备份和迁移成本低 |
| ORM/迁移 | SQLAlchemy 2.x + Alembic | 显式模型和版本化迁移，未来可切换 PostgreSQL |
| 数据分析 | pandas + NumPy | 价格序列对齐、收益序列和风险指标计算 |
| 数据源 | AkShare 适配器 + CSV/手工输入 | 复用现有经验，但统一输出数据和错误语义 |
| 后端测试 | pytest + FastAPI TestClient | 覆盖纯计算、数据库、provider 和 API 集成 |
| 前端测试 | Vitest + Testing Library + Playwright | 覆盖组件状态、API 交互和关键用户路径 |
| 工程质量 | Ruff + mypy + ESLint + TypeScript | 分别检查 Python 与前端类型和代码质量 |

Python 依赖统一迁移到 `pyproject.toml`，前端依赖由 `frontend/package.json` 和 `pnpm-lock.yaml` 管理。生产依赖和开发依赖分组，锁定可复现版本后再开始功能开发。

---

## 4. 总体架构

```text
Browser
  │
  ▼
React SPA ──────────────── Future Agent / Future IM
  │ JSON /api/v1                         │
  └──────────────────┬───────────────────┘
                     ▼
                FastAPI Routes
                     │
                     ▼
            Application Services
         ┌───────────┼───────────────┐
         ▼           ▼               ▼
     Portfolio   Risk Analysis   Scenario Evaluation
         │           │               │
         └───────────┼───────────────┘
                     ▼
               Domain Model
    Instrument / Position / Policy / Risk State / Evidence
                     │
             ┌───────┴────────┐
             ▼                ▼
      SQLAlchemy Repos   MarketDataProvider
             │                │
             ▼          ┌─────┴─────┐
          SQLite      AkShare      CSV
```

核心约束：

1. FastAPI 路由只负责输入校验、调用服务和返回 JSON，不能计算风险。
2. 风险计算使用纯函数和明确输入，不能直接访问数据库或网络。
3. 数据源适配器只返回标准化数据或结构化失败，不能把缺失值伪装成 `0`。
4. 实际组合、目标配置和 Scenario 分开持久化；Scenario 永不覆盖实际持仓。
5. React 只能通过 `/api/v1` 访问数据，不能接触 SQLite 或复制后端风险算法。
6. OpenAPI 是前后端契约源；生成类型有差异时构建失败，不能用前端手写类型掩盖。

本地运行拓扑：

```text
开发：Browser → Vite :5173 → FastAPI :8000 → data/tickeye.db
构建：Browser → FastAPI :8000 → frontend/dist + /api/v1 → data/tickeye.db
```

---

## 5. 建议目录结构

```text
tickeye/
├── pyproject.toml
├── alembic.ini
├── migrations/
├── frontend/
│   ├── package.json
│   ├── pnpm-lock.yaml
│   ├── vite.config.ts
│   ├── src/
│   │   ├── api/
│   │   ├── app/
│   │   ├── components/
│   │   ├── features/
│   │   │   ├── portfolio/
│   │   │   ├── risk/
│   │   │   ├── scenarios/
│   │   │   └── watchlists/
│   │   └── routes/
│   └── tests/
│       ├── unit/
│       └── e2e/
├── src/tickeye/
│   ├── __init__.py
│   ├── config.py
│   ├── cli.py
│   ├── domain/
│   │   ├── enums.py
│   │   ├── models.py
│   │   ├── risk.py
│   │   └── scenario.py
│   ├── application/
│   │   ├── portfolio_service.py
│   │   ├── market_data_service.py
│   │   ├── risk_service.py
│   │   └── scenario_service.py
│   ├── infrastructure/
│   │   ├── db/
│   │   ├── repositories/
│   │   └── market_data/
│   └── web/
│       ├── app.py
│       ├── api/
│       └── static_app.py
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   └── fixtures/
└── data/
    └── .gitkeep
```

`data/` 中的数据库、导入文件和用户持仓数据，以及 `frontend/node_modules/`、`frontend/dist/`，必须加入 `.gitignore`，不能提交到仓库。

---

## 6. MVP 数据模型

### 6.1 核心表

| 模型 | 关键字段 | 说明 |
|------|----------|------|
| `Profile` | `id`, `name`, `base_currency` | MVP 只有一个本地用户，但保留明确的数据归属根节点 |
| `Instrument` | `code`, `name`, `type`, `market`, `currency`, `asset_class`, `region` | 标的事实，不保存 held/watched/planned 状态 |
| `Account` | `profile_id`, `name`, `institution`, `currency` | 资产所在账户 |
| `Position` | `account_id`, `instrument_id`, `quantity`, `manual_value`, `cost`, `as_of` | 当前持仓；数量或手工市值至少存在一个 |
| `PositionSnapshot` | `captured_at`, `source`, `payload_hash` | 保存一次完整持仓事实，支持恢复和变化解释 |
| `TargetAllocation` | `profile_id`, `subject_type`, `subject_id`, `target_weight`, `tolerance` | 目标可以针对标的或资产类别 |
| `Watchlist` / `WatchlistItem` | 分组、标的、理由、标签 | 与实际持仓保持独立关系 |
| `MarketObservation` | `instrument_id`, `date`, `value`, `value_type`, `source`, `fetched_at` | 标准化净值、复权价格或指数值 |
| `PolicyRule` | `rule_type`, `subject`, `threshold`, `warning_ratio`, `enabled` | 只实现集中度、现金下限和目标偏离 |
| `Scenario` | `name`, `status`, `created_at`, `assumptions` | 未执行的方案容器 |
| `ScenarioOperation` | `instrument_id`, `operation_type`, `amount`, `estimated_cost` | 买、卖、加仓、减仓或目标权重调整 |
| `RiskSnapshot` | `portfolio_as_of`, `calculated_at`, `state`, `coverage`, `methodology_version` | 一次不可变风险分析结果 |
| `RiskFinding` | `dimension`, `state`, `current_value`, `boundary`, `contributors`, `evidence` | 可解释的单项风险结论 |
| `InsightEvent` | `event_type`, `severity`, `dedupe_key`, `occurred_at`, `risk_snapshot_id` | 风险突破、恢复或数据质量变化 |

### 6.2 三种组合的实现

```text
Actual Portfolio
  = Account + current Positions

Target Portfolio
  = TargetAllocations

Scenario Portfolio
  = immutable copy of Actual Portfolio
    + ordered ScenarioOperations
```

Scenario 计算只生成派生结果和快照，不修改 `Position`。如果未来用户确认执行方案，也只能由独立的交易/持仓更新流程完成。

### 6.3 金额与时间

- 数据库金额、数量和比例使用定点数语义，不用二进制浮点保存货币。
- 分析内部可以使用浮点数组，但输出前必须处理 `NaN`、无穷值和精度。
- 每条估值、市场数据和分析结果分别保存 `as_of` 与 `calculated_at`。
- 日期按市场日期保存，系统时间保存为带时区 UTC，页面按本地时区显示。

---

## 7. 金融计算口径

### 7.1 持仓估值与覆盖率

```text
position_value = quantity × latest_usable_value
                 或用户输入的 manual_value

weight = position_value / known_portfolio_value
```

- 每项持仓必须展示估值来源、估值日期和是否陈旧。
- 缺失价格不能填 `0`，该持仓进入数据风险。
- 覆盖率同时展示“成功估值的持仓数量”和“成功估值的参考市值比例”。如果缺失持仓连参考市值也未知，比例本身标记为 `UNKNOWN`。
- 跨估值日组合可以展示，但必须标记日期不一致，不能伪装成同一时点快照。

### 7.2 历史风险不是账户收益

MVP 没有交易和现金流账本，因此只计算：

> **使用当前权重或 Scenario 权重，在历史市场序列上进行的风险模拟。**

该序列明确命名为 `historical_risk_simulation`，页面不得使用“我的历史收益”或“账户收益”。默认采用固定权重、每日再平衡假设，所有比较方案使用相同窗口和相同方法。

第一版指标：

- 年化波动率。
- 下行波动率。
- 模拟区间最大回撤。
- 当前模拟回撤。
- 单一标的与资产类别集中度。
- 资产相关性矩阵，仅在样本充足时展示。

默认使用最近 252 个有效观测日，至少需要 120 个对齐观测日；窗口和门槛集中配置，并在结果中记录。样本不足时返回 `UNKNOWN`，不自动改用更短窗口制造结果。

净值序列优先使用能反映分红影响的累计净值或复权价格。只能取得单位净值时，结论必须带数据限制说明。

### 7.3 序列对齐与陈旧数据

- 不允许无期限前向填充。
- 按标的市场和类型配置新鲜度阈值，QDII 与境内 ETF 不能共用一个固定阈值。
- 对齐后记录每项资产的有效样本数、最后日期和缺失比例。
- 对组合有实质影响的持仓数据不足时，整体市场风险状态为 `UNKNOWN`。
- AkShare 接口结构变化、网络失败和空数据必须是不同的错误类型。

### 7.4 风险状态

每个维度独立产生状态：

```text
UNKNOWN  无法可靠计算
WITHIN   在已定义边界内
WATCH    接近边界
BREACHED 已越过边界
```

MVP 规则：

- 单标的集中度上限。
- 资产类别目标权重及允许偏离。
- 现金最低比例。
- 数据新鲜度和覆盖率门槛。

`WATCH` 默认在距离边界剩余 20% 缓冲区时触发，具体 `warning_ratio` 可由规则保存。顶层状态按“可靠证据上的 BREACHED 优先，其次关键维度 UNKNOWN、WATCH、WITHIN”聚合，避免未知数据掩盖已经确认的越界；页面仍必须展示所有维度，不能只给一个颜色。

市场波动和回撤在 MVP 中先作为事实与比较指标；用户没有设置明确边界时，系统不能擅自把某个波动率解释为违规。

### 7.5 Scenario 比较

每次比较必须包含 `NO_ACTION` 基线，并输出：

- 操作前后权重、现金比例和集中度变化。
- 目标配置距离变化。
- 同一历史窗口下的波动率、下行波动和最大回撤变化。
- 用户输入的交易成本估计。
- 可选的手工压力假设，例如某资产类别下跌一定比例；这是 `ASSUMPTION`，不是预测。
- 数据覆盖率、陈旧数据、缺失资产和结论置信度。
- 方案改善了什么、恶化了什么，以及最主要的反对理由。

---

## 8. API 与页面边界

### 8.1 MVP API

```text
GET    /api/v1/portfolio
PUT    /api/v1/portfolio/positions
POST   /api/v1/portfolio/import
POST   /api/v1/market-data/refresh
GET    /api/v1/data-quality

GET    /api/v1/watchlists
POST   /api/v1/watchlists/{id}/items

GET    /api/v1/policies
PUT    /api/v1/policies/{id}

GET    /api/v1/risk/current
POST   /api/v1/risk/recalculate

POST   /api/v1/scenarios
POST   /api/v1/scenarios/{id}/operations
GET    /api/v1/scenarios/{id}/comparison

GET    /api/v1/events
```

API 返回统一包含：

- `data`
- `as_of`
- `calculated_at`
- `coverage`
- `warnings`
- `methodology_version`

### 8.2 MVP 前端页面

| 页面 | 首版能力 |
|------|----------|
| `/` | 顶层风险状态、主要风险、数据日期、覆盖率和重要变化 |
| `/portfolio` | 账户、持仓、现金、手工录入和 CSV 导入 |
| `/watchlists` | 观察列表的增删、分组、理由和标签 |
| `/policies` | 目标权重、集中度上限、现金下限和偏离区间 |
| `/scenarios` | 创建操作方案并与 `NO_ACTION` 比较 |
| `/data-quality` | 数据源、日期、缺失、陈旧和失败原因 |
| `/events` | 风险状态和数据质量变化事件 |

“判断摘要”先作为风险首页和 Scenario 结果中的结构化区块，不单独建设第八个页面。

---

## 9. v1 复用与退役策略

| v1 资产 | 处理方式 |
|---------|----------|
| `fund_analysis.py` 的代码识别与多数据源经验 | 用 contract test 固化已知输入输出，再重写为 typed provider；不直接复制整个文件 |
| AkShare 基金、境内指数和全球指数调用 | 按标的类型拆成适配器方法，保留重试和明确 fallback 顺序 |
| `funds_config.json` | 提供一次性导入命令，分别导入 watchlist 或初始持仓，不再作为运行时事实源 |
| `indices_config.json` | 迁移为 instrument alias seed，后续由数据库管理 |
| `main.py` | V2 风险首页可运行后删除 |
| `feishu_config.py`、`feishu_notifier.py`、`feishu_config.json` | MVP 不接 IM，迁移结束后删除；未来按通知适配器重新实现 |
| `README.md`、`README_CN.md`、`DEVLOG.md` | 开发过程中改写为 V2 安装、口径和迁移说明 |

迁移原则：先为 v1 的有效数据获取场景建立固定样例，再实现 V2 provider；新 provider 通过样例和失败测试后，才删除旧入口。

---

## 10. 分阶段实施计划

每个阶段都必须形成可运行、可测试的纵向切片，不接受“所有模型先写完，最后再连接页面”。

### PR 0：工程基线

交付：

- 创建 `pyproject.toml`、`src/tickeye` 包和后端启动命令。
- 创建 `frontend/` React + TypeScript + Vite 工程及 pnpm lockfile。
- 建立 FastAPI `/api/v1/health`、OpenAPI、开发期 CORS 白名单和统一错误格式。
- 建立 React 应用框架、前端路由、API client、QueryClient 和健康状态页。
- 配置前端构建产物由 FastAPI 同源托管，确保 SPA fallback 不拦截 `/api/v1`。
- 配置 SQLAlchemy、Alembic 和 SQLite 数据目录。
- 配置 pytest、Ruff、mypy、Vitest、ESLint、TypeScript 和统一日志。
- 增加 `.env.example` 与本地配置说明。

验收：

- 新环境可以安装前后端依赖并启动两个开发服务。
- React 健康页可以通过生成的 API 类型读取 FastAPI health 响应。
- 前端生产构建后，只运行 FastAPI 也能打开应用并刷新客户端路由。
- 数据库可以从空库迁移到最新版本。
- 前后端测试、lint、typecheck 和 build 均可运行。

### PR 1：资产事实与持久化

交付：

- 实现 `Profile`、`Instrument`、`Account`、`Position`、`PositionSnapshot`。
- 实现手工持仓录入、编辑和删除。
- 实现严格 CSV 预览、校验、确认导入，错误行不静默跳过。
- 实现 `/portfolio` 和对应 API。
- 保存金额、数据来源和 `as_of`。

验收：

- 用户可以创建账户、录入基金/ETF/现金并重启后保留数据。
- CSV 重复行、未知代码、负数量和非法日期都有明确错误。
- 每次持仓变更形成可恢复快照。

### PR 2：市场数据与数据可信度

交付：

- 定义 `MarketDataProvider` 接口和标准错误类型。
- 从 v1 提取基金、境内指数、全球指数获取行为，建立 AkShare adapter。
- 持久化 `MarketObservation`，支持手动刷新和缓存。
- 建立数据新鲜度、样本量、缺失率和来源检查。
- 实现 `/data-quality`。

验收：

- 网络失败、空数据、字段变化和未知标的不会产生伪造的 `0`。
- 同一日期重复刷新幂等。
- 页面能准确展示每项资产的数据来源、最后日期和失败原因。
- 默认测试不依赖实时网络，provider contract test 使用固定 fixture。

### PR 3：组合估值与风险计算

交付：

- 实现持仓估值、权重和覆盖率。
- 实现历史序列对齐和质量门槛。
- 实现年化波动、下行波动、最大回撤、当前回撤、集中度和相关性。
- 输出 methodology version、假设和证据。
- 实现 Risk Snapshot 和风险首页第一版。

验收：

- 纯函数通过手算小样例和固定市场序列测试。
- 缺失、陈旧、短样本、全现金、单一持仓和零波动组合行为明确。
- 页面明确写出这是“当前权重历史风险模拟”，不显示真实账户收益。

### PR 4：风险规则与事件

交付：

- 实现 `PolicyRule`、`RiskFinding` 和顶层状态聚合。
- 支持集中度上限、资产类别目标偏离、现金下限和数据质量边界。
- 实现 `/policies` 和解释性风险摘要。
- 比较前后两个 Risk Snapshot，生成去重的 `InsightEvent`。
- 实现 `/events`。

验收：

- `WITHIN → WATCH → BREACHED → WITHIN` 状态转换都有测试。
- 修改规则会重新计算，但不会改写旧 Risk Snapshot。
- 同一风险重复计算不产生重复事件。
- 每个结论包含当前值、边界、贡献者、日期和覆盖率。

### PR 5：Scenario 方案实验室

交付：

- 实现 Scenario 和有序 ScenarioOperation。
- 支持买入、卖出、金额调整、目标权重调整和 `NO_ACTION`。
- 复用同一个 Risk Engine 计算 before/after。
- 支持交易成本输入和手工压力假设。
- 实现 `/scenarios`、比较 API 和判断摘要。

验收：

- Scenario 永不修改实际 Position。
- 卖出超过持仓、负现金、权重不闭合和未知价格均被拒绝或标为不可计算。
- before/after 使用完全相同的数据窗口和方法版本。
- 输出同时展示改善项、恶化项、反对理由和数据限制。

### PR 6：观察列表与完整 Web 闭环

交付：

- 实现 Watchlist、分组、标签和观察理由。
- 允许从观察列表创建 Scenario，但不做推荐或排序。
- 完善风险首页、空状态、错误状态和导航。
- 增加一条从持仓录入到 Scenario 比较的浏览器 E2E 测试。
- 增加数据导出和 SQLite 备份说明。

验收：

- 新用户从空库可以独立完成整个 MVP 闭环。
- 页面在数据源失败时仍可操作，并清晰告诉用户哪些结论不可用。
- 观察列表不会改变持仓或被描述成推荐结果。

### PR 7：迁移与 v1 退役

交付：

- 将 `funds_config.json` 导入新数据库。
- 核对新旧数据获取结果和异常行为。
- 删除 `main.py`、旧飞书实现和不再使用的 JSON 运行时配置。
- 重写中英文 README 和开发日志。
- 清理旧依赖并确认新环境可重建。

验收：

- 仓库只存在一个正式启动入口。
- V2 不依赖 v1 根目录脚本。
- 用户数据文件不会进入 Git。
- 从空环境按照 README 可以完成安装、迁移、启动和备份。

---

## 11. 测试计划

### 11.1 单元测试

- 估值、权重、覆盖率和舍入。
- 收益序列、波动率、下行波动和回撤。
- 序列对齐、样本门槛和陈旧数据判定。
- 风险状态聚合及全部边界等号情况。
- Scenario 操作应用顺序、现金约束和幂等性。
- 事件 dedupe key 和状态恢复。

金融计算测试必须包括手算结果和公开固定序列，不能只断言“不报错”。

### 11.2 集成测试

- Alembic 从空库升级。
- Repository 的创建、更新、快照和事务回滚。
- API 输入校验、错误响应和并发修改保护。
- CSV 预览与确认导入。
- AkShare adapter 对固定响应、空响应和字段变化的处理。

### 11.3 前端组件与交互测试

- 风险状态、覆盖率、证据和 `UNKNOWN` 的渲染。
- loading、empty、partial、error 和 stale 状态。
- 持仓表单、CSV 预览、规则表单和 Scenario 操作校验。
- TanStack Query mutation 后只刷新相关 query，不依赖全局页面刷新。
- API schema 生成结果与前端 TypeScript 编译。

### 11.4 Web E2E

关键路径：

```text
创建账户
  → 录入现金和两个基金
  → 刷新固定市场数据
  → 设置集中度与现金规则
  → 查看风险首页
  → 创建买入 Scenario
  → 比较 NO_ACTION 与操作方案
  → 查看证据和数据限制
```

至少覆盖：成功路径、数据缺失路径和非法 Scenario 路径。

### 11.5 默认本地质量门

```bash
pytest
ruff check .
mypy src
pnpm --dir frontend test
pnpm --dir frontend run lint
pnpm --dir frontend run typecheck
pnpm --dir frontend run build
pnpm --dir frontend exec playwright test
```

自动化暂不恢复，但每个 PR 的完成定义仍然要求本地质量门全部通过。

---

## 12. 主要失败模式与处理

| 失败模式 | 系统行为 | 用户看到什么 |
|----------|----------|--------------|
| AkShare 超时 | 有限重试，保留上次成功数据并标记陈旧 | 数据源失败、上次日期、重试入口 |
| AkShare 字段变化 | contract validation 失败，不写入坏数据 | 该标的 `UNKNOWN` 和字段不兼容原因 |
| 部分持仓无价格 | 计算已知部分，但整体覆盖率下降 | 未覆盖持仓列表，不显示虚假完整结论 |
| QDII 日期晚于/早于其他资产 | 保留各自 `as_of`，触发日期不一致 | 跨市场估值日期提示 |
| 历史样本不足 | 风险指标返回 `UNKNOWN` | 缺少多少样本以及所需门槛 |
| CSV 重复导入 | 使用导入指纹和确认步骤防重复 | 明确提示重复批次 |
| Scenario 导致负现金或超额卖出 | 拒绝计算该操作 | 可修正的字段错误，不污染持仓 |
| 风险规则修改 | 新建快照重新评估 | 显示规则变化导致状态变化 |
| SQLite 文件损坏或误删 | 启动前检查并提供备份/恢复说明 | 明确阻止继续写入，不自动重建覆盖 |

任何会让错误结果看起来像正常结果的失败，优先级高于页面体验问题。

---

## 13. 执行顺序与提交原则

PR 0 到 PR 5 具有强顺序依赖，建议串行完成。PR 6 的视觉样式可以在 PR 3 后并行探索，但数据交互必须等待 API 稳定。

```text
PR 0 工程基线
  → PR 1 资产事实
  → PR 2 市场数据
  → PR 3 风险计算
  → PR 4 规则与事件
  → PR 5 Scenario
  → PR 6 完整 Web 闭环
  → PR 7 迁移和退役
```

每个 PR 遵守：

- 结构变更和行为变更尽量分开提交。
- 数据库模型变化必须带 migration。
- 风险计算变化必须更新 `methodology_version` 和回归测试。
- 不提交用户数据库、真实持仓 CSV、密钥或绝对金额截图。
- 不因为后续可能接 Agent 或商业化而提前建立微服务、消息队列或复杂权限系统。

---

## 14. MVP 完成定义

只有同时满足以下条件，V2 MVP 才算完成：

- 用户可以从空数据库完成持仓录入和 CSV 导入。
- 实际、目标、观察和 Scenario 数据关系正确且互不污染。
- 风险首页显示状态、贡献者、边界、数据日期和覆盖率。
- 数据不足时显示 `UNKNOWN`，不存在通过 `0` 或静默忽略伪造的完整结果。
- 至少一个 `NO_ACTION` 与操作方案可以使用相同口径比较。
- 页面不声称提供真实账户收益或投资推荐。
- 关键金融计算、状态转换、数据失败和 Scenario 路径都有测试。
- 本地启动、迁移、测试、备份和恢复步骤有文档。
- v1 正式入口已经退役，仓库只保留 V2 运行方式。

---

## 15. 开始开发时的第一批任务

1. 创建 `pyproject.toml` 并锁定 Python 与后端依赖版本。
2. 建立 `src/tickeye`、FastAPI app factory、配置和日志模块。
3. 创建 `frontend/` React + TypeScript + Vite 工程并锁定 pnpm 依赖。
4. 配置 SQLite、SQLAlchemy session 和首个 Alembic migration。
5. 建立 health API、生成 TypeScript API 类型并完成 React 健康页。
6. 配置前端开发代理、CORS 白名单和构建后同源静态托管。
7. 添加前后端健康测试，验证 Web、数据库和完整工具链。
8. 建立 `.gitignore` 数据目录规则和 `.env.example`。
9. 更新 README 的 V2 本地启动草案。

这一批任务只建立可验证的工程骨架，不提前实现风险算法或复制 v1 代码。
