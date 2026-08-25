# TickEye V2

[English](README.md)

TickEye 是一个本地优先的个人投资决策支持与风险控制工具。它围绕一个核心问题展开：

> 我的钱现在处于什么风险状态？

系统不替用户作出买卖决定，而是持续整理持仓、关注标的和市场变化中的风险信号，给出可追溯的事实、解释与行动前检查，帮助用户控制风险并提高长期获得收益的概率。

当前分支已经按 [V2 产品描述](docs/v2_product.md) 和 [开发计划](docs/v2_development_plan.md) 完成本地 Web MVP。V1 正式入口已经退役，旧配置仅隔离保存在 `legacy/v1/` 用于迁移核对。

## 当前进度

工程基线、资产事实、市场数据、历史风险模拟和第一版用户风险规则已经具备：

- FastAPI API 与统一错误响应
- SQLite 本地数据库和 Alembic 迁移
- React、TypeScript、Vite 前端
- 前端开发代理及 FastAPI 单进程生产托管
- 从 OpenAPI 自动生成的前端接口类型
- Python 与前端的基础测试、类型检查和静态检查
- 单用户 Profile、账户、标的、持仓和不可变持仓快照
- `/portfolio` 手工新增、编辑和删除持仓
- CSV 严格预览与确认导入，拒绝错误行和重复批次
- revision 乐观锁，避免旧页面覆盖较新的持仓
- 可替换的市场数据 Provider 契约与 AkShare 实现
- 基金、QDII 基金和 ETF 的手动行情刷新与本地幂等缓存
- 刷新审计、明确的网络/空数据/字段变化/非法值错误语义
- `/data-quality` 数据新鲜度、样本数、异常记录拒绝率和数据源限制展示
- 持仓估值、标的/资产类别权重和数据覆盖率
- 当前权重历史风险模拟：年化波动率、下行波动率、最大/当前回撤和相关性
- 不可变 Risk Snapshot，持仓或行情变化后旧快照会标记过期
- 风险首页展示计算状态、指标、估值依据、证据、假设和数据限制，并按证据优先级给出下一步入口
- 风险首页展示最近 3 条已记录的重要状态变化，完整历史保留在事件页
- 用户明确设置的单标的/资产类别上限、资产类别目标偏离和现金下限
- 不可变规则评估，以及首次发现、状态变化和恢复事件的去重记录
- `/policies` 风险规则管理和 `/events` 风险事件时间线
- `/scenarios` 创建风险方案，在实际持仓临时副本上模拟调整并比较 `NO_ACTION` 基线
- Scenario 输出同窗历史风险、规则状态、手工压力、成本和判断摘要
- `/watchlists` 管理用户自选观察分组、候选标的、理由和标签
- 观察标的进入行情质量跟踪，可从观察页创建风险方案，但不会写入实际持仓
- `/api/v1/export` 导出持仓、规则、观察列表和 Scenario 用户事实
- `tickeye-migrate-v1` 两步预览并迁移旧基金观察配置，不把指数或观察标的写成持仓

“历史风险可计算”不表示组合安全；只有用户明确设置边界后，系统才会判断相应维度是否接近或越过边界。系统没有现金流账本，不输出真实账户收益或收益归因。

## MVP 功能冻结边界

V2 Web MVP 到此冻结功能范围。当前闭环是“录入实际持仓 → 刷新并检查数据 → 查看风险状态和重要变化 → 按需设置个人边界 → 对用户主动提出的调整进行风险方案模拟”。

冻结后只接受缺陷修复、验收体验调整、文档补充、依赖与安全维护。以下能力不进入本 MVP：

- 真实账户收益、现金流账本、TWR、XIRR 和收益归因
- 机会发现、基金推荐、候选排序和自动买卖结论
- 自动下单、券商或银行连接，以及模拟撮合、虚拟盈亏和排行榜
- 自动定时行情、IM/Agent 通知和事件已读状态
- 多用户、登录权限、云端部署和商业化边界
- 旧配置中的指数跟踪；继续保持暂缓，后续单独确定产品价值和数据口径

## 本地开发

