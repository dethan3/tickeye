#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版批量市场分析工具
使用健壮的数据获取器，支持重试、缓存和错误恢复
Author: TickEye Team
Date: 2025-08-04
"""

import sys
import os
import logging
from typing import List, Dict

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from monitor.robust_market_fetcher import RobustMarketFetcher

def setup_simple_logging():
    """设置简单的日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

def create_enhanced_watchlist() -> List[Dict[str, str]]:
    """创建增强版监控列表"""
    return [
        # 基金 - 包含不同类型
        {"code": "270042", "type": "fund", "name": "广发纳斯达克100ETF联接人民币(QDII)A"},
        {"code": "000001", "type": "fund", "name": "华夏成长混合"},
        {"code": "110022", "type": "fund", "name": "易方达消费行业股票"},
        {"code": "161725", "type": "fund", "name": "招商中证白酒指数(LOF)A"},
        {"code": "519674", "type": "fund", "name": "银河创新成长混合"},
        
        # 股票 - 包含不同板块
        {"code": "000001", "type": "stock", "name": "平安银行"},
        {"code": "000002", "type": "stock", "name": "万科A"},
        {"code": "600036", "type": "stock", "name": "招商银行"},
        {"code": "600519", "type": "stock", "name": "贵州茅台"},
        {"code": "000858", "type": "stock", "name": "五粮液"},
    ]

def display_enhanced_results(results: Dict, analysis: Dict):
    """显示增强版查询结果"""
    print("\n" + "="*80)
    print("🚀 TickEye 增强版批量市场分析结果")
    print("="*80)
    
    # 显示查询摘要
    summary = results.get("summary", {})
    print(f"\n📊 查询摘要:")
    print(f"   总计请求: {summary.get('total_requested', 0)} 只")
    print(f"   基金请求: {summary.get('funds_requested', 0)} 只")
    print(f"   股票请求: {summary.get('stocks_requested', 0)} 只")
    print(f"   基金成功: {summary.get('funds_found', 0)} 只")
    print(f"   股票成功: {summary.get('stocks_found', 0)} 只")
    print(f"   成功率: {summary.get('success_rate', 0):.1f}%")
    
    # 显示基金数据
    if results.get("funds") is not None:
        funds_df = results["funds"]
        print(f"\n💰 基金数据详情 ({len(funds_df)} 只):")
        print("-" * 80)
        print(f"{'代码':<8} {'名称':<25} {'净值':<10} {'涨跌幅':<10} {'状态':<15}")
        print("-" * 80)
        
        for _, row in funds_df.iterrows():
            code = row.get('基金代码', 'N/A')
            name = str(row.get('基金简称', 'N/A'))[:23]
            
            # 获取净值信息
            net_value = "N/A"
            for col in row.index:
                if '单位净值' in col and pd.notna(row[col]) and row[col] != '':
                    net_value = str(row[col])
                    break
            
            # 获取涨跌幅
            change = "N/A"
            change_col = row.get('日增长率', '')
            if pd.notna(change_col) and change_col != '':
                change = str(change_col)
            
            # 获取状态
            buy_status = str(row.get('申购状态', 'N/A'))[:7]
            redeem_status = str(row.get('赎回状态', 'N/A'))[:7]
            status = f"{buy_status}/{redeem_status}"
            
            print(f"{code:<8} {name:<25} {net_value:<10} {change:<10} {status:<15}")
    
    # 显示股票数据
    if results.get("stocks") is not None:
        stocks_df = results["stocks"]
        print(f"\n📈 股票数据详情 ({len(stocks_df)} 只):")
        print("-" * 80)
        print(f"{'代码':<8} {'名称':<15} {'最新价':<10} {'涨跌幅':<10} {'成交额(万)':<12} {'市值(亿)':<10}")
        print("-" * 80)
        
        for _, row in stocks_df.iterrows():
            code = row.get('代码', 'N/A')
            name = str(row.get('名称', 'N/A'))[:13]
            price = row.get('最新价', 'N/A')
            change = row.get('涨跌幅', 'N/A')
            
            # 处理成交额（转换为万元）
            volume = row.get('成交额', 0)
            try:
                volume_wan = f"{float(volume)/10000:.0f}" if volume != 'N/A' and pd.notna(volume) else 'N/A'
            except:
                volume_wan = 'N/A'
            
            # 处理市值（转换为亿元）
            market_cap = row.get('总市值', 0)
            try:
                market_cap_yi = f"{float(market_cap)/100000000:.1f}" if market_cap != 'N/A' and pd.notna(market_cap) else 'N/A'
            except:
                market_cap_yi = 'N/A'
            
            print(f"{code:<8} {name:<15} {price:<10} {change:<10}% {volume_wan:<12} {market_cap_yi:<10}")
    
    # 显示市场分析
    if analysis:
        print(f"\n📊 市场分析:")
        print("-" * 50)
        
        # 基金分析
        funds_analysis = analysis.get("funds_analysis", {})
        if funds_analysis:
            print(f"基金市场:")
            print(f"  📈 上涨: {funds_analysis.get('rising', 0)} 只")
            print(f"  📉 下跌: {funds_analysis.get('falling', 0)} 只")
            print(f"  ➡️  平盘: {funds_analysis.get('flat', 0)} 只")
        
        # 股票分析
        stocks_analysis = analysis.get("stocks_analysis", {})
        if stocks_analysis:
            avg_change = stocks_analysis.get('avg_change', 0)
            print(f"股票市场:")
            print(f"  📈 上涨: {stocks_analysis.get('rising', 0)} 只")
            print(f"  📉 下跌: {stocks_analysis.get('falling', 0)} 只")
            print(f"  ➡️  平盘: {stocks_analysis.get('flat', 0)} 只")
            print(f"  📊 平均涨跌幅: {avg_change:.2f}%")
        
        # 市场概览
        market_overview = analysis.get("market_overview", {})
        if market_overview:
            sentiment = market_overview.get('market_sentiment', '中性')
            print(f"市场情绪: {sentiment}")

