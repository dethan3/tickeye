#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量市场分析工具 - 支持同时查询多只股票和基金的涨跌幅
Author: TickEye Team
Date: 2025-01-24
"""

import sys
import os
import json
from typing import List, Dict

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from monitor.market_data_fetcher import MarketDataFetcher
from utils.logger import setup_logger

def create_sample_watchlist() -> List[Dict[str, str]]:
    """创建示例监控列表"""
    return [
        # 基金
        {"code": "270042", "type": "fund", "name": "广发纯债债券A"},
        {"code": "000001", "type": "fund", "name": "华夏成长混合"},
        {"code": "110022", "type": "fund", "name": "易方达消费行业股票"},
        
        # 股票
        {"code": "000001", "type": "stock", "name": "平安银行"},
        {"code": "000002", "type": "stock", "name": "万科A"},
        {"code": "600036", "type": "stock", "name": "招商银行"},
    ]

def display_results(data_dict: Dict, analysis: Dict):
    """显示查询结果"""
    print("\n" + "="*80)
    print("📊 批量市场数据分析结果")
    print("="*80)
    
    # 显示摘要
    summary = analysis.get("summary", {})
    print(f"\n📋 数据摘要:")
    print(f"   基金数量: {summary.get('funds_count', 0)}")
    print(f"   股票数量: {summary.get('stocks_count', 0)}")
    
    # 显示基金数据
    if data_dict.get("funds") is not None:
        funds_df = data_dict["funds"]
        print(f"\n💰 基金数据 ({len(funds_df)} 只):")
        print("-" * 60)
        
        # 显示列名以便调试
        print(f"📋 可用列: {list(funds_df.columns)}")
        
        # 尝试显示数据
        try:
            # 查找关键列
            code_col = next((col for col in funds_df.columns if '代码' in col), None)
            name_col = next((col for col in funds_df.columns if '名称' in col or '简称' in col), None)
            value_col = next((col for col in funds_df.columns if '净值' in col), None)
            change_col = next((col for col in funds_df.columns if '涨跌' in col or '增长' in col), None)
            
            print(f"{'代码':<8} {'名称':<20} {'净值':<10} {'涨跌幅':<10}")
            print("-" * 60)
            
            for _, row in funds_df.iterrows():
                code = row.get(code_col, "N/A") if code_col else "N/A"
                name = str(row.get(name_col, "N/A"))[:18] if name_col else "N/A"
                value = row.get(value_col, "N/A") if value_col else "N/A"
                change = row.get(change_col, "N/A") if change_col else "N/A"
                
                print(f"{code:<8} {name:<20} {value:<10} {change:<10}")
                
        except Exception as e:
            print(f"显示基金数据时出错: {e}")
            print("原始数据:")
            print(funds_df.head(3).to_string())
    
    # 显示股票数据
    if data_dict.get("stocks") is not None:
        stocks_df = data_dict["stocks"]
        print(f"\n📈 股票数据 ({len(stocks_df)} 只):")
        print("-" * 60)
        
        # 显示列名以便调试
        print(f"📋 可用列: {list(stocks_df.columns)}")
        
        try:
            # 查找关键列
            code_col = next((col for col in stocks_df.columns if '代码' in col), None)
            name_col = next((col for col in stocks_df.columns if '名称' in col), None)
            price_col = next((col for col in stocks_df.columns if '最新价' in col or '现价' in col), None)
            change_col = next((col for col in stocks_df.columns if '涨跌幅' in col), None)
            
            print(f"{'代码':<8} {'名称':<15} {'价格':<10} {'涨跌幅':<10}")
            print("-" * 60)
            
            for _, row in stocks_df.iterrows():
                code = row.get(code_col, "N/A") if code_col else "N/A"
                name = str(row.get(name_col, "N/A"))[:13] if name_col else "N/A"
                price = row.get(price_col, "N/A") if price_col else "N/A"
                change = row.get(change_col, "N/A") if change_col else "N/A"
                
                print(f"{code:<8} {name:<15} {price:<10} {change:<10}")
                
        except Exception as e:
            print(f"显示股票数据时出错: {e}")
            print("原始数据:")
            print(stocks_df.head(3).to_string())
    
    # 显示分析结果
    details = analysis.get("details", {})
    if details:
        print(f"\n📊 涨跌分析:")
        print("-" * 40)
        
        for data_type, detail in details.items():
            if detail:
                positive = detail.get("positive", 0)
                negative = detail.get("negative", 0)
                neutral = detail.get("neutral", 0)
                total = positive + negative + neutral
                
                if total > 0:
                    print(f"{data_type.upper()}:")
                    print(f"  📈 上涨: {positive} ({positive/total*100:.1f}%)")
                    print(f"  📉 下跌: {negative} ({negative/total*100:.1f}%)")
                    print(f"  ➡️  平盘: {neutral} ({neutral/total*100:.1f}%)")

def main():
    """主函数"""
    print("🦉 TickEye 批量市场分析工具")
    print("支持同时查询多只股票和基金的涨跌幅")
    print("=" * 50)
    
    # 设置日志
    logger = setup_logger('batch_analyzer')
    
    # 创建市场数据获取器
    fetcher = MarketDataFetcher()
    
    # 创建监控列表
    watchlist = create_sample_watchlist()
    
    print(f"\n📋 监控列表 ({len(watchlist)} 只):")
    for i, item in enumerate(watchlist, 1):
        print(f"  {i:2d}. {item['code']} ({item['type']}) - {item.get('name', 'N/A')}")
    
    print(f"\n🔍 正在获取市场数据...")
    
    try:
        # 批量获取数据
        data_dict = fetcher.get_batch_changes(watchlist, include_history=False)
        
        # 分析数据
        analysis = fetcher.analyze_changes(data_dict)
        
        # 显示结果
        display_results(data_dict, analysis)
        
        print(f"\n✅ 批量分析完成!")
        
    except Exception as e:
        logger.error(f"批量分析失败: {e}")
        print(f"❌ 分析失败: {e}")
        
        # 显示调试信息
        import traceback
        traceback.print_exc()

def test_single_api():
    """测试单个API调用"""
    print("🧪 测试单个API调用")
    print("=" * 30)
    
    import akshare as ak
    
    try:
        print("1. 测试基金日常数据API...")
        df = ak.fund_open_fund_daily_em()
        if df is not None and not df.empty:
            print(f"   ✅ 成功获取 {len(df)} 条基金数据")
            print(f"   📋 列名: {list(df.columns)}")
            
            # 查找基金270042
            code_col = None
            for col in df.columns:
                if '代码' in col:
                    code_col = col
                    break
            
            if code_col:
                target_fund = df[df[code_col] == '270042']
                if not target_fund.empty:
                    print(f"   🎯 找到基金270042:")
                    print(target_fund.to_string(index=False))
                else:
                    print(f"   ⚠️  未找到基金270042")
            else:
                print(f"   ❌ 未找到代码列")
        else:
            print(f"   ❌ API返回空数据")
    except Exception as e:
        print(f"   ❌ API调用失败: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_single_api()
    else:
        main()
