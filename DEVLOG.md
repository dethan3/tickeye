# 📝 开发日志

## 2025-12-03 指数数据源调整

- **A 股指数数据源调整**  
  - `fund_analysis._build_cn_index_spot_df` 调整为：
    - **优先使用新浪接口** `stock_zh_index_spot_sina` 获取 A 股指数实时行情；
    - 当新浪获取失败或无匹配数据时，再使用 **东财接口** `stock_zh_index_spot_em(symbol="沪深重要指数")` 作为兜底；
    - 仍在失败时，保持回退到 `stock_zh_index_daily` 的历史日线逻辑不变。

- **全球指数数据源调整**  
  - `fund_analysis.get_global_index_data` 调整为：
    - **优先使用新浪接口** 获取核心全球指数：
      - `HSI`：`stock_hk_index_spot_sina`；
      - `SPX` / `NDX`：`index_us_stock_sina`（使用最近两个收盘价计算日涨跌幅）；
    - 当新浪失败时，再使用 **东财接口** `index_global_spot_em` 作为兜底，并通过 `indices_config.json` 中的别名配置匹配指数代码/名称；
    - 对目前未配置新浪数据源的其他全球指数，如果东财也不可用，则返回空结果并记录 warning 日志。

- **监控配置调整**  
  - `funds_config.json` 中移除以下全球指数代码，使其暂不参与监控：
    - `VNINDEX`（越南胡志明）
    - `SENSEX`（印度孟买 SENSEX）
  - 当前默认监控的指数为：`000001`（上证指数）、`HSI`（恒生指数）、`NDX`（纳斯达克）、`SPX`（标普 500），且均已通过新浪/东财组合数据源成功获取数据（实测）。

> 备注：上述调整的目标是降低东财接口不稳定（`RemoteDisconnected` 等）对整体监控结果的影响，尽量保证关键指数数据由新浪提供，东财仅在必要时作为备用数据源。
