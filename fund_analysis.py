#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金分析工具 - 专门用于查看基金每日涨跌幅度
Author: TickEye Team
Date: 2025-01-24
"""

import sys
import os
import logging
from datetime import datetime, timedelta
import pandas as pd

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from monitor.fetcher import SimpleFundDataFetcher
from utils.logger import setup_logger

def analyze_fund_270042(days: int = 30):
    """
    分析基金 270042 的每日涨跌幅度
    
    Args:
        days: 分析最近多少天的数据
    """
    # 设置日志
    logger = setup_logger('fund_analysis', level=logging.INFO)
    
    # 创建数据获取器
    fetcher = SimpleFundDataFetcher()
    
    print(f"\n🔍 正在分析基金 270042 最近 {days} 天的涨跌幅度...")
    print("=" * 60)
    
    try:
        # 获取基金每日涨跌数据
        daily_changes = fetcher.get_fund_daily_changes('270042', days=days)
        
        if daily_changes is None or daily_changes.empty:
            print("❌ 未能获取到基金数据，请检查网络连接或基金代码是否正确")
            return
        
        # 显示基金基本信息
        print(f"📊 基金代码: 270042")
        print(f"📅 数据时间范围: {daily_changes['净值日期'].min().strftime('%Y-%m-%d')} 至 {daily_changes['净值日期'].max().strftime('%Y-%m-%d')}")
        print(f"📈 数据条数: {len(daily_changes)} 条")
        print()
        
        # 显示详细的每日数据
        print("📋 每日涨跌幅度明细:")
        print("-" * 60)
        print(f"{'日期':<12} {'单位净值':<10} {'涨跌幅(%)':<12} {'趋势':<6}")
        print("-" * 60)
        
        for _, row in daily_changes.iterrows():
            date_str = row['净值日期'].strftime('%Y-%m-%d')
            net_value = f"{row['单位净值']:.4f}"
            
            if '涨跌幅(%)' in row and pd.notna(row['涨跌幅(%)']):
                change_pct = row['涨跌幅(%)']
                if isinstance(change_pct, str):
                    change_str = change_pct
                    # 简单判断趋势
                    if '%' in change_pct:
                        try:
                            change_num = float(change_pct.replace('%', ''))
                            trend = "📈" if change_num > 0 else "📉" if change_num < 0 else "➡️"
                        except:
                            trend = "❓"
                    else:
                        trend = "❓"
                else:
                    change_str = f"{change_pct:.2f}%"
                    trend = "📈" if change_pct > 0 else "📉" if change_pct < 0 else "➡️"
            else:
                change_str = "N/A"
                trend = "❓"
            
            print(f"{date_str:<12} {net_value:<10} {change_str:<12} {trend:<6}")
        
        # 统计分析
        print("\n📊 统计分析:")
        print("-" * 40)
        
        if '涨跌幅(%)' in daily_changes.columns:
            # 处理涨跌幅数据
            changes = daily_changes['涨跌幅(%)'].copy()
            
            # 如果是字符串格式，转换为数值
            if changes.dtype == 'object':
                changes = changes.str.replace('%', '').astype(float, errors='ignore')
            
            # 过滤有效数据
            valid_changes = changes.dropna()
            
            if len(valid_changes) > 0:
                positive_days = len(valid_changes[valid_changes > 0])
                negative_days = len(valid_changes[valid_changes < 0])
                flat_days = len(valid_changes[valid_changes == 0])
                
                print(f"📈 上涨天数: {positive_days} 天 ({positive_days/len(valid_changes)*100:.1f}%)")
                print(f"📉 下跌天数: {negative_days} 天 ({negative_days/len(valid_changes)*100:.1f}%)")
                print(f"➡️  平盘天数: {flat_days} 天 ({flat_days/len(valid_changes)*100:.1f}%)")
                print(f"📊 最大涨幅: {valid_changes.max():.2f}%")
                print(f"📊 最大跌幅: {valid_changes.min():.2f}%")
                print(f"📊 平均涨跌幅: {valid_changes.mean():.2f}%")
                print(f"📊 涨跌幅标准差: {valid_changes.std():.2f}%")
        
        print("\n✅ 分析完成!")
        
    except Exception as e:
        logger.error(f"分析过程中出现错误: {e}")
        print(f"❌ 分析失败: {e}")

def main():
    """主函数"""
    print("🦉 TickEye 基金分析工具")
    print("专注于基金 270042 的每日涨跌幅度分析")
    
    # 默认分析最近30天
    days = 30
    
    # 如果有命令行参数，使用指定天数
    if len(sys.argv) > 1:
        try:
            days = int(sys.argv[1])
            if days <= 0:
                print("❌ 天数必须大于0")
                return
        except ValueError:
            print("❌ 请输入有效的天数")
            return
    
    analyze_fund_270042(days)

if __name__ == "__main__":
    main()
