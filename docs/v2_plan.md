# Tickeye V2 Plan

我想做的不是“Trader”，而更接近 **Independent Systematic Investor / Solo Quant Investor**：不追求高频交易，而是长期积累数据、形成判断框架、制定资产配置与买卖规则，再用软件持续验证。

 `tickeye` 这个项目其实非常适合作为这条路线的起点。

目前 TickEye 已经具备了基金/指数跟踪、AkShare 数据获取、pandas 数据处理、实时数据回退和每日表现分析等能力。 而且已经通过 GitHub Actions 把它做成了定时运行的系统，而不是需要每天手动执行的脚本。 数据源不稳定时，甚至已经在新浪、东财、历史数据之间设计了 fallback。

这其实已经体现出一种很好的方向：

> **不是预测市场，而是建立自己的市场观察基础设施。**

建议以后就沿着这条路走。

## TickEye 不要变成“荐股机器人”

我反而建议把它逐渐发展成：

```text
TickEye
│
├── 1. Market Data
│      基金 / ETF / 指数 / 利率 / 黄金 / 汇率
│
├── 2. Portfolio
│      我的持仓 / 成本 / 现金流 / 权重
│
├── 3. Analytics
│      收益率 / 波动率 / Drawdown / Sharpe
│      Correlation / Rolling Return
│
├── 4. Research
│      策略假设
│      Backtest
│      Benchmark
│      Scenario Analysis
│
├── 5. Decision Rules
│      定投
│      再平衡
│      仓位调整
│      风险控制
│
└── 6. Research Agent
       数据整理
       新闻 / 财报摘要
       异常解释
       投资日志
       Research Report
```

注意最下面才是 Agent。

我认为这点特别重要。

---

## 现在真正应该做的是 TickEye v2：Portfolio Analytics

现在 TickEye 回答的是：

> **今天市场怎么样？**

下一阶段应该回答：

> **我的钱现在处于什么风险状态？**

这是完全不同的层次。

第一批我会加入这些指标：

**Portfolio Return**

你的组合：

* 今日收益
* 本月收益
* YTD
* 1Y
* CAGR

然后是：

**Risk**

* Annualized Volatility
* Max Drawdown
* 当前 Drawdown
* Downside Volatility

然后：

**Risk-adjusted Return**

* Sharpe
* Sortino

再然后：

**Portfolio Structure**

* 每项资产权重
* 股票 / 债券 / 黄金 / 现金比例
* 中国 / 美国 / 日本等地域暴露
* Correlation Matrix

最后：

**Benchmark**

例如：

```text
My Portfolio      +8.7%
CSI300             +4.2%
S&P 500           +10.1%
60/40 Benchmark    +6.8%
```

这样你才会逐渐拥有自己的 **portfolio intelligence**。

---

## 第二步才是策略研究

这里我尤其建议你克制。

不要开始：

> RSI < 30 买入
> MACD 金叉买入
> AI 判断牛熊

而是先研究一些**非常朴素的长期投资规则**。

例如：

### Strategy A：定投

每月固定日期：

```text
¥3000 → Portfolio
```

长期结果怎样？

---

### Strategy B：再平衡

比如：

```text
股票     60%
债券     20%
黄金     10%
现金     10%
```

每季度 / 每半年再平衡。

然后研究：

> 年度再平衡 vs 季度再平衡有什么区别？

---

### Strategy C：Threshold Rebalancing

不是每个月操作。

而是目标：

```text
股票 60%
```

实际超过：

```text
66%
```

或者跌到：

```text
54%
```

才进行调整。

这已经是很典型的系统化投资思想。

---

### Strategy D：Trend Filter

例如研究：

```text
Price > 200D MA
→ 正常配置

Price < 200D MA
→ 降低风险资产比例
```

不是因为：

> “200 日均线很神奇。”

而是测试：

> 它是否在长期数据中降低 Drawdown？

研究目标可能不是提高收益率，而是：

**降低风险。**

这非常适合你这种长线路线。

---

## 可能涉及到的理论

### 第一优先级：Portfolio Management

**Return**

```text
Simple Return
Log Return
Cumulative Return
CAGR
```

**Risk**

```text
Volatility
Drawdown
Max Drawdown
VaR
```

**Risk-adjusted Return**

```text
Sharpe
Sortino
Calmar
```

这是 TickEye 马上就能用上的知识。

---

### 第二优先级：Statistics

只研究真正需要的

例如：

```text
Mean
Variance
Standard Deviation
Correlation
Covariance

Distribution

Regression

Sampling

Confidence Interval
```

然后进一步：

```text
Rolling Mean
Rolling Volatility
Rolling Correlation
```

这些东西都会直接变成 TickEye 的代码。

于是学习就不会很枯燥。

---

# 第三优先级：Backtesting

应该深入需要理解：

**Look-ahead Bias**

例如你用了当天收盘价产生信号，却假设当天收盘价成交。

---

**Survivorship Bias**

今天存在的基金：

≠

十年前所有能投资的基金。

---

**Overfitting**

测试：

100 个参数

最后找到：

```text
MA = 137 days
```

年化最高。

大概率没什么意义。

---

**Transaction Cost**

即使是低频策略也要考虑：

手续费
申购赎回费
ETF spread
税费
滑点。

---

**Out-of-sample**

例如：

```text
2010 ───────── 2020
       Research

2021 ───────── 2025
       Validation
```

不要所有数据都拿来优化参数。

---

### Macro

例如：

通胀
利率
经济增长
信用周期
收益率曲线
美元
大宗商品。

但同样不要发展成：

> “美联储降息 → 纳指一定涨。”

而是研究不同经济环境：

```text
Growth ↑ / Inflation ↓

Growth ↓ / Inflation ↓

Growth ↑ / Inflation ↑

Growth ↓ / Inflation ↑
```

不同资产历史上表现有什么差异。

这就逐渐变成：

**Asset Allocation Research。**

---

#  TickEye 最终可以形成一个很漂亮的结构

```text
                TickEye

           Data Infrastructure
                  │
        ┌─────────┼─────────┐
        ↓         ↓         ↓
      Market   Portfolio   Macro
        │         │         │
        └─────────┼─────────┘
                  ↓
             Research DB
                  │
                  ↓
           Backtest Engine
                  │
                  ↓
             Risk Engine
                  │
                  ↓
          Investment Policy
                  │
                  ↓
            Decision Engine
                  │
                  ↓
             Human Review
```

Agent 在旁边：

```text
Research Agent
     │
     ├── 收集信息
     ├── 总结市场
     ├── 查询历史
     ├── 调用 Backtest
     ├── 比较策略
     └── 生成 Investment Journal
```

而不是：

```text
LLM
 ↓
猜涨跌
 ↓
买股票
```

两者差别非常大。

---

## 尤其看好「Investment Journal」

以后每次真正做投资决策，都保存：

```text
2026-xx-xx

Action:
增加黄金 ETF 5%

Reason:
组合黄金权重从目标10%下降至6.8%

Rule:
Rebalance threshold ±3%

Market view:
不作为此次交易依据

Expected result:
恢复目标资产配置

Review date:
6 months later
```

六个月以后：

TickEye 可以问你：

> 当时为什么买？

然后：

> 实际结果如何？

长期积累几十、几百条之后，你会拥有一样很多个人投资者没有的资产：

**自己的决策数据集。**

甚至可以分析：

> 哪类决策是赚钱的？

> 哪些主动判断经常错？

> 再平衡贡献了多少收益？

> 我的择时到底有没有 Alpha？

这时候 Agent 才真正变得非常有趣。

---