def test_robust_features():
    """测试健壮性功能"""
    print("🧪 测试健壮性功能")
    print("=" * 40)
    
    # 创建获取器实例
    fetcher = RobustMarketFetcher(max_retries=2, cache_duration=60)
    
    # 测试缓存功能
    print("1. 测试缓存功能...")
    start_time = time.time()
    
    # 第一次调用
    result1 = fetcher.get_fund_data_robust(['270042'])
    time1 = time.time() - start_time
    
    # 第二次调用（应该使用缓存）
    start_time2 = time.time()
    result2 = fetcher.get_fund_data_robust(['270042'])
    time2 = time.time() - start_time2
    
    print(f"   第一次调用耗时: {time1:.2f} 秒")
    print(f"   第二次调用耗时: {time2:.2f} 秒")
    print(f"   缓存效果: {'✅ 有效' if time2 < time1/2 else '❌ 无效'}")
    
    return result1 is not None

def main():
    """主函数"""
    print("🦉 TickEye 增强版批量市场分析工具")
    print("支持重试机制、智能缓存和错误恢复")
    print("=" * 60)
    
    # 设置日志
    setup_simple_logging()
    
    # 创建健壮的市场数据获取器
    fetcher = RobustMarketFetcher(
        max_retries=3,      # 最大重试3次
        batch_size=50,      # 批处理大小
        cache_duration=300  # 缓存5分钟
    )
    
    # 创建监控列表
    watchlist = create_enhanced_watchlist()
    
    print(f"\n📋 增强版监控列表 ({len(watchlist)} 只):")
    fund_count = sum(1 for item in watchlist if item["type"] == "fund")
    stock_count = sum(1 for item in watchlist if item["type"] == "stock")
    print(f"   基金: {fund_count} 只")
    print(f"   股票: {stock_count} 只")
    
    for i, item in enumerate(watchlist, 1):
        type_icon = "💰" if item["type"] == "fund" else "📈"
        print(f"   {i:2d}. {type_icon} {item['code']} - {item.get('name', 'N/A')}")
    
    print(f"\n🔍 开始批量查询...")
    
    try:
        import time
        start_time = time.time()
        
        # 批量查询数据
        results = fetcher.batch_query(watchlist)
        
        # 分析数据
        analysis = fetcher.analyze_market_data(results)
        
        query_time = time.time() - start_time
        
        # 显示结果
        display_enhanced_results(results, analysis)
        
        print(f"\n⏱️  查询耗时: {query_time:.2f} 秒")
        print(f"✅ 增强版批量分析完成!")
        
        # 测试健壮性功能
        if len(sys.argv) > 1 and sys.argv[1] == "--test-robust":
            print(f"\n" + "="*60)
            test_robust_features()
        
    except Exception as e:
        logging.error(f"批量分析失败: {e}")
        print(f"❌ 分析失败: {e}")
        
        # 显示调试信息
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import pandas as pd
    import time
    main()
