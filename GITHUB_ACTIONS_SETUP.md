# GitHub Actions 定时运行设置指南

本文档介绍如何使用 GitHub Actions 实现 TickEye 基金监测程序的每日定时运行。

## 🚀 快速开始

### 1. 推送代码到 GitHub

确保你的项目已经推送到 GitHub 仓库：

```bash
git add .
git commit -m "Add GitHub Actions workflow"
git push origin main
```

### 2. 配置 GitHub Secrets

在 GitHub 仓库页面：

1. 点击 **Settings** 标签
2. 在左侧菜单中选择 **Secrets and variables** → **Actions**
3. 点击 **New repository secret**
4. 添加以下 Secret：

| Name | Value | 说明 |
|------|-------|------|
| `FEISHU_WEBHOOK_URL` | 你的飞书机器人 webhook URL | 必需，用于发送通知 |

### 3. 启用 GitHub Actions

1. 在仓库页面点击 **Actions** 标签
2. 如果是第一次使用，点击 **I understand my workflows, go ahead and enable them**
3. 你应该能看到 "Daily Fund Monitor" workflow

## ⏰ 运行时间设置

当前配置的运行时间：

- **每天 09:00** (北京时间) - 开盘前检查
- **工作日 15:00** (北京时间) - 收盘后分析

### 修改运行时间

编辑 `.github/workflows/daily-fund-monitor.yml` 文件中的 cron 表达式：

```yaml
schedule:
  # 自定义时间 (注意：GitHub Actions 使用 UTC 时间)
  - cron: '0 1 * * *'    # 北京时间 09:00
  - cron: '0 7 * * 1-5'  # 北京时间 15:00 (仅工作日)
```

**时区转换参考**：
- 北京时间 = UTC + 8
- 北京时间 09:00 = UTC 01:00
- 北京时间 15:00 = UTC 07:00

## 🎮 手动运行

### 通过 GitHub 界面

1. 进入 **Actions** 标签
2. 选择 "Daily Fund Monitor" workflow
3. 点击 **Run workflow**
4. 可以设置参数：
   - **分析天数**: 默认 1 天
   - **发送表格格式**: 默认 false

### 通过 GitHub CLI

```bash
# 安装 GitHub CLI
brew install gh  # macOS
# 或 apt install gh  # Ubuntu

# 登录
gh auth login

# 手动触发 workflow
gh workflow run "Daily Fund Monitor"

# 带参数触发
gh workflow run "Daily Fund Monitor" -f days=3 -f send_table=true
```

## 📊 监控和日志

### 查看运行状态

1. 在 **Actions** 标签页可以看到所有运行记录
2. 点击具体的运行记录查看详细日志
3. 绿色 ✅ 表示成功，红色 ❌ 表示失败

### 日志内容

运行日志包含：
- 环境设置信息
- Python 依赖安装过程
- 基金数据获取过程
- 飞书通知发送结果
- 错误信息（如有）

### 错误处理

如果运行失败：
1. 查看详细的错误日志
2. 检查 Secret 配置是否正确
3. 确认网络连接正常
4. 验证基金代码配置

## 🔧 高级配置

### 添加更多运行时间

```yaml
schedule:
  - cron: '0 1 * * *'     # 每天 09:00
  - cron: '0 7 * * 1-5'   # 工作日 15:00
  - cron: '0 9 * * 1-5'   # 工作日 17:00 (新增)
```

### 只在工作日运行

```yaml
schedule:
  - cron: '0 1 * * 1-5'   # 周一到周五 09:00
```

### 添加邮件通知

在 workflow 中添加邮件通知步骤：

```yaml
- name: Send email on failure
  if: failure()
  uses: dawidd6/action-send-mail@v3
  with:
    server_address: smtp.gmail.com
    server_port: 587
    username: ${{ secrets.EMAIL_USERNAME }}
    password: ${{ secrets.EMAIL_PASSWORD }}
    subject: TickEye 基金监测失败
    body: GitHub Actions 运行失败，请检查日志。
    to: your-email@example.com
```

## 🛡️ 安全建议

1. **敏感信息**: 所有敏感信息都应该通过 GitHub Secrets 管理
2. **权限控制**: 确保仓库的 Actions 权限设置合理
3. **定期检查**: 定期检查 workflow 运行状态
4. **备份配置**: 保留配置文件的备份

## 📝 故障排除

### 常见问题

**Q: Workflow 没有按时运行**
A: GitHub Actions 的 cron 可能有延迟，通常在设定时间的 0-15 分钟内运行

**Q: 飞书通知发送失败**
A: 检查 `FEISHU_WEBHOOK_URL` Secret 是否配置正确

**Q: 基金数据获取失败**
A: 可能是网络问题或 akshare API 限制，查看详细日志

**Q: Python 依赖安装失败**
A: 检查 `requirements.txt` 文件是否正确

### 调试技巧

1. **启用详细日志**:
   ```yaml
   - name: Run fund monitor
     env:
       PYTHONUNBUFFERED: 1
       DEBUG: true
   ```

2. **添加调试输出**:
   ```yaml
   - name: Debug info
     run: |
       echo "Python version: $(python --version)"
       echo "Current directory: $(pwd)"
       echo "Files: $(ls -la)"
   ```

## 🎯 最佳实践

1. **测试优先**: 先手动运行几次确保正常
2. **监控运行**: 定期检查运行状态和日志
3. **备份重要**: 保留重要配置的备份
4. **文档更新**: 及时更新配置文档

---

## 📞 支持

如果遇到问题：
1. 查看 GitHub Actions 官方文档
2. 检查项目的 Issues 页面
3. 参考本项目的运行日志

祝你使用愉快！🦉
