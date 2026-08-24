# TickEye V2

TickEye 是一个本地优先的个人投资决策支持与风险控制工具。它围绕一个核心问题展开：

> 我的钱现在处于什么风险状态？

系统不替用户作出买卖决定，而是持续整理持仓、关注标的和市场变化中的风险信号，给出可追溯的事实、解释与行动前检查，帮助用户控制风险并提高长期获得收益的概率。

当前分支正在按 [V2 产品描述](v2_product.md) 和 [开发计划](v2_development_plan.md) 重建。V1 脚本暂时保留，尚未接入 V2 应用。

## 当前进度

工程基线已经具备：

- FastAPI API 与统一错误响应
- SQLite 本地数据库和 Alembic 迁移
- React、TypeScript、Vite 前端
- 前端开发代理及 FastAPI 单进程生产托管
- 从 OpenAPI 自动生成的前端接口类型
- Python 与前端的基础测试、类型检查和静态检查

目前页面只用于验证整条技术链路。持仓、观察列表和风险分析从后续迭代开始实现。

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

## 项目结构

```text
src/tickeye/          V2 Python 应用
  domain/             领域模型与规则
  application/        用例编排
  infrastructure/     数据库与外部数据源
  web/                FastAPI 接口与前端托管
frontend/             React 前端
migrations/           Alembic 数据库迁移
tests/                Python 测试
data/                 本地数据（不提交）
```

## 产品边界

TickEye 提供信息组织、风险解释和决策支持，不承诺收益，不代替用户决策，也不把尚未具备的数据包装成精确结论。MVP 暂不输出缺少现金流账本支撑的收益归因，也暂不实现机会分析。

## License

[MIT](LICENSE)