需要 Python 3.11+、[uv](https://docs.astral.sh/uv/) 和 Node.js 22+，前端包管理器使用 pnpm。

```bash
uv sync --group dev
pnpm --dir frontend install
cp .env.example .env
.venv/bin/alembic upgrade head
```

分别启动后端和前端：

```bash
.venv/bin/tickeye --reload
```

```bash
pnpm --dir frontend dev
```

浏览器打开 `http://127.0.0.1:5173`。Vite 会把 `/api` 请求代理到 `http://127.0.0.1:8000`。

风险首页位于 `http://127.0.0.1:5173/`，持仓页面位于 `/portfolio`，观察列表位于 `/watchlists`，规则页面位于 `/policies`，风险方案模拟位于 `/scenarios`，风险事件页面位于 `/events`，数据质量页面位于 `/data-quality`。

## 观察列表

观察列表只保存用户主动选择的候选标的、观察理由和标签。系统不发现机会、不推荐基金，也不按所谓“值得买入程度”排序。一个标的可以同时处于“已持有”和“观察中”；这两个关系彼此独立。

- 加入观察列表不会创建或修改 `Position`，也不会改变持仓 revision 和已有风险快照。
- 持有或观察中的非现金标的都会进入数据质量页和“刷新全部行情”的范围。
- 从观察页点击“模拟调整风险”会把候选作为零持仓输入冻结到新 Scenario；只有在方案中显式追加买入等调整，after 组合才会产生该标的敞口。
- 候选缺少价格时仍可建立基线，但涉及它的买入或金额调整无法可靠换算，系统会拒绝该操作并说明原因。
- Scenario 始终是未执行实验，不会因比较结果自动改变真实持仓。

## 历史风险模拟口径

首页展示的是 `historical-risk-v1` 当前权重历史风险模拟，不是用户账户的历史收益。计算采用以下固定口径：

- 非现金持仓优先使用“数量 × 最新可用净值/复权价”估值；没有行情时才使用手工市值。现金使用手工市值或数量表示余额。
- 使用当前估值权重回放历史，并假设每天按固定权重重新平衡。
- 现金日收益假设为 0，不计利息、费用、税费和交易滑点。
- 最多使用最近 252 个共同价格观测日，至少需要 120 个；不前向填充，不自动缩短门槛。
- 年化波动率使用 252 个交易日和样本标准差；下行波动率以 0 为最低可接受日收益。
- 最大回撤和当前回撤使用模拟净值相对历史高点的正数跌幅表示。
- 缺失估值、缺失/陈旧行情、最近刷新失败或共同样本不足时，市场风险指标返回 `UNKNOWN`。
- 全现金组合单独标记，并只在“现金日收益为 0”的假设下输出零市场波动；这不涵盖通胀、流动性或信用风险。

风险快照只能通过首页按钮或 `POST /api/v1/risk/recalculate` 显式生成。`GET /api/v1/risk/current` 读取最后一份不可变快照；持仓或行情后来变化时，旧快照会标记过期，不会被后台静默改写。

## 用户风险规则与事件

TickEye 不预设“适合所有人”的风险阈值。规则边界、目标容差和关注缓冲都由用户明确填写；没有启用规则时，规则汇总状态为 `UNKNOWN`，不会显示为安全或边界内。

- 上限规则：当前值大于上限才算 `BREACHED`，等于上限为 `WATCH`。
- 现金下限：当前值小于下限才算 `BREACHED`，等于下限为 `WATCH`。
- 目标配置：偏离值大于容差才算 `BREACHED`，等于容差为 `WATCH`。
- 顶层状态优先级为 `BREACHED > UNKNOWN > WATCH > WITHIN`，已确认的越界不会被数据未知掩盖。

每次修改规则或在首页重新计算都会生成新的不可变风险快照和规则评估，不会改写历史。事件只记录首次发现、真实状态变化和恢复；相同状态重复计算不会产生重复事件。这些规则是用户声明的风险边界，不是系统推断的风险偏好，也不是买卖建议。

## Scenario 风险方案模拟

风险方案不是模拟交易账户。Scenario 在创建时冻结当前持仓事实、行情历史和基础持仓版本；后续调整只作用于这个临时副本，不修改实际 `Position`。每追加一个有序调整，系统都会保存一份新的不可变比较结果。

首版支持：

- `NO_ACTION`：每个方案自带的不操作基线。
- `BUY` / `SELL`：按金额买入或卖出当前已持有且有冻结价格的标的。
- `SET_AMOUNT`：把标的调整到指定市值。
- `SET_TARGET_WEIGHT`：按扣除估计成本后的组合总值调整目标权重。
- 用户输入的估计交易成本。
- 可选的资产类别手工下跌压力；这是 `ASSUMPTION`，不是预测。

买入、卖出和调整按保存顺序应用。现金按组合级资金池结算；超额卖出、负现金、缺少价格、成本超过卖出所得和无法闭合的操作会被拒绝，不会保存半成品。实际组合里的非现金标的可以直接参与实验；用户观察列表中的未持有候选也可以先作为零持仓输入冻结，再在该 Scenario 中显式买入或调整。

before/after 强制使用同一份冻结行情、相同历史窗口、相同风险方法和同一规则版本。结果同时展示结构与历史风险变化、规则状态、改善项、恶化项、反对理由、数据限制和置信度，但不预测收益，也不构成买卖建议。

## 市场数据与质量状态

系统刷新当前持有或观察中的基金、QDII 基金和 ETF；具体观察范围由用户通过持仓和观察列表共同决定。现金资产会显示为“无需行情”。刷新暂时由用户在数据质量页面手动发起，没有后台定时任务。

市场数据经 Provider 标准化后写入本地数据库。相同日期、标的和口径的数据重复刷新不会重复插入；网络或上游错误会被记录，但不会清除最后一份有效数据。质量页面使用以下状态：

- `可用`：数据新鲜，且至少有 120 个样本
- `部分数据`：上游返回的部分记录因日期、空值或非正数等问题被拒绝
- `数据陈旧`：普通基金/ETF 超过 3 个自然日，QDII 超过 5 个自然日没有新数据
- `尚无数据`：从未成功刷新
- `刷新失败`：最近一次刷新失败，同时保留此前有效数据
- `样本不足`：少于 120 个样本
- `无需行情`：现金类资产

当前 AkShare 适配规则：公募基金优先采用累计净值，仅在结果为空时回退到单位净值；ETF 使用前复权日线。前复权历史可能因分红送配重新计算，因此该限制会随数据一起保存并展示。字段变化不会被静默当作空数据处理，而会明确报告为数据源结构变化。

## CSV 持仓导入

CSV 导入分为“预览校验”和“确认替换”两步。确认时 CSV 中的完整列表会替换当前持仓；任何错误行都会阻止整批写入，不会被静默跳过。

最小必需列为 `account`、`code`、`market` 和 `as_of`。首次出现的标的还必须提供 `name`、`type`、`currency`、`asset_class` 和 `region`，并在 `quantity` 或 `manual_value` 中至少填写一项。

```csv
account,code,name,type,market,currency,asset_class,region,quantity,manual_value,cost,as_of
长期账户,510300,沪深300ETF,etf,CN,CNY,equity,中国,1000,4000,3800,2026-08-24
现金账户,CASH-CNY,人民币现金,cash,CN,CNY,cash,中国,,10000,,2026-08-24
```

支持的 `type`：`fund`、`etf`、`qdii_fund`、`cash`。

支持的 `asset_class`：`equity`、`fixed_income`、`mixed`、`cash`、`commodity`、`other`。

MVP 只接受人民币账户和人民币计价资产。日期必须为 `YYYY-MM-DD` 且不能晚于今天；数量、市值和成本不能为负数。

## 数据导出与 SQLite 备份

页面底部的“导出用户数据”会下载版本化 JSON，内容包括 Profile、当前持仓、用户风险规则、观察列表，以及用于解释既有实验的 Scenario 冻结输入与操作。可重新获取的行情缓存、派生风险快照、规则事件和 Scenario 比较结果不会重复导出。JSON 当前用于查看和未来迁移，尚不提供自动恢复导入，因此不能代替数据库备份。

数据库默认位于 `data/tickeye.db`。应用运行期间不要直接复制这个文件；使用 SQLite 在线备份命令取得一致快照：

```bash
mkdir -p backups
sqlite3 data/tickeye.db ".backup 'backups/tickeye-20260825.db'"
sqlite3 backups/tickeye-20260825.db "PRAGMA integrity_check;"
```

第二条命令应输出 `ok`。备份文件包含用户事实、行情缓存和所有历史派生结果，请像保护账户资料一样保护它，不要提交到 Git。

恢复时先停止 TickEye，并恢复到新文件，避免覆盖现有数据库：

```bash
sqlite3 backups/tickeye-20260825.db ".backup 'data/tickeye-restored.db'"
TICKEYE_DATABASE_URL=sqlite:///./data/tickeye-restored.db .venv/bin/alembic upgrade head
TICKEYE_DATABASE_URL=sqlite:///./data/tickeye-restored.db .venv/bin/tickeye
```

确认页面数据无误后，再决定是否把 `.env` 中的 `TICKEYE_DATABASE_URL` 指向恢复文件。若 `PRAGMA integrity_check` 不是 `ok`，不要继续写入该文件。

## v1 配置迁移

`legacy/v1/funds_config.json` 同时包含基金和指数，不能整批当作基金或真实持仓导入。迁移命令默认执行只读预览：六位基金代码会准备进入名为“v1 迁移观察列表”的分组；在 `legacy/v1/indices_config.json` 中出现的指数会明确暂缓。

先完成数据库迁移并建议创建备份，然后预览：

```bash
.venv/bin/alembic upgrade head
.venv/bin/tickeye-migrate-v1
```

预览会展示推断的标的类型、资产类别、地区、已存在项目、暂缓项目、配置问题和一个 64 位令牌。类型和地区是根据 v1 名称保守推断的，导入项目统一带有 `v1迁移` 和 `待核对` 标签。

确认预览无误后，把输出的令牌原样传回：

```bash
.venv/bin/tickeye-migrate-v1 \
  --confirm \
  --preview-token <预览输出的令牌>
```

确认操作在单个数据库事务中完成，不会创建或修改 `Position`，也不会推进持仓 revision。重复运行会跳过目标分组中已经存在的标的。配置内容或目标分组名称发生变化后，旧令牌会失效，必须重新预览。

需要自定义文件、分组或机器可读输出时：

```bash
.venv/bin/tickeye-migrate-v1 \
  --funds-config ./legacy/v1/funds_config.json \
  --indices-config ./legacy/v1/indices_config.json \
  --target-watchlist "旧版关注" \
  --json
```

指数当前只进入迁移审计结果，不进入观察列表。待 V2 明确定义指数基准用途和数据模型后再单独迁移，避免把市场基准误解为可买基金。

## 单进程运行

前端构建后，FastAPI 会直接托管静态文件和前端路由：

```bash
pnpm --dir frontend build
.venv/bin/alembic upgrade head
.venv/bin/tickeye
```

然后打开 `http://127.0.0.1:8000`。

## API 类型同步

后端接口契约改变后，重新导出 OpenAPI 并生成 TypeScript 类型：

```bash
.venv/bin/tickeye-export-openapi frontend/src/api/openapi.json
pnpm --dir frontend generate:api
```

`frontend/src/api/generated/` 是生成目录，不要手工修改。

## 质量检查

```bash
.venv/bin/ruff check src tests
.venv/bin/mypy src
.venv/bin/pytest
pnpm --dir frontend typecheck
pnpm --dir frontend test
pnpm --dir frontend lint
pnpm --dir frontend build
```

首次运行浏览器 E2E 前安装 Chromium；Linux 如果提示缺少系统动态库，可使用 Playwright 官方的 `--with-deps` 安装方式：

```bash
pnpm --dir frontend exec playwright install chromium
pnpm --dir frontend test:e2e
```

E2E 会启动临时 FastAPI、Vite 和临时 SQLite，并使用确定性行情 Provider 验证“持仓 → 观察 → 数据 → 风险 → 规则 → Scenario”闭环，不会读写 `data/tickeye.db`，也不会访问外部行情服务。

## 项目结构

```text
docs/                 产品愿景、产品定义与工程计划
src/tickeye/          V2 Python 应用
  domain/             领域模型与规则
  application/        用例编排
  infrastructure/     数据库与外部数据源
  web/                FastAPI 接口与前端托管
frontend/             React 前端
migrations/           Alembic 数据库迁移
tests/                Python 测试
data/                 本地数据（不提交）
backups/              本地数据库备份（不提交）
```

## 设计文档

- [V2 升级愿景](docs/v2_plan.md)
- [V2 产品定义](docs/v2_product.md)
- [V2 Web MVP 开发计划](docs/v2_development_plan.md)
- [English README](README.md)

## 产品边界

TickEye 提供信息组织、风险解释和决策支持，不承诺收益，不代替用户决策，也不把尚未具备的数据包装成精确结论。MVP 暂不输出缺少现金流账本支撑的收益归因，也暂不实现机会分析。

## License

[MIT](LICENSE)
